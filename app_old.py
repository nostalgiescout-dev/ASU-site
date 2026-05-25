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

# Create app
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-2024-scouts-only')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scouts_only.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Babel configuration for internationalization
app.config['BABEL_DEFAULT_LOCALE'] = 'ar'
app.config['BABEL_SUPPORTED_LOCALES'] = ['ar', 'en', 'fr', 'es']

def get_locale():
    # Check if language is set in session, otherwise use browser preference
    lang = session.get('lang')
    if lang and lang in app.config['BABEL_SUPPORTED_LOCALES']:
        return lang
    return request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])

# Context processor to inject get_locale into Jinja2 templates
@app.context_processor
def inject_locale():
    return dict(get_locale=get_locale, current_lang=get_locale())

babel = Babel(app, locale_selector=get_locale)

@app.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in app.config['BABEL_SUPPORTED_LOCALES']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('home'))

# File to store users (in production, use a proper database)
USERS_FILE = 'users.json'

# Simple in-memory storage for activities (in production, use a database)
activities = [
    {"id": 1, "title": "رحلة تسلق الجبال", "description": "مغامرة مثيرة في جبال الأطلس", "date": "2024-06-15"},
    {"id": 2, "title": "دورة الإسعافات الأولية", "description": "تعلم المهارات الأساسية للإسعاف", "date": "2024-06-20"},
    {"id": 3, "title": "مخيم الصيف", "description": "أسبوع كامل من الأنشطة والمغامرات", "date": "2024-07-01"}
]

def load_users():
    """Load users from JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_users(users):
    """Save users to JSON file"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def check_password(password, hashed):
    """Check if password matches hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_default_admin():
    """Create default admin user if no users exist"""
    users = load_users()
    if not users:
        users['admin'] = {
            'username': 'admin',
            'password_hash': hash_password('scouts2024'),
            'role': 'admin',
            'full_name': 'مدير النظام',
            'email': 'admin@scouts.ma',
            'created_at': datetime.now().isoformat(),
            'is_active': True
        }
        save_users(users)
        print("✅ Default admin user created: admin / scouts2024")
    return users

# Initialize users
users_db = create_default_admin()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_logged_in' not in session:
            return redirect(url_for('admin_login'))
        username = session.get('username')
        users = load_users()
        if username not in users or users[username]['role'] != 'admin':
            flash('غير مصرح لك بالوصول إلى هذه الصفحة')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def home():
    return render_template('index.html', activities=activities, lang=get_locale())

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        users = load_users()
        if username in users and users[username]['is_active'] and check_password(password, users[username]['password_hash']):
            session['user_logged_in'] = True
            session['username'] = username
            session['user_role'] = users[username]['role']
            session['full_name'] = users[username]['full_name']
            return redirect(url_for('admin'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة')

    login_html = """
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="utf-8" />
        <meta content="width=device-width, initial-scale=1.0" name="viewport" />
        <title>تسجيل الدخول - جمعية كشافة فقط</title>
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
    </head>
    <body class="bg-gradient-to-br from-blue-50 to-indigo-100 min-h-screen flex items-center justify-center" style="font-family: 'Cairo', sans-serif;">
        <div class="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
            <div class="text-center mb-8">
                <div class="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center text-primary mx-auto mb-4">
                    <span class="material-symbols-outlined text-3xl">admin_panel_settings</span>
                </div>
                <h1 class="text-2xl font-black text-gray-800">تسجيل الدخول للإدارة</h1>
                <p class="text-gray-600 mt-2">جمعية كشافة فقط</p>
            </div>

            <form method="POST" class="space-y-6">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">اسم المستخدم</label>
                    <input type="text" name="username" required
                           class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-2">كلمة المرور</label>
                    <input type="password" name="password" required
                           class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all">
                </div>
                <button type="submit"
                        class="w-full bg-primary text-on-primary py-3 px-4 rounded-lg font-bold hover:bg-primary/90 transition-all duration-200 transform hover:scale-105">
                    تسجيل الدخول
                </button>
            </form>

            <div class="mt-6 text-center">
                <a href="/" class="text-primary hover:text-primary/80 text-sm font-medium transition-colors">
                    العودة للموقع الرئيسي
                </a>
            </div>
        </div>
    </body>
    </html>
    """
    return login_html

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/admin')
@admin_required
def admin():
    users = load_users()
    total_users = len([u for u in users.values() if u['is_active']])

    admin_html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="utf-8" />
        <meta content="width=device-width, initial-scale=1.0" name="viewport" />
        <title>إدارة الأنشطة - جمعية كشافة فقط</title>
        <script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;900&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
    </head>
    <body class="bg-gray-50" style="font-family: 'Cairo', sans-serif;">
        <div class="max-w-6xl mx-auto p-6">
            <div class="flex justify-between items-center mb-8">
                <div>
                    <h1 class="text-3xl font-black text-gray-800">لوحة التحكم الإدارية</h1>
                    <p class="text-gray-600 mt-1">مرحباً بك، {session.get('full_name', 'المستخدم')}</p>
                </div>
                <div class="flex gap-4">
                    <a href="/" class="bg-gray-600 text-white px-4 py-2 rounded-lg hover:bg-gray-700 transition-colors">
                        العودة للموقع
                    </a>
                    <a href="/admin/logout" class="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors">
                        تسجيل الخروج
                    </a>
                </div>
            </div>

            <!-- Stats Cards -->
            <div class="grid md:grid-cols-3 gap-6 mb-8">
                <div class="bg-white rounded-lg shadow-md p-6">
                    <div class="flex items-center">
                        <div class="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-600">
                            <span class="material-symbols-outlined">event</span>
                        </div>
                        <div class="mr-4">
                            <p class="text-2xl font-bold text-gray-800">{len(activities)}</p>
                            <p class="text-gray-600">الأنشطة</p>
                        </div>
                    </div>
                </div>
                <div class="bg-white rounded-lg shadow-md p-6">
                    <div class="flex items-center">
                        <div class="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center text-green-600">
                            <span class="material-symbols-outlined">group</span>
                        </div>
                        <div class="mr-4">
                            <p class="text-2xl font-bold text-gray-800">{total_users}</p>
                            <p class="text-gray-600">المستخدمين</p>
                        </div>
                    </div>
                </div>
                <div class="bg-white rounded-lg shadow-md p-6">
                    <div class="flex items-center">
                        <div class="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center text-purple-600">
                            <span class="material-symbols-outlined">admin_panel_settings</span>
                        </div>
                        <div class="mr-4">
                            <p class="text-2xl font-bold text-gray-800">{len([u for u in users.values() if u.get('role') == 'admin' and u['is_active']])}</p>
                            <p class="text-gray-600">المشرفين</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Navigation Tabs -->
            <div class="bg-white rounded-lg shadow-md mb-8">
                <div class="border-b border-gray-200">
                    <nav class="flex">
                        <button onclick="showTab('activities')" class="tab-button active px-6 py-4 text-gray-700 font-medium border-b-2 border-primary">
                            إدارة الأنشطة
                        </button>
                        <button onclick="showTab('users')" class="tab-button px-6 py-4 text-gray-500 font-medium hover:text-gray-700">
                            إدارة المستخدمين
                        </button>
                    </nav>
                </div>

                <!-- Activities Tab -->
                <div id="activities-tab" class="tab-content p-6">
                    <div class="flex justify-between items-center mb-6">
                        <h2 class="text-xl font-bold">الأنشطة</h2>
                        <button onclick="showAddActivityModal()" class="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors">
                            إضافة نشاط جديد
                        </button>
                    </div>

                    <div class="space-y-4">
    """
    for activity in activities:
        admin_html += f"""
                        <div class="border border-gray-200 rounded-lg p-4 flex justify-between items-center">
                            <div>
                                <h3 class="font-bold text-lg">{activity['title']}</h3>
                                <p class="text-gray-600">{activity['description']}</p>
                                <p class="text-sm text-gray-500">التاريخ: {activity['date']}</p>
                            </div>
                            <div class="flex gap-2">
                                <button onclick="editActivity({activity['id']})" class="bg-yellow-600 text-white px-3 py-1 rounded hover:bg-yellow-700 transition-colors text-sm">
                                    تعديل
                                </button>
                                <a href="/admin/delete/{activity['id']}" class="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 transition-colors text-sm" onclick="return confirm('هل أنت متأكد من حذف هذا النشاط؟')">
                                    حذف
                                </a>
                            </div>
                        </div>
        """
    admin_html += """
                    </div>
                </div>

                <!-- Users Tab -->
                <div id="users-tab" class="tab-content p-6 hidden">
                    <div class="flex justify-between items-center mb-6">
                        <h2 class="text-xl font-bold">المستخدمين</h2>
                        <button onclick="showAddUserModal()" class="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 transition-colors">
                            إضافة مستخدم جديد
                        </button>
                    </div>

                    <div class="space-y-4">
    """
    for username, user_data in users.items():
        if user_data['is_active']:
            role_color = 'bg-purple-100 text-purple-800' if user_data['role'] == 'admin' else 'bg-blue-100 text-blue-800'
            admin_html += f"""
                        <div class="border border-gray-200 rounded-lg p-4 flex justify-between items-center">
                            <div>
                                <h3 class="font-bold text-lg">{user_data['full_name']}</h3>
                                <p class="text-gray-600">@{username}</p>
                                <p class="text-sm text-gray-500">{user_data.get('email', 'لا يوجد بريد إلكتروني')}</p>
                                <span class="inline-block px-2 py-1 text-xs rounded-full {role_color} mt-1">
                                    {user_data['role']}
                                </span>
                            </div>
                            <div class="flex gap-2">
                                <button onclick="editUser('{username}')" class="bg-yellow-600 text-white px-3 py-1 rounded hover:bg-yellow-700 transition-colors text-sm">
                                    تعديل
                                </button>
                                <a href="/admin/user/delete/{username}" class="bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 transition-colors text-sm" onclick="return confirm('هل أنت متأكد من حذف هذا المستخدم؟')">
                                    حذف
                                </a>
                            </div>
                        </div>
        """
    admin_html += """
                    </div>
                </div>
            </div>
        </div>

        <!-- Add Activity Modal -->
        <div id="addActivityModal" class="fixed inset-0 bg-black bg-opacity-50 hidden flex items-center justify-center z-50">
            <div class="bg-white rounded-lg p-6 w-full max-w-md mx-4">
                <h3 class="text-lg font-bold mb-4">إضافة نشاط جديد</h3>
                <form method="POST" action="/admin/add">
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">عنوان النشاط</label>
                            <input type="text" name="title" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">وصف النشاط</label>
                            <textarea name="description" rows="3" required class="w-full px-3 py-2 border border-gray-300 rounded-md"></textarea>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">تاريخ النشاط</label>
                            <input type="date" name="date" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                    </div>
                    <div class="flex gap-2 mt-6">
                        <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">إضافة</button>
                        <button type="button" onclick="hideAddActivityModal()" class="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700">إلغاء</button>
                    </div>
                </form>
            </div>
        </div>

        <!-- Add User Modal -->
        <div id="addUserModal" class="fixed inset-0 bg-black bg-opacity-50 hidden flex items-center justify-center z-50">
            <div class="bg-white rounded-lg p-6 w-full max-w-md mx-4">
                <h3 class="text-lg font-bold mb-4">إضافة مستخدم جديد</h3>
                <form method="POST" action="/admin/user/create">
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">اسم المستخدم</label>
                            <input type="text" name="username" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">الاسم الكامل</label>
                            <input type="text" name="full_name" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">البريد الإلكتروني</label>
                            <input type="email" name="email" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">كلمة المرور</label>
                            <input type="password" name="password" required class="w-full px-3 py-2 border border-gray-300 rounded-md">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">الدور</label>
                            <select name="role" class="w-full px-3 py-2 border border-gray-300 rounded-md">
                                <option value="user">مستخدم</option>
                                <option value="admin">مشرف</option>
                            </select>
                        </div>
                    </div>
                    <div class="flex gap-2 mt-6">
                        <button type="submit" class="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700">إضافة</button>
                        <button type="button" onclick="hideAddUserModal()" class="bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700">إلغاء</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
            function showTab(tabName) {
                document.querySelectorAll('.tab-content').forEach(tab => tab.classList.add('hidden'));
                document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active', 'border-primary'));
                document.getElementById(tabName + '-tab').classList.remove('hidden');
                event.target.classList.add('active', 'border-primary');
            }

            function showAddActivityModal() {
                document.getElementById('addActivityModal').classList.remove('hidden');
            }

            function hideAddActivityModal() {
                document.getElementById('addActivityModal').classList.add('hidden');
            }

            function showAddUserModal() {
                document.getElementById('addUserModal').classList.remove('hidden');
            }

            function hideAddUserModal() {
                document.getElementById('addUserModal').classList.add('hidden');
            }

            function editActivity(id) {
                alert('تعديل النشاط قيد التطوير');
            }

            function editUser(username) {
                alert('تعديل المستخدم قيد التطوير');
            }
        </script>
    </body>
    </html>
    """
    return admin_html

@app.route('/admin/add', methods=['POST'])
@admin_required
def add_activity():
    title = request.form.get('title')
    description = request.form.get('description')
    date = request.form.get('date')

    if title and description and date:
        new_id = max([a['id'] for a in activities], default=0) + 1
        activities.append({
            "id": new_id,
            "title": title,
            "description": description,
            "date": date
        })

    return redirect(url_for('admin'))

@app.route('/admin/delete/<int:activity_id>')
@admin_required
def delete_activity(activity_id):
    global activities
    activities = [a for a in activities if a['id'] != activity_id]
    return redirect(url_for('admin'))

@app.route('/admin/user/create', methods=['POST'])
@admin_required
def create_user():
    username = request.form.get('username')
    full_name = request.form.get('full_name')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'user')

    if not username or not full_name or not password:
        flash('يرجى ملء جميع الحقول المطلوبة')
        return redirect(url_for('admin'))

    users = load_users()
    if username in users:
        flash('اسم المستخدم موجود بالفعل')
        return redirect(url_for('admin'))

    users[username] = {
        'username': username,
        'password_hash': hash_password(password),
        'role': role,
        'full_name': full_name,
        'email': email or '',
        'created_at': datetime.now().isoformat(),
        'is_active': True
    }
    save_users(users)

    flash(f'تم إنشاء المستخدم {full_name} بنجاح')
    return redirect(url_for('admin'))

@app.route('/admin/user/delete/<username>')
@admin_required
def delete_user(username):
    if username == session.get('username'):
        flash('لا يمكنك حذف حسابك الخاص')
        return redirect(url_for('admin'))

    users = load_users()
    if username in users:
        users[username]['is_active'] = False
        save_users(users)
        flash('تم حذف المستخدم بنجاح')

    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
