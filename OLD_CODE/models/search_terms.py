from app import db
from datetime import datetime

class SearchTerms(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    terms = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SearchTerms {self.name}>'
    
    def get_terms_list(self):
        return [term.strip() for term in self.terms.split(',') if term.strip()]