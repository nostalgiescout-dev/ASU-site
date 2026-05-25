"""
Scouts Only - Complete web platform for Scout Association
Main Flask application with routes for public website and admin dashboard
"""

import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for, 
    session, flash, jsonify, abort, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import Babel, gettext as _
from models import db, User, Unit, Club, Activity, Group, HomePage

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

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
    return {
        'get_locale': get_locale,
        'translate_field': get_translated_field,
        'current_lang': get_locale(),
        'supported_langs': app.config['BABEL_SUPPORTED_LOCALES']
    }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    activities = Activity.query.order_by(Activity.date.desc()).all()

    return render_template(
        'home.html',
        units=units,
        clubs=clubs,
        activities=activities,
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
    activities = Activity.query.filter_by(club_id=club_id).order_by(Activity.date.desc()).all()
    return render_template('club_detail.html', club=club, activities=activities)

@app.route('/activities')
def activities():
    """Display all activities/events"""
    page = request.args.get('page', 1, type=int)
    activities = Activity.query.order_by(Activity.date.desc()).paginate(page=page, per_page=12)
    return render_template('activities.html', activities=activities)

@app.route('/activity/<activity_id>')
def activity_detail(activity_id):
    """Display single activity details"""
    activity = Activity.query.get_or_404(activity_id)
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
    """List all activities"""
    activities = Activity.query.order_by(Activity.date.desc()).all()
    return render_template('admin/activities.html', activities=activities)

@app.route('/admin/activities/create', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_create_activity():
    """Create new activity"""
    clubs = Club.query.all()
    
    if request.method == 'POST':
        try:
            activity = Activity(
                title_ar=request.form.get('title_ar'),
                title_en=request.form.get('title_en'),
                title_fr=request.form.get('title_fr'),
                title_es=request.form.get('title_es'),
                description_ar=request.form.get('description_ar'),
                description_en=request.form.get('description_en'),
                description_fr=request.form.get('description_fr'),
                description_es=request.form.get('description_es'),
                date=datetime.fromisoformat(request.form.get('date')),
                location_ar=request.form.get('location_ar'),
                location_en=request.form.get('location_en'),
                video_url=request.form.get('video_url'),
                club_id=request.form.get('club_id') or None,
                status=request.form.get('status', 'upcoming')
            )
            
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"activity_{activity.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    activity.image_url = f"/uploads/{filename}"
            
            db.session.add(activity)
            db.session.commit()
            flash('تم إنشاء النشاط بنجاح', 'success')
            return redirect(url_for('admin_activities'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/activity_form.html', clubs=clubs)

@app.route('/admin/activities/<activity_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_activity(activity_id):
    """Edit activity"""
    activity = Activity.query.get_or_404(activity_id)
    clubs = Club.query.all()
    
    if request.method == 'POST':
        try:
            activity.title_ar = request.form.get('title_ar')
            activity.title_en = request.form.get('title_en')
            activity.title_fr = request.form.get('title_fr')
            activity.title_es = request.form.get('title_es')
            activity.description_ar = request.form.get('description_ar')
            activity.description_en = request.form.get('description_en')
            activity.description_fr = request.form.get('description_fr')
            activity.description_es = request.form.get('description_es')
            activity.date = datetime.fromisoformat(request.form.get('date'))
            activity.location_ar = request.form.get('location_ar')
            activity.location_en = request.form.get('location_en')
            activity.video_url = request.form.get('video_url')
            activity.club_id = request.form.get('club_id') or None
            activity.status = request.form.get('status', 'upcoming')
            
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"activity_{activity.id}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    activity.image_url = f"/uploads/{filename}"
            
            db.session.commit()
            flash('تم تحديث النشاط بنجاح', 'success')
            return redirect(url_for('admin_activities'))
        except Exception as e:
            db.session.rollback()
            flash(f'خطأ: {str(e)}', 'error')
    
    return render_template('admin/activity_form.html', activity=activity, clubs=clubs)

@app.route('/admin/activities/<activity_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_activity(activity_id):
    """Delete activity"""
    activity = Activity.query.get_or_404(activity_id)
    db.session.delete(activity)
    db.session.commit()
    flash('تم حذف النشاط بنجاح', 'success')
    return redirect(url_for('admin_activities'))

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
