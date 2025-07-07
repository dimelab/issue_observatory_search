from flask_login import UserMixin
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    scrapes = db.relationship('Scrape', backref='user', lazy=True)
    search_terms = db.relationship('SearchTerms', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.username}>'