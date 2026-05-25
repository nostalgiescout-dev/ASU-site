# Scouts Only - Complete Platform Setup Guide

## Overview
This is a complete, production-ready web platform for the Scout Association called "Scouts Only". It features a modern, responsive public website and a comprehensive admin dashboard for managing all content.

## Features

### Public Website
- **Homepage**: Hero section, statistics, mission/vision, latest activities
- **Units Page**: Display scout units (Cubs, Scouts, Advanced, Rovers) with descriptions
- **Clubs Page**: Show various clubs and their activities
- **Activities Page**: Complete listing of all events and activities with pagination
- **Find Group**: Interactive map with Leaflet.js to find nearest scout groups
- **Multi-language Support**: Arabic, English, French, Spanish
- **Responsive Design**: Mobile-first approach with Tailwind CSS

### Admin Dashboard  
- **Secure Login**: Flask-Login with bcrypt password hashing
- **Units Management**: CRUD operations for scout units
- **Clubs Management**: Manage clubs and their activities
- **Activities Management**: Create and edit events with multimedia support
- **Groups Management**: Manage scout group locations with coordinates
- **Users Management**: Create and manage admin users
- **Settings**: Manage homepage content

### Technical Stack
- **Backend**: Python Flask 2.3.3
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: HTML5, Tailwind CSS, JavaScript
- **Authentication**: Flask-Login + bcrypt
- **Internationalization**: Flask-Babel
- **Map**: Leaflet.js

## Installation & Setup

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Virtual environment (venv)

### Step 1: Create Virtual Environment
```bash
cd "C:\Users\HP\Desktop\Nouveau dossier\ASU\ASU-siteweb"
python -m venv .venv
.venv\Scripts\activate
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Initialize Database
```bash
python app.py
```

This will:
- Create the SQLite database (`scouts_only.db`)
- Create all tables
- Insert sample data
- Create default admin user (username: `admin`, password: `scouts2024`)

### Step 4: Run the Application
```bash
python app.py
```

The application will start at `http://localhost:5000`

## Accessing the Platform

### Public Website
- **Homepage**: http://localhost:5000/
- **Units**: http://localhost:5000/units
- **Clubs**: http://localhost:5000/clubs
- **Activities**: http://localhost:5000/activities
- **Find Group**: http://localhost:5000/find-group
- **About**: http://localhost:5000/about

### Admin Dashboard
- **Login**: http://localhost:5000/admin/login
- **Dashboard**: http://localhost:5000/admin
- **Manage Units**: http://localhost:5000/admin/units
- **Manage Clubs**: http://localhost:5000/admin/clubs
- **Manage Activities**: http://localhost:5000/admin/activities
- **Manage Groups**: http://localhost:5000/admin/groups
- **Manage Users**: http://localhost:5000/admin/users
- **Settings**: http://localhost:5000/admin/settings

### Default Credentials
- **Username**: admin
- **Password**: scouts2024

⚠️ **IMPORTANT**: Change this password immediately in production!

## Project Structure
```
ASU-siteweb/
├── app.py                 # Main Flask application with all routes
├── models.py              # SQLAlchemy database models
├── requirements.txt       # Python dependencies
├── scouts_only.db         # SQLite database (auto-created)
├── uploads/               # User-uploaded files
│   ├── images/
│   └── videos/
├── static/
│   ├── css/
│   │   └── styles.css    # Tailwind CSS custom styles
│   ├── js/
│   │   └── main.js       # JavaScript functionality
│   └── images/
└── templates/
    ├── base.html          # Base layout template
    ├── index.html         # Homepage
    ├── units.html         # Units page
    ├── clubs.html         # Clubs page
    ├── activities.html    # Activities page
    ├── find_group.html    # Map/find group page
    ├── about.html         # About page
    ├── admin/
    │   ├── login.html
    │   ├── dashboard.html
    │   ├── units.html
    │   ├── unit_form.html
    │   ├── clubs.html
    │   ├── club_form.html
    │   ├── activities.html
    │   ├── activity_form.html
    │   ├── groups.html
    │   ├── group_form.html
    │   ├── users.html
    │   ├── user_form.html
    │   └── settings.html
    └── errors/
        ├── 403.html
        ├── 404.html
        └── 500.html
```

## Database Models

### User
- `username`: Unique user identifier
- `email`: Email address
- `password_hash`: Bcrypt hashed password
- `full_name`: User's full name
- `role`: admin/editor/viewer
- `is_active`: Account status

### Unit
- `name_ar/en/fr/es`: Multi-language names
- `description_ar/en/fr/es`: Multi-language descriptions
- `age_range`: Age range (e.g., "7-10")
- `icon`: Material icon name
- `image_url`: Unit image
- `order`: Display order

### Club
- `name_ar/en/fr/es`: Multi-language names
- `description_ar/en/fr/es`: Multi-language descriptions
- `icon`: Material icon name
- `image_url`: Club image
- `order`: Display order

### Activity
- `title_ar/en/fr/es`: Multi-language titles
- `description_ar/en/fr/es`: Multi-language descriptions
- `date`: Event date and time
- `location_ar/en`: Multi-language location
- `image_url`: Event image
- `video_url`: YouTube embed URL
- `club_id`: Associated club
- `status`: upcoming/ongoing/completed
- `views`: View count

### Group
- `name`: Group name
- `city_ar/en`: Multi-language city name
- `latitude/longitude`: GPS coordinates
- `address`: Physical address
- `phone`: Contact phone
- `email`: Contact email
- `leader_name`: Group leader
- `leader_phone`: Leader's phone
- `members_count`: Number of members
- `units_active`: Active unit types

### HomePage
- `hero_title_ar/en`: Hero section title
- `hero_description_ar/en`: Hero description
- `hero_image`: Hero background image
- `mission_ar/en`: Mission statement
- `vision_ar/en`: Vision statement
- `total_members/units/groups`: Statistics
- `established_year`: Founding year

## API Endpoints

### Public APIs
- `GET /api/groups` - Get all scout groups as JSON
- `GET /api/groups/nearby?lat=X&lon=Y&radius=50` - Find groups near location
- `GET /set-lang/<lang>` - Set language preference

### Admin APIs
- Unit CRUD: POST/GET/PUT/DELETE `/admin/units`
- Club CRUD: POST/GET/PUT/DELETE `/admin/clubs`
- Activity CRUD: POST/GET/PUT/DELETE `/admin/activities`
- Group CRUD: POST/GET/PUT/DELETE `/admin/groups`
- User CRUD: POST/GET/PUT/DELETE `/admin/users`

## Configuration

### Environment Variables
Create a `.env` file:
```env
FLASK_ENV=production
SECRET_KEY=your-secret-key-here
SQLALCHEMY_DATABASE_URI=sqlite:///scouts_only.db
```

### Language Support
Supported languages in templates:
- Arabic (ar)
- English (en)
- French (fr)
- Spanish (es)

Set language preference at: `/set-lang/<lang>`

## Customization

### Adding New Language
1. Update `app.config['BABEL_SUPPORTED_LOCALES']`
2. Add translation fields to all models
3. Update templates to include new language

### Styling
- Main styles: `static/css/styles.css`
- Uses Tailwind CSS utilities
- Customizable Tailwind config in base.html

### Adding New Admin Page
1. Create model in `models.py`
2. Add routes in `app.py`
3. Create templates in `templates/admin/`
4. Add navigation link in `base.html`

## File Upload

Uploaded files are stored in the `uploads/` directory. Supported formats:
- Images: PNG, JPG, JPEG, GIF, WebP
- Videos: MP4, WebM
- Maximum file size: 50MB

### Upload Paths
- Unit images: `/uploads/unit_*`
- Club images: `/uploads/club_*`
- Activity images: `/uploads/activity_*`
- Hero image: `/uploads/hero_*`

## Security Considerations

✅ **Implemented:**
- Password hashing with bcrypt
- Login required decorators
- Admin role verification
- Session management with Flask-Login
- CSRF protection (Jinja2 templates)
- Secure file upload validation

⚠️ **For Production:**
1. Change `SECRET_KEY` to a strong random string
2. Set `FLASK_ENV=production`
3. Use a production database (PostgreSQL recommended)
4. Enable HTTPS/SSL
5. Implement rate limiting
6. Add logging and monitoring
7. Regular security audits
8. Keep dependencies updated

## Deployment Options

### Option 1: Heroku
1. Create `Procfile`:
   ```
   web: gunicorn app:app
   ```
2. Create `runtime.txt`: `python-3.11.5`
3. Add `gunicorn` to requirements.txt
4. Deploy: `git push heroku main`

### Option 2: AWS/Azure/GCP
1. Use managed Flask hosting
2. Configure PostgreSQL database
3. Set up environment variables
4. Configure CloudFront for static files

### Option 3: Docker
Create `Dockerfile`:
```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app:app"]
```

### Option 4: Traditional Server
1. Install Python 3.8+
2. Clone repository
3. Create virtual environment
4. Install dependencies
5. Use Gunicorn + Nginx
6. Configure systemd service

## Troubleshooting

### Database Issues
```bash
# Reset database
rm scouts_only.db
python app.py
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Template Not Found
- Ensure templates are in `/templates` directory
- Check file naming (lowercase)
- Verify file path in `render_template()`

### Static Files Not Loading
- Check `static/` directory structure
- Verify `url_for()` function usage
- Clear browser cache

## Support & Contributing

For issues, feature requests, or contributions:
1. Report bugs with detailed description
2. Include error logs
3. Suggest features with use cases
4. Follow code style guidelines

## License

This platform is developed for Scouts Only Association. All rights reserved.

## Contact

**Scouts Only Association**
- Email: info@scouts-only.org
- Phone: +212 XXX XXX XXX
- Website: scouts-only.org

---

**Last Updated**: April 2024
**Version**: 1.0.0
**Status**: Production Ready ✅
