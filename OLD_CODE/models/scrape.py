from app import db
from datetime import datetime

class Scrape(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    search_engine = db.Column(db.String(50), nullable=False)
    max_results = db.Column(db.Integer, default=10)
    allowed_domains = db.Column(db.Text)
    scrape_depth = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    pages = db.relationship('ScrapedPage', backref='scrape', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Scrape {self.title}>'

class ScrapedPage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    scrape_id = db.Column(db.Integer, db.ForeignKey('scrape.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    domain = db.Column(db.String(200), nullable=False)
    title = db.Column(db.String(500))
    content = db.Column(db.Text)
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)
    depth_level = db.Column(db.Integer, default=1)
    
    def __repr__(self):
        return f'<ScrapedPage {self.url}>'