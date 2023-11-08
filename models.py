from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    verified = db.Column(db.Integer, default=0)
    password = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.Integer, nullable=True)
    img = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    verifications = db.relationship('Verification', backref="user", cascade='all, delete-orphan')
    properties = db.relationship('Property', backref="user", cascade='all, delete-orphan')
    messages = db.relationship('Message', backref="user", cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref="user", cascade='all, delete-orphan')

    def __init__(self,**kwargs):
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return 'User>>> {self.email}'
    
class Verification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    code = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    expiration = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self) -> str:
        return 'User>>> {self.code}'

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False) 
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(255), nullable=True)
    approved = db.Column(db.Integer, default=0)
    location = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    reviews = db.relationship('Review', backref="property", cascade='all, delete-orphan')
    files = db.relationship('File', backref="property", cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return 'Property>>> {self.title}'
    
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self) -> str:
        return 'Property>>> {self.name}'
    
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    body = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    mfiles = db.relationship('Mfile', backref="message", cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return 'Message>>> {self.body}'
    
class Mfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.Text, unique=True, nullable=False)
    type = db.Column(db.Text, nullable=False)
    size = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self) -> str:
        return 'Review>>> {self.name}'
    
class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'), nullable=False) 
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.String(255), default="")
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.Integer, nullable=True)
    website = db.Column(db.String(255), default="")
    img = db.Column(db.String(255), default="")
    manager = db.Column(db.String(255), default="")
    location = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(255), nullable=False)
    qrcode = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    reviews = db.relationship('Review', backref="branch", cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return 'Branch>>> {self.name}'
    

    
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    branch_id = db.Column(db.Integer, db.ForeignKey('branch.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)  
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, default="")
    rating = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    files = db.relationship('File', backref="review", cascade='all, delete-orphan')

    def __repr__(self) -> str:
        return 'Review>>> {self.title}'
    
class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.Text, unique=True, nullable=False)
    type = db.Column(db.Text, nullable=False)
    ceo = db.Column(db.String(255), default="")
    size = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self) -> str:
        return 'File>>> {self.name}'