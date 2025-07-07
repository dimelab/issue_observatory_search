#!/usr/bin/env python3
"""
Script to create users for the Issue Observatory Search application.
Since user creation via frontend is not implemented, this script allows
backend admins to create users manually.
"""

import sys
from werkzeug.security import generate_password_hash
from app import create_app, db
from app.models import User

def create_user(username, email, password):
    """Create a new user"""
    app = create_app()
    
    with app.app_context():
        # Check if user already exists
        if User.query.filter_by(username=username).first():
            print(f"Error: User '{username}' already exists!")
            return False
        
        if User.query.filter_by(email=email).first():
            print(f"Error: Email '{email}' already exists!")
            return False
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password)
        )
        
        db.session.add(user)
        db.session.commit()
        
        print(f"User '{username}' created successfully!")
        return True

def main():
    if len(sys.argv) != 4:
        print("Usage: python create_user.py <username> <email> <password>")
        sys.exit(1)
    
    username = sys.argv[1]
    email = sys.argv[2]
    password = sys.argv[3]
    
    create_user(username, email, password)

if __name__ == '__main__':
    main()