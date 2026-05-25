"""
Database models for Scouts Only platform
Using SQLAlchemy ORM with SQLite backend
"""

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import bcrypt
import uuid

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='editor')  # admin, editor, viewer
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
    
    def check_password(self, password):
        """Verify password against hash"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )

    def get_id(self):
        """Flask-Login expects the user ID as a string."""
        return str(self.id)
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat()
        }

class Unit(db.Model):
    """Scout unit model (Cubs, Scouts, Advanced, Rovers)"""
    __tablename__ = 'units'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name_ar = db.Column(db.String(120), nullable=False)
    name_en = db.Column(db.String(120), nullable=False)
    name_fr = db.Column(db.String(120), nullable=False)
    name_es = db.Column(db.String(120), nullable=False)
    
    description_ar = db.Column(db.Text, nullable=False)
    description_en = db.Column(db.Text, nullable=False)
    description_fr = db.Column(db.Text, nullable=False)
    description_es = db.Column(db.Text, nullable=False)
    
    age_range = db.Column(db.String(50), nullable=False)  # e.g., "7-10"
    icon = db.Column(db.String(50), default='scout')
    image_url = db.Column(db.String(255))
    order = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': {
                'ar': self.name_ar,
                'en': self.name_en,
                'fr': self.name_fr,
                'es': self.name_es
            },
            'description': {
                'ar': self.description_ar,
                'en': self.description_en,
                'fr': self.description_fr,
                'es': self.description_es
            },
            'age_range': self.age_range,
            'icon': self.icon,
            'image_url': self.image_url
        }

class Club(db.Model):
    """Scout club model (Media, Environment, Sports, etc.)"""
    __tablename__ = 'clubs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name_ar = db.Column(db.String(120), nullable=False)
    name_en = db.Column(db.String(120), nullable=False)
    name_fr = db.Column(db.String(120), nullable=False)
    name_es = db.Column(db.String(120), nullable=False)
    
    description_ar = db.Column(db.Text, nullable=False)
    description_en = db.Column(db.Text, nullable=False)
    description_fr = db.Column(db.Text, nullable=False)
    description_es = db.Column(db.Text, nullable=False)
    
    icon = db.Column(db.String(50), default='palette')
    image_url = db.Column(db.String(255))
    order = db.Column(db.Integer, default=0)
    
    activities = db.relationship('Activity', backref='club', lazy=True, cascade='all, delete-orphan')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': {
                'ar': self.name_ar,
                'en': self.name_en,
                'fr': self.name_fr,
                'es': self.name_es
            },
            'description': {
                'ar': self.description_ar,
                'en': self.description_en,
                'fr': self.description_fr,
                'es': self.description_es
            },
            'icon': self.icon,
            'image_url': self.image_url,
            'activity_count': len(self.activities)
        }

class Activity(db.Model):
    """Activity/Event model"""
    __tablename__ = 'activities'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title_ar = db.Column(db.String(200), nullable=False)
    title_en = db.Column(db.String(200), nullable=False)
    title_fr = db.Column(db.String(200), nullable=False)
    title_es = db.Column(db.String(200), nullable=False)
    
    description_ar = db.Column(db.Text, nullable=False)
    description_en = db.Column(db.Text, nullable=False)
    description_fr = db.Column(db.Text, nullable=False)
    description_es = db.Column(db.Text, nullable=False)
    
    date = db.Column(db.DateTime, nullable=False)
    location_ar = db.Column(db.String(200))
    location_en = db.Column(db.String(200))
    
    image_url = db.Column(db.String(255))
    video_url = db.Column(db.String(255))  # YouTube or other video embed
    
    club_id = db.Column(db.String(36), db.ForeignKey('clubs.id'), nullable=True)
    
    status = db.Column(db.String(20), default='upcoming')  # upcoming, ongoing, completed
    views = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': {
                'ar': self.title_ar,
                'en': self.title_en,
                'fr': self.title_fr,
                'es': self.title_es
            },
            'description': {
                'ar': self.description_ar,
                'en': self.description_en,
                'fr': self.description_fr,
                'es': self.description_es
            },
            'date': self.date.isoformat(),
            'location': {
                'ar': self.location_ar,
                'en': self.location_en
            },
            'image_url': self.image_url,
            'video_url': self.video_url,
            'status': self.status,
            'views': self.views
        }

class Group(db.Model):
    """Scout group location model"""
    __tablename__ = 'groups'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(120), nullable=False)
    city_ar = db.Column(db.String(100), nullable=False)
    city_en = db.Column(db.String(100), nullable=False)
    
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    
    leader_name = db.Column(db.String(120))
    leader_phone = db.Column(db.String(20))
    
    members_count = db.Column(db.Integer, default=0)
    units_active = db.Column(db.String(200))  # CSV of unit types
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'city': {
                'ar': self.city_ar,
                'en': self.city_en
            },
            'latitude': self.latitude,
            'longitude': self.longitude,
            'address': self.address,
            'phone': self.phone,
            'email': self.email,
            'leader_name': self.leader_name,
            'leader_phone': self.leader_phone,
            'members_count': self.members_count,
            'units_active': self.units_active
        }

class HomePage(db.Model):
    """Homepage content model"""
    __tablename__ = 'home_pages'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    hero_title_ar = db.Column(db.String(200))
    hero_title_en = db.Column(db.String(200))
    hero_description_ar = db.Column(db.Text)
    hero_description_en = db.Column(db.Text)
    hero_image = db.Column(db.String(255))
    
    mission_ar = db.Column(db.Text)
    mission_en = db.Column(db.Text)
    vision_ar = db.Column(db.Text)
    vision_en = db.Column(db.Text)
    
    total_members = db.Column(db.Integer, default=0)
    total_units = db.Column(db.Integer, default=0)
    total_groups = db.Column(db.Integer, default=0)
    established_year = db.Column(db.Integer, default=2000)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'hero': {
                'title': {'ar': self.hero_title_ar, 'en': self.hero_title_en},
                'description': {'ar': self.hero_description_ar, 'en': self.hero_description_en},
                'image': self.hero_image
            },
            'mission': {'ar': self.mission_ar, 'en': self.mission_en},
            'vision': {'ar': self.vision_ar, 'en': self.vision_en},
            'statistics': {
                'total_members': self.total_members,
                'total_units': self.total_units,
                'total_groups': self.total_groups,
                'established_year': self.established_year
            }
        }
