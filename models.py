from app import db  # Import db directly from your app module
from datetime import datetime

class Housing(db.Model):
    __tablename__ = 'housing'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    address = db.Column(db.String(200), nullable=False)
    image_filename = db.Column(db.String(200), nullable=True)
    image_url = db.Column(db.String(300), nullable=True)
    capacity = db.Column(db.Integer, default=0)
    hackathon_id = db.Column(db.Integer, db.ForeignKey('hackathon.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with Hackathon
    hackathon = db.relationship('Hackathon', backref=db.backref('housing_locations', lazy=True))
    
    def __repr__(self):
        return f'<Housing {self.name}>'