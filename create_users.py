#!/usr/bin/env python3
"""
User Management Script for Scouts Website
Run this script to create additional admin users
"""

import json
import bcrypt
import os
from datetime import datetime

USERS_FILE = 'users.json'

def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

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

def create_admin_user(username, full_name, email, password):
    """Create a new admin user"""
    users = load_users()

    if username in users:
        print(f"❌ User '{username}' already exists!")
        return False

    users[username] = {
        'username': username,
        'password_hash': hash_password(password),
        'role': 'admin',
        'full_name': full_name,
        'email': email,
        'created_at': datetime.now().isoformat(),
        'is_active': True
    }

    save_users(users)
    print(f"✅ Admin user '{full_name}' created successfully!")
    print(f"   Username: {username}")
    print(f"   Password: {password}")
    return True

def create_regular_user(username, full_name, email, password):
    """Create a new regular user"""
    users = load_users()

    if username in users:
        print(f"❌ User '{username}' already exists!")
        return False

    users[username] = {
        'username': username,
        'password_hash': hash_password(password),
        'role': 'user',
        'full_name': full_name,
        'email': email,
        'created_at': datetime.now().isoformat(),
        'is_active': True
    }

    save_users(users)
    print(f"✅ Regular user '{full_name}' created successfully!")
    print(f"   Username: {username}")
    print(f"   Password: {password}")
    return True

def list_users():
    """List all users"""
    users = load_users()
    print("\n📋 Current Users:")
    print("-" * 50)
    for username, data in users.items():
        if data['is_active']:
            role = "👑 Admin" if data['role'] == 'admin' else "👤 User"
            print(f"{role} | {data['full_name']} (@{username}) | {data.get('email', 'No email')}")
    print()

if __name__ == "__main__":
    print("🏕️  Scouts Website - User Management")
    print("=" * 40)

    # Example: Create additional admin users
    print("\nCreating sample admin users...")

    # Create sample admin users
    create_admin_user('anwar_admin', 'أنور السدجات', 'anwar@scouts.ma', 'admin123')
    create_admin_user('adil_admin', 'عديل الشنوري', 'adil@scouts.ma', 'admin456')

    list_users()

    print("\n🎯 Login Instructions:")
    print("- Go to: http://127.0.0.1:5000/admin/login")
    print("- Use any of the created usernames and passwords above")
    print("- Admin users can manage both activities and users")
    print("- Regular users can only manage activities")