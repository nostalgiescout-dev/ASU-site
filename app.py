"""
Scouts Only - Complete web platform for Scout Association
Main Flask application with routes for public website and admin dashboard
"""

import os
import csv
import re
import secrets
from io import StringIO
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import parse_qs, urlparse
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for, 
    session, flash, jsonify, abort, send_from_directory, Response
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import Babel, gettext as _
from sqlalchemy import inspect, or_, text
from sqlalchemy.orm import joinedload
from models import db, User, Unit, Club, Activity, Group, HomePage

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ACTIVITY_STATUSES = {'upcoming', 'ongoing', 'completed'}
EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
CURRENT_DATE = datetime(2026, 8, 21)
_activity_schema_ready = False

def _get_env_name():
    value = (os.environ.get('SCOUTS_ONLY_ENV') or os.environ.get('FLASK_ENV') or 'development').strip().lower()
    return value or 'development'

ENV_NAME = _get_env_name()
IS_PRODUCTION = ENV_NAME in {'prod', 'production'}

# Create app
app = Flask(__name__, static_folder='static')
_secret_key = os.environ.get('SECRET_KEY')
if not _secret_key:
    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be set in production (set env var SECRET_KEY).")
    _secret_key = secrets.token_urlsafe(32)
app.config['SECRET_KEY'] = _secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///scouts_only.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BABEL_DEFAULT_LOCALE'] = 'ar'
app.config['BABEL_SUPPORTED_LOCALES'] = ['ar', 'en', 'fr', 'es']

# Create upload folder
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize database and i18n
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

def get_locale():
    """Get current locale from URL, session, or browser preference."""
    supported = app.config['BABEL_SUPPORTED_LOCALES']
    lang = request.args.get('lang')
    if lang in supported:
        return lang

    lang = session.get('lang')
    if lang in supported:
        return lang

    return request.accept_languages.best_match(supported) or app.config['BABEL_DEFAULT_LOCALE']


@app.before_request
def persist_requested_locale():
    """Persist ?lang=<code> in session for the next requests."""
    lang = request.args.get('lang')
    if lang in app.config['BABEL_SUPPORTED_LOCALES']:
        session['lang'] = lang

def get_translated_field(obj, field_name, lang=None):
    """Return the best available translated model field for the active locale."""
    selected_lang = lang or get_locale()
    fallback_langs = ['ar', 'en', 'fr', 'es']
    candidates = [selected_lang] + [code for code in fallback_langs if code != selected_lang]

    for code in candidates:
        value = getattr(obj, f'{field_name}_{code}', None)
        if value:
            return value
    return ''

babel = Babel(app, locale_selector=get_locale)

@app.context_processor
def inject_locale():
    """Inject locale and helper functions into templates"""
    def current_query_url(endpoint, **updates):
        values = request.args.to_dict(flat=True)
        for key, value in updates.items():
            if value in (None, ''):
                values.pop(key, None)
            else:
                values[key] = value
        return url_for(endpoint, **values)

    return {
        'get_locale': get_locale,
        'translate_field': get_translated_field,
        'current_lang': get_locale(),
        'supported_langs': app.config['BABEL_SUPPORTED_LOCALES'],
        'get_video_embed_url': get_video_embed_url,
        'current_query_url': current_query_url
    }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_today_start():
    """Return the start of today for activity comparisons."""
    return CURRENT_DATE.replace(hour=0, minute=0, second=0, microsecond=0)

def normalize_optional_text(value):
    """Trim optional text values and collapse blanks to None."""
    if value is None:
        return None
    value = value.strip()
    return value or None

def require_text(value, label):
    """Validate required text fields."""
    cleaned = normalize_optional_text(value)
    if not cleaned:
        raise ValueError(f'يرجى إدخال {label}.')
    return cleaned

def parse_activity_datetime(value):
    """Parse the admin activity datetime-local input safely."""
    cleaned = normalize_optional_text(value)
    if not cleaned:
        raise ValueError('يرجى تحديد تاريخ ووقت النشاط.')
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise ValueError('صيغة تاريخ النشاط غير صحيحة.') from exc

def suggest_activity_status(activity_date):
    """Suggest a status from the activity date relative to today."""
    if not activity_date:
        return 'upcoming'

    today = get_today_start().date()
    activity_day = activity_date.date()
    if activity_day < today:
        return 'completed'
    if activity_day == today:
        return 'ongoing'
    return 'upcoming'

def validate_url(value, label):
    """Validate optional HTTP(S) URLs."""
    cleaned = normalize_optional_text(value)
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError(f'{label} يجب أن يكون رابطًا صحيحًا يبدأ بـ http أو https.')
    return cleaned

def validate_email(value):
    """Validate optional email values."""
    cleaned = normalize_optional_text(value)
    if not cleaned:
        return None
    if not EMAIL_PATTERN.match(cleaned):
        raise ValueError('يرجى إدخال بريد إلكتروني صالح للتواصل.')
    return cleaned

def validate_optional_positive_int(value, label):
    """Validate optional positive integer values."""
    cleaned = normalize_optional_text(value)
    if not cleaned:
        return None
    try:
        parsed = int(cleaned)
    except ValueError as exc:
        raise ValueError(f'{label} يجب أن يكون رقمًا صحيحًا.') from exc
    if parsed < 1:
        raise ValueError(f'{label} يجب أن يكون أكبر من صفر.')
    return parsed

def get_video_embed_url(video_url):
    """Convert common video URLs to embeddable URLs when possible."""
    cleaned = normalize_optional_text(video_url)
    if not cleaned:
        return None

    parsed = urlparse(cleaned)
    host = parsed.netloc.lower()

    if 'youtube.com' in host:
        if parsed.path.startswith('/embed/'):
            return cleaned
        video_id = parse_qs(parsed.query).get('v', [''])[0]
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}'
    if 'youtu.be' in host:
        video_id = parsed.path.strip('/')
        if video_id:
            return f'https://www.youtube.com/embed/{video_id}'
    if 'vimeo.com' in host and parsed.path.strip('/').isdigit():
        return f'https://player.vimeo.com/video/{parsed.path.strip("/")}'

    return cleaned

def save_uploaded_activity_image(activity, file_storage):
    """Store an uploaded activity image if a valid file was provided."""
    if not file_storage or not file_storage.filename:
        return
    if not allowed_file(file_storage.filename):
        raise ValueError('صيغة الصورة غير مدعومة. استخدم png أو jpg أو jpeg أو gif أو webp.')

    filename = secure_filename(f"activity_{activity.id}_{file_storage.filename}")
    file_storage.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    activity.image_url = f"/uploads/{filename}"

def apply_activity_form_data(activity, form, files):
    """Validate and assign admin activity form values to a model instance."""
    activity_date = parse_activity_datetime(form.get('date'))
    selected_status = normalize_optional_text(form.get('status'))
    suggested_status = suggest_activity_status(activity_date)

    activity.title_ar = require_text(form.get('title_ar'), 'العنوان بالعربية')
    activity.title_en = require_text(form.get('title_en'), 'العنوان بالإنجليزية')
    activity.title_fr = require_text(form.get('title_fr'), 'العنوان بالفرنسية')
    activity.title_es = require_text(form.get('title_es'), 'العنوان بالإسبانية')
    activity.description_ar = require_text(form.get('description_ar'), 'الوصف بالعربية')
    activity.description_en = require_text(form.get('description_en'), 'الوصف بالإنجليزية')
    activity.description_fr = require_text(form.get('description_fr'), 'الوصف بالفرنسية')
    activity.description_es = require_text(form.get('description_es'), 'الوصف بالإسبانية')

    activity.date = activity_date
    activity.location_ar = normalize_optional_text(form.get('location_ar'))
    activity.location_en = normalize_optional_text(form.get('location_en'))
    activity.video_url = validate_url(form.get('video_url'), 'رابط الفيديو')
    activity.registration_url = validate_url(form.get('registration_url'), 'رابط التسجيل')
    activity.club_id = normalize_optional_text(form.get('club_id'))
    activity.max_participants = validate_optional_positive_int(form.get('max_participants'), 'الحد الأقصى للمشاركين')
    activity.contact_email = validate_email(form.get('contact_email'))
    activity.contact_phone = normalize_optional_text(form.get('contact_phone'))
    activity.featured = form.get('featured') == 'on'
    activity.is_published = form.get('is_published') == 'on'
    activity.status = selected_status if selected_status in ACTIVITY_STATUSES else suggested_status

    save_uploaded_activity_image(activity, files.get('image'))
    return suggested_status

def duplicate_activity_title(value, locale):
    """Append a lightweight copy suffix for duplicated activities."""
    suffixes = {
        'ar': ' (نسخة)',
        'en': ' (Copy)',
        'fr': ' (Copie)',
        'es': ' (Copia)'
    }
    return f'{value}{suffixes.get(locale, " (Copy)")}' if value else value

def get_activity_filters(args):
    """Extract normalized admin filter values from query params."""
    return {
        'search': (args.get('search') or '').strip(),
        'status': (args.get('status') or '').strip(),
        'club_id': (args.get('club_id') or '').strip(),
        'featured': (args.get('featured') or '').strip(),
        'published': (args.get('published') or '').strip(),
        'sort': (args.get('sort') or 'desc').strip().lower()
    }

def build_activity_admin_query(filters):
    """Build the filtered admin activities query."""
    query = Activity.query.options(joinedload(Activity.club))

    if filters['search']:
        search_term = f"%{filters['search']}%"
        query = query.filter(
            or_(
                Activity.title_ar.ilike(search_term),
                Activity.title_en.ilike(search_term),
                Activity.title_fr.ilike(search_term),
                Activity.title_es.ilike(search_term)
            )
        )

    if filters['status'] in ACTIVITY_STATUSES:
        query = query.filter(Activity.status == filters['status'])

    if filters['club_id']:
        query = query.filter(Activity.club_id == filters['club_id'])

    if filters['featured'] == 'yes':
        query = query.filter(Activity.featured.is_(True))
    elif filters['featured'] == 'no':
        query = query.filter(Activity.featured.is_(False))

    if filters['published'] == 'yes':
        query = query.filter(Activity.is_published.is_(True))
    elif filters['published'] == 'no':
        query = query.filter(Activity.is_published.is_(False))

    sort_expression = Activity.date.asc() if filters['sort'] == 'asc' else Activity.date.desc()
    return query.order_by(sort_expression, Activity.created_at.desc())

def get_safe_redirect_target(default_endpoint='admin_activities'):
    """Return a local redirect target after admin quick actions."""
    target = request.form.get('next') or request.args.get('next')
    if target and target.startswith('/'):
        return target
    return url_for(default_endpoint)

def ensure_activity_schema():
    """Add missing activity columns when migrations are not configured."""
    global _activity_schema_ready

    if _activity_schema_ready:
        return

    db.create_all()
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    if 'activities' not in existing_tables:
        _activity_schema_ready = True
        return

    existing_columns = {column['name'] for column in inspector.get_columns('activities')}
    alter_statements = {
        'featured': "ALTER TABLE activities ADD COLUMN featured BOOLEAN DEFAULT 0",
        'registration_url': "ALTER TABLE activities ADD COLUMN registration_url VARCHAR(255)",
        'max_participants': "ALTER TABLE activities ADD COLUMN max_participants INTEGER",
        'is_published': "ALTER TABLE activities ADD COLUMN is_published BOOLEAN DEFAULT 1",
        'contact_email': "ALTER TABLE activities ADD COLUMN contact_email VARCHAR(120)",
        'contact_phone': "ALTER TABLE activities ADD COLUMN contact_phone VARCHAR(50)"
    }

    with db.engine.begin() as connection:
        for column_name, statement in alter_statements.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))
        if 'is_published' not in existing_columns:
            connection.execute(text("UPDATE activities SET is_published = 1 WHERE is_published IS NULL"))
        if 'featured' not in existing_columns:
            connection.execute(text("UPDATE activities SET featured = 0 WHERE featured IS NULL"))

    _activity_schema_ready = True

@app.before_request
def ensure_schema_before_requests():
    """Ensure the runtime schema is compatible before serving requests."""
    ensure_activity_schema()

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('غير مصرح لك بالوصول إلى هذه الصفحة', 'error')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# PUBLIC ROUTES
# ============================================================================

@app.route('/')
def home():
    """Homepage."""
    association = HomePage.query.first()
    if not association:
        association = HomePage()
        db.session.add(association)
        db.session.commit()

    units = Unit.query.order_by(Unit.order).all()
    clubs = Club.query.order_by(Club.order).all()
    today = get_today_start()
    public_activity_query = Activity.query.filter(Activity.is_published.is_(True))
    featured_upcoming_activities = public_activity_query.filter(
        Activity.featured.is_(True),
        Activity.date >= today
    ).order_by(Activity.date.asc()).limit(3).all()
    upcoming_activities = public_activity_query.filter(Activity.date >= today).order_by(Activity.date.asc()).limit(6).all()
    activities = upcoming_activities
    if not activities:
        activities = public_activity_query.order_by(Activity.date.desc()).limit(6).all()
    if not featured_upcoming_activities and upcoming_activities:
        featured_upcoming_activities = upcoming_activities[:3]

    return render_template(
        'home.html',
        units=units,
        clubs=clubs,
        activities=activities,
        featured_upcoming_activities=featured_upcoming_activities,
        association=association
    )

@app.route('/units')
def units():
    """Display all scout units"""
    units = Unit.query.order_by(Unit.order).all()
    return render_template('units.html', units=units)

@app.route('/unit/<unit_id>')
def unit_detail(unit_id):
    """Display single unit details"""
    unit = Unit.query.get_or_404(unit_id)
    return render_template('unit_detail.html', unit=unit)

@app.route('/clubs')
def clubs():
    """Display all clubs"""
    clubs = Club.query.order_by(Club.order).all()
    return render_template('clubs.html', clubs=clubs)

@app.route('/club/<club_id>')
def club_detail(club_id):
    """Display single club details with activities"""
    club = Club.query.get_or_404(club_id)
    activities = Activity.query.filter(
        Activity.club_id == club_id,
        Activity.is_published.is_(True)
    ).order_by(Activity.date.desc()).all()
    return render_template('club_detail.html', club=club, activities=activities)

@app.route('/activities')
def activities():
    """Display all activities/events"""
    page = request.args.get('page', 1, type=int)
    activities = Activity.query.filter(
        Activity.is_published.is_(True)
    ).order_by(Activity.date.desc()).paginate(page=page, per_page=12, error_out=False)
    return render_template('activities.html', activities=activities)

@app.route('/activity/<activity_id>')
def activity_detail(activity_id):
    """Display single activity details"""
    is_admin_preview = current_user.is_authenticated and current_user.role == 'admin'
    activity_query = Activity.query.filter(Activity.id == activity_id)
    if not is_admin_preview:
        activity_query = activity_query.filter(Activity.is_published.is_(True))
    activity = activity_query.first_or_404()
    if not is_admin_preview:
        activity.views += 1
        db.session.commit()
    return render_template('activity_detail.html', activity=activity)

@app.route('/find-group')
def find_group():
    """Find nearest scout group with interactive map"""
    groups = Group.query.all()
    groups_json = [group.to_dict() for group in groups]
    return render_template('find_group.html', groups=groups_json)

@app.route('/api/groups')
def api_groups():
    """API endpoint for fetching groups as JSON"""
    groups = Group.query.all()
    return jsonify([group.to_dict() for group in groups])

@app.route('/api/groups/nearby')
def api_nearby_groups():
    """Find groups near user location"""
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    radius = request.args.get('radius', 50, type=float)  # km
    
    if not lat or not lon:
        return jsonify({'error': 'Latitude and longitude required'}), 400
    
    # Simple distance calculation
    groups = Group.query.all()
    nearby = []
    
    for group in groups:
        # Haversine formula for distance
        from math import radians, cos, sin, asin, sqrt
        R = 6371  # Earth radius in km
        
        lat1, lon1 = radians(lat), radians(lon)
        lat2, lon2 = radians(group.latitude), radians(group.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        distance = R * c
        
        if distance <= radius:
            group_dict = group.to_dict()
            group_dict['distance'] = round(distance, 2)
            nearby.append(group_dict)
    
    return jsonify(sorted(nearby, key=lambda x: x['distance']))

@app.route('/set-lang/<lang>')
def set_lang(lang):
    """Set language preference"""
    if lang in app.config['BABEL_SUPPORTED_LOCALES']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('home'))

@app.route('/about')
def about():
    """About page"""
    home_page = HomePage.query.first()
    return render_template('about.html', home_page=home_page)

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
    
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    """Admin logout"""
    logout_user()
    return redirect(url_for('home'))

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Main admin dashboard"""
    stats = {
        'total_units': Unit.query.count(),
        'total_clubs': Club.query.count(),
        'total_activities': Activity.query.count(),
        'total_groups': Group.query.count(),
        'total_users': User.query.count()
    }
    
    recent_activities = Activity.query.order_by(Activity.created_at.desc()).limit(5).all()
    
    return render_template(
        'admin/dashboard.html',
        stats=stats,
        recent_activities=recent_activities
    )

# --- Units Management ---
@app.route('/admin/units')
@login_required
@admin_required
def admin_units():
    """List all units"""
    units = Unit.query.order_by(Unit.order).all()
    return render_template('admin/units.html', units=units)

@app.route('/admin/units/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_unit():
    """Create new unit"""
    if request.method == 'POST':
        try:
            unit = Unit(
                name_ar=request.form.get('name_ar'),
                name_en=request.form.get('name_en'),
                name_fr=request.form.get('name_fr'),
                name_es=request.form.get('name_es'),
                description_ar=request.form.get('description_ar'),
                description_en=request.form.get('description_en'),
                description_fr=request.form.get('description_fr'),
                description_es=request.form.get('description_es'),
                age_range=request.form.get('age_range'),
                icon=request.form.get('icon', 'scout'),
                order=request.form.get('order', 0, type=int)
            )
            
            # Handle file upload
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"unit_{unit.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    unit.image_url = f"/uploads/{filename}"
            
            db.session.add(unit)
            db.session.commit()
            flash('تم إنشاء الوحدة بنجاح', 'success')
            return redirect(url_for('admin_units'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/unit_form.html')

@app.route('/admin/units/<unit_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_unit(unit_id):
    """Edit unit"""
    unit = Unit.query.get_or_404(unit_id)
    
    if request.method == 'POST':
        try:
            unit.name_ar = request.form.get('name_ar')
            unit.name_en = request.form.get('name_en')
            unit.name_fr = request.form.get('name_fr')
            unit.name_es = request.form.get('name_es')
            unit.description_ar = request.form.get('description_ar')
            unit.description_en = request.form.get('description_en')
            unit.description_fr = request.form.get('description_fr')
            unit.description_es = request.form.get('description_es')
            unit.age_range = request.form.get('age_range')
            unit.icon = request.form.get('icon', 'scout')
            unit.order = request.form.get('order', 0, type=int)
            
            # Handle file upload
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"unit_{unit.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    unit.image_url = f"/uploads/{filename}"
            
            db.session.commit()
            flash('تم تحديث الوحدة بنجاح', 'success')
            return redirect(url_for('admin_units'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/unit_form.html', unit=unit)

@app.route('/admin/units/<unit_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_unit(unit_id):
    """Delete unit"""
    unit = Unit.query.get_or_404(unit_id)
    db.session.delete(unit)
    db.session.commit()
    flash('تم حذف الوحدة بنجاح', 'success')
    return redirect(url_for('admin_units'))

# --- Clubs Management ---
@app.route('/admin/clubs')
@login_required
@admin_required
def admin_clubs():
    """List all clubs"""
    clubs = Club.query.order_by(Club.order).all()
    return render_template('admin/clubs.html', clubs=clubs)

@app.route('/admin/clubs/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_club():
    """Create new club"""
    if request.method == 'POST':
        try:
            club = Club(
                name_ar=request.form.get('name_ar'),
                name_en=request.form.get('name_en'),
                name_fr=request.form.get('name_fr'),
                name_es=request.form.get('name_es'),
                description_ar=request.form.get('description_ar'),
                description_en=request.form.get('description_en'),
                description_fr=request.form.get('description_fr'),
                description_es=request.form.get('description_es'),
                icon=request.form.get('icon', 'palette'),
                order=request.form.get('order', 0, type=int)
            )
            
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"club_{club.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    club.image_url = f"/uploads/{filename}"
            
            db.session.add(club)
            db.session.commit()
            flash('تم إنشاء النادي بنجاح', 'success')
            return redirect(url_for('admin_clubs'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/club_form.html')

@app.route('/admin/clubs/<club_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_club(club_id):
    """Edit club"""
    club = Club.query.get_or_404(club_id)
    
    if request.method == 'POST':
        try:
            club.name_ar = request.form.get('name_ar')
            club.name_en = request.form.get('name_en')
            club.name_fr = request.form.get('name_fr')
            club.name_es = request.form.get('name_es')
            club.description_ar = request.form.get('description_ar')
            club.description_en = request.form.get('description_en')
            club.description_fr = request.form.get('description_fr')
            club.description_es = request.form.get('description_es')
            club.icon = request.form.get('icon', 'palette')
            club.order = request.form.get('order', 0, type=int)
            
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"club_{club.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    club.image_url = f"/uploads/{filename}"
            
            db.session.commit()
            flash('تم تحديث النادي بنجاح', 'success')
            return redirect(url_for('admin_clubs'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/club_form.html', club=club)

@app.route('/admin/clubs/<club_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_club(club_id):
    """Delete club"""
    club = Club.query.get_or_404(club_id)
    db.session.delete(club)
    db.session.commit()
    flash('تم حذف النادي بنجاح', 'success')
    return redirect(url_for('admin_clubs'))

# --- Activities Management ---
@app.route('/admin/activities')
@login_required
@admin_required
def admin_activities():
    """List all activities with search, filters, and pagination."""
    filters = get_activity_filters(request.args)
    page = request.args.get('page', 1, type=int)
    activities = build_activity_admin_query(filters).paginate(page=page, per_page=12, error_out=False)
    stats = {
        'upcoming': Activity.query.filter(Activity.status == 'upcoming').count(),
        'ongoing': Activity.query.filter(Activity.status == 'ongoing').count(),
        'completed': Activity.query.filter(Activity.status == 'completed').count(),
        'featured': Activity.query.filter(Activity.featured.is_(True)).count(),
        'published': Activity.query.filter(Activity.is_published.is_(True)).count()
    }
    current_url = url_for('admin_activities', **request.args.to_dict(flat=True))
    return render_template(
        'admin/activities.html',
        activities=activities,
        clubs=Club.query.order_by(Club.name_ar.asc()).all(),
        filters=filters,
        stats=stats,
        current_url=current_url
    )

@app.route('/admin/activities/export')
@login_required
@admin_required
def admin_export_activities():
    """Export activities as CSV using the current admin filters."""
    filters = get_activity_filters(request.args)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'id', 'title_ar', 'title_en', 'title_fr', 'title_es', 'date', 'club',
        'status', 'featured', 'is_published', 'views', 'registration_url',
        'max_participants', 'contact_email', 'contact_phone'
    ])

    for activity in build_activity_admin_query(filters).all():
        writer.writerow([
            activity.id,
            activity.title_ar,
            activity.title_en,
            activity.title_fr,
            activity.title_es,
            activity.date.isoformat() if activity.date else '',
            activity.club.name_ar if activity.club else '',
            activity.status,
            'yes' if activity.featured else 'no',
            'yes' if activity.is_published else 'no',
            activity.views,
            activity.registration_url or '',
            activity.max_participants or '',
            activity.contact_email or '',
            activity.contact_phone or ''
        ])

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename=activities_{timestamp}.csv'}
    )

@app.route('/admin/activities/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_activity():
    """Create new activity"""
    clubs = Club.query.all()
    
    if request.method == 'POST':
        try:
            activity = Activity()
            suggested_status = apply_activity_form_data(activity, request.form, request.files)
            db.session.add(activity)
            db.session.commit()
            flash('تم إنشاء النشاط بنجاح', 'success')
            return redirect(url_for('admin_activities'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/activity_form.html', clubs=clubs, suggested_status='upcoming')

@app.route('/admin/activities/<activity_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_activity(activity_id):
    """Edit activity"""
    activity = Activity.query.get_or_404(activity_id)
    clubs = Club.query.all()
    
    if request.method == 'POST':
        try:
            suggested_status = apply_activity_form_data(activity, request.form, request.files)
            db.session.commit()
            flash('تم تحديث النشاط بنجاح', 'success')
            return redirect(url_for('admin_activities'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template(
        'admin/activity_form.html',
        activity=activity,
        clubs=clubs,
        suggested_status=suggest_activity_status(activity.date)
    )

@app.route('/admin/activities/<activity_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_activity(activity_id):
    """Delete activity"""
    activity = Activity.query.get_or_404(activity_id)
    db.session.delete(activity)
    db.session.commit()
    flash('تم حذف النشاط بنجاح', 'success')
    return redirect(get_safe_redirect_target())

@app.route('/admin/activities/<activity_id>/mark-completed', methods=['POST'])
@login_required
@admin_required
def admin_mark_activity_completed(activity_id):
    """Quick action to mark an activity as completed."""
    activity = Activity.query.get_or_404(activity_id)
    activity.status = 'completed'
    db.session.commit()
    flash('تم تحديث حالة النشاط إلى منتهي.', 'success')
    return redirect(get_safe_redirect_target())

@app.route('/admin/activities/<activity_id>/toggle-featured', methods=['POST'])
@login_required
@admin_required
def admin_toggle_activity_featured(activity_id):
    """Quick action to toggle featured state."""
    activity = Activity.query.get_or_404(activity_id)
    activity.featured = not bool(activity.featured)
    db.session.commit()
    flash('تم تحديث تمييز النشاط.', 'success')
    return redirect(get_safe_redirect_target())

@app.route('/admin/activities/<activity_id>/duplicate', methods=['POST'])
@login_required
@admin_required
def admin_duplicate_activity(activity_id):
    """Create a draft copy of an activity."""
    activity = Activity.query.get_or_404(activity_id)
    duplicated = Activity(
        title_ar=duplicate_activity_title(activity.title_ar, 'ar'),
        title_en=duplicate_activity_title(activity.title_en, 'en'),
        title_fr=duplicate_activity_title(activity.title_fr, 'fr'),
        title_es=duplicate_activity_title(activity.title_es, 'es'),
        description_ar=activity.description_ar,
        description_en=activity.description_en,
        description_fr=activity.description_fr,
        description_es=activity.description_es,
        date=activity.date,
        location_ar=activity.location_ar,
        location_en=activity.location_en,
        image_url=activity.image_url,
        video_url=activity.video_url,
        registration_url=activity.registration_url,
        max_participants=activity.max_participants,
        is_published=False,
        featured=False,
        contact_email=activity.contact_email,
        contact_phone=activity.contact_phone,
        club_id=activity.club_id,
        status=suggest_activity_status(activity.date)
    )
    db.session.add(duplicated)
    db.session.commit()
    flash('تم إنشاء نسخة جديدة من النشاط كمسودة غير منشورة.', 'success')
    return redirect(get_safe_redirect_target())

# --- Groups Management ---
@app.route('/admin/groups')
@login_required
@admin_required
def admin_groups():
    """List all scout groups"""
    groups = Group.query.all()
    return render_template('admin/groups.html', groups=groups)

@app.route('/admin/groups/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_group():
    """Create new scout group"""
    if request.method == 'POST':
        try:
            group = Group(
                name=request.form.get('name'),
                city_ar=request.form.get('city_ar'),
                city_en=request.form.get('city_en'),
                latitude=request.form.get('latitude', type=float),
                longitude=request.form.get('longitude', type=float),
                address=request.form.get('address'),
                phone=request.form.get('phone'),
                email=request.form.get('email'),
                leader_name=request.form.get('leader_name'),
                leader_phone=request.form.get('leader_phone'),
                members_count=request.form.get('members_count', 0, type=int),
                units_active=request.form.get('units_active')
            )
            
            db.session.add(group)
            db.session.commit()
            flash('تم إنشاء المجموعة بنجاح', 'success')
            return redirect(url_for('admin_groups'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/group_form.html')

@app.route('/admin/groups/<group_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_group(group_id):
    """Edit scout group"""
    group = Group.query.get_or_404(group_id)
    
    if request.method == 'POST':
        try:
            group.name = request.form.get('name')
            group.city_ar = request.form.get('city_ar')
            group.city_en = request.form.get('city_en')
            group.latitude = request.form.get('latitude', type=float)
            group.longitude = request.form.get('longitude', type=float)
            group.address = request.form.get('address')
            group.phone = request.form.get('phone')
            group.email = request.form.get('email')
            group.leader_name = request.form.get('leader_name')
            group.leader_phone = request.form.get('leader_phone')
            group.members_count = request.form.get('members_count', 0, type=int)
            group.units_active = request.form.get('units_active')
            
            db.session.commit()
            flash('تم تحديث المجموعة بنجاح', 'success')
            return redirect(url_for('admin_groups'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/group_form.html', group=group)

@app.route('/admin/groups/<group_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_group(group_id):
    """Delete scout group"""
    group = Group.query.get_or_404(group_id)
    db.session.delete(group)
    db.session.commit()
    flash('تم حذف المجموعة بنجاح', 'success')
    return redirect(url_for('admin_groups'))

# --- Users Management ---
@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """List all users"""
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_user():
    """Create new user"""
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            if User.query.filter_by(username=username).first():
                flash('اسم المستخدم موجود بالفعل', 'error')
                return render_template('admin/user_form.html')
            
            user = User(
                username=username,
                email=request.form.get('email'),
                full_name=request.form.get('full_name'),
                role=request.form.get('role', 'editor'),
                is_active=True
            )
            user.set_password(request.form.get('password'))
            
            db.session.add(user)
            db.session.commit()
            flash('تم إنشاء المستخدم بنجاح', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/user_form.html')

@app.route('/admin/users/<user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    """Edit user"""
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        try:
            user.email = request.form.get('email')
            user.full_name = request.form.get('full_name')
            user.role = request.form.get('role')
            user.is_active = request.form.get('is_active') == 'on'
            
            password = request.form.get('password')
            if password:
                user.set_password(password)
            
            db.session.commit()
            flash('تم تحديث المستخدم بنجاح', 'success')
            return redirect(url_for('admin_users'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/user_form.html', user=user)

@app.route('/admin/users/<user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Delete user"""
    if user_id == current_user.id:
        flash('لا يمكنك حذف حسابك الخاص', 'error')
        return redirect(url_for('admin_users'))
    
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('تم حذف المستخدم بنجاح', 'success')
    return redirect(url_for('admin_users'))

# --- Settings ---
@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_settings():
    """Manage homepage and general settings"""
    home_page = HomePage.query.first()
    if not home_page:
        home_page = HomePage()
        db.session.add(home_page)
        db.session.commit()
    
    if request.method == 'POST':
        try:
            home_page.hero_title_ar = request.form.get('hero_title_ar')
            home_page.hero_title_en = request.form.get('hero_title_en')
            home_page.hero_description_ar = request.form.get('hero_description_ar')
            home_page.hero_description_en = request.form.get('hero_description_en')
            
            home_page.mission_ar = request.form.get('mission_ar')
            home_page.mission_en = request.form.get('mission_en')
            home_page.vision_ar = request.form.get('vision_ar')
            home_page.vision_en = request.form.get('vision_en')
            
            home_page.total_members = request.form.get('total_members', 0, type=int)
            home_page.total_units = request.form.get('total_units', 0, type=int)
            home_page.total_groups = request.form.get('total_groups', 0, type=int)
            home_page.established_year = request.form.get('established_year', 2000, type=int)
            
            if 'hero_image' in request.files:
                file = request.files['hero_image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"hero_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    home_page.hero_image = f"/uploads/{filename}"
            
            db.session.commit()
            flash('تم تحديث الإعدادات بنجاح', 'success')
            return redirect(url_for('admin_settings'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/settings.html', home_page=home_page)

# --- File uploads ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def server_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db():
    """Initialize database with sample data"""
    with app.app_context():
        db.create_all()
        
        # Create default admin user if not exists
        if User.query.filter_by(username='admin').first() is None:
            default_password = os.environ.get('DEFAULT_ADMIN_PASSWORD')
            if IS_PRODUCTION and not default_password:
                print("⚠️  Admin user not created: set DEFAULT_ADMIN_PASSWORD to create one in production.")
                default_password = None

            admin = User(
                username='admin',
                email='admin@scouts-only.org',
                full_name='مدير النظام',
                role='admin',
                is_active=True
            )
            if not default_password:
                default_password = 'scouts2024'
            admin.set_password(default_password)
            db.session.add(admin)
            db.session.commit()
            print(f"✅ Admin user created: admin / {default_password}")
        
        # Create sample units if not exists
        if Unit.query.count() == 0:
            units = [
                Unit(
                    name_ar='الأشبال', name_en='Cubs', name_fr='Louveteaux', name_es='Cachorros',
                    description_ar='وحدة الأشبال للأطفال من 7-10 سنوات',
                    description_en='Cubs unit for children aged 7-10',
                    description_fr='Unité des louveteaux pour enfants de 7-10 ans',
                    description_es='Unidad de Cachorros para niños de 7-10 años',
                    age_range='7-10',
                    icon='scout_small',
                    order=1
                ),
                Unit(
                    name_ar='الكشاف', name_en='Scouts', name_fr='Éclaireurs', name_es='Exploradores',
                    description_ar='وحدة الكشاف للشباب من 11-15 سنة',
                    description_en='Scouts unit for youth aged 11-15',
                    description_fr='Unité des éclaireurs pour jeunes de 11-15 ans',
                    description_es='Unidad de Exploradores para jóvenes de 11-15 años',
                    age_range='11-15',
                    icon='scout',
                    order=2
                ),
                Unit(
                    name_ar='المتقدم', name_en='Advanced', name_fr='Pionniers', name_es='Pioneros',
                    description_ar='وحدة المتقدم للشباب من 16-18 سنة',
                    description_en='Advanced unit for youth aged 16-18',
                    description_fr='Unité des pionniers pour jeunes de 16-18 ans',
                    description_es='Unidad de Pioneros para jóvenes de 16-18 años',
                    age_range='16-18',
                    icon='scout_advanced',
                    order=3
                ),
                Unit(
                    name_ar='الجوالة', name_en='Rovers', name_fr='Routiers', name_es='Caminantes',
                    description_ar='وحدة الجوالة للشباب من 19-25 سنة',
                    description_en='Rovers unit for youth aged 19-25',
                    description_fr='Unité des routiers pour jeunes de 19-25 ans',
                    description_es='Unidad de Caminantes para jóvenes de 19-25 años',
                    age_range='19-25',
                    icon='scout_rover',
                    order=4
                )
            ]
            for unit in units:
                db.session.add(unit)
            db.session.commit()
            print("✅ Sample units created")
        
        # Create sample clubs if not exists
        if Club.query.count() == 0:
            clubs = [
                Club(
                    name_ar='نادي الإعلام', name_en='Media Club', name_fr='Club Média', name_es='Club de Medios',
                    description_ar='يركز على الإعلام والصحافة والتصوير الفوتوغرافي',
                    description_en='Focuses on media, journalism and photography',
                    description_fr='Se concentre sur les médias, le journalisme et la photographie',
                    description_es='Se enfoca en medios, periodismo y fotografía',
                    icon='camera',
                    order=1
                ),
                Club(
                    name_ar='نادي البيئة', name_en='Environment Club', name_fr='Club Environnement', name_es='Club Ambiental',
                    description_ar='الاهتمام بحماية البيئة والمحافظة على الطبيعة',
                    description_en='Focus on environmental protection and nature conservation',
                    description_fr='Accent sur la protection de l\'environnement',
                    description_es='Enfoque en la protección del medio ambiente',
                    icon='leaf',
                    order=2
                ),
                Club(
                    name_ar='نادي الرياضة', name_en='Sports Club', name_fr='Club de Sports', name_es='Club de Deportes',
                    description_ar='تنظيم الأنشطة الرياضية والمسابقات',
                    description_en='Organizing sports activities and competitions',
                    description_fr='Organisation d\'activités sportives et de compétitions',
                    description_es='Organización de actividades deportivas y competiciones',
                    icon='sports',
                    order=3
                )
            ]
            for club in clubs:
                db.session.add(club)
            db.session.commit()
            print("✅ Sample clubs created")
        
        # Create sample groups if not exists
        if Group.query.count() == 0:
            groups = [
                Group(
                    name='مجموعة الرباط 1',
                    city_ar='الرباط',
                    city_en='Rabat',
                    latitude=34.0209,
                    longitude=-6.8416,
                    address='شارع محمد الخامس، الرباط',
                    phone='+212 5XX XXX XXX',
                    email='group1@scouts.ma',
                    leader_name='محمد علي',
                    leader_phone='+212 6XX XXX XXX',
                    members_count=45,
                    units_active='أشبال، كشاف، متقدم'
                ),
                Group(
                    name='مجموعة الدار البيضاء 1',
                    city_ar='الدار البيضاء',
                    city_en='Casablanca',
                    latitude=33.5731,
                    longitude=-7.5898,
                    address='بوليفار محمد الخامس، الدار البيضاء',
                    phone='+212 5XX XXX XXX',
                    email='group2@scouts.ma',
                    leader_name='فاطمة أحمد',
                    leader_phone='+212 6XX XXX XXX',
                    members_count=62,
                    units_active='أشبال، كشاف'
                ),
                Group(
                    name='مجموعة فاس 1',
                    city_ar='فاس',
                    city_en='Fez',
                    latitude=33.9716,
                    longitude=-5.0077,
                    address='حي الحمراء، فاس',
                    phone='+212 5XX XXX XXX',
                    email='group3@scouts.ma',
                    leader_name='عمر محمود',
                    leader_phone='+212 6XX XXX XXX',
                    members_count=38,
                    units_active='كشاف، متقدم، جوالة'
                )
            ]
            for group in groups:
                db.session.add(group)
            db.session.commit()
            print("✅ Sample scout groups created")
        
        # Create sample homepage content
        if HomePage.query.count() == 0:
            home = HomePage(
                hero_title_ar='جمعية كشافة فقط',
                hero_title_en='Scouts Only Association',
                hero_description_ar='منظمة شبابية تركز على تطوير الكفاءات والقيادة',
                hero_description_en='A youth organization focused on skill development and leadership',
                mission_ar='تطوير شخصية الشباب والفتيات من خلال الأنشطة التعليمية والترفيهية',
                mission_en='Develop the personality of youth through educational and recreational activities',
                vision_ar='أن نصبح الجمعية الأولى في تدريب الكوادر الشبابية',
                vision_en='To become the leading association in youth development',
                total_members=150,
                total_units=4,
                total_groups=3,
                established_year=2010
            )
            db.session.add(home)
            db.session.commit()
            print("✅ Homepage content created")
        
        print("✅ Database initialized successfully!")

if __name__ == '__main__':
    # In production, prefer running via a WSGI server and manage DB init/seed explicitly.
    if not IS_PRODUCTION or os.environ.get('SCOUTS_ONLY_SEED', '').strip().lower() in {'1', 'true', 'yes'}:
        init_db()

    debug_env = os.environ.get('FLASK_DEBUG')
    if debug_env is None or not debug_env.strip():
        debug_flag = not IS_PRODUCTION
    else:
        debug_flag = debug_env.strip().lower() in {'1', 'true', 'yes'}
    host = os.environ.get('HOST', '127.0.0.1' if IS_PRODUCTION else '0.0.0.0')
    port = int(os.environ.get('PORT', '5000'))
    app.run(debug=(debug_flag and not IS_PRODUCTION), host=host, port=port)
