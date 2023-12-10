from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    action_user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    target_id = db.Column(db.Integer, nullable=True)
    type = db.Column(db.String(255), nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self) -> str:
        return f'Notification ID: {self.id} - Type: {self.type}'
    
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    phone_number = db.Column(db.Integer, nullable=True)
    profile_picture = db.Column(db.String(255), default="default_profile.png")
    email_verified = db.Column(db.Integer, default=0)
    phone_number_verified = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    verifications = db.relationship('Verification', backref="user", cascade='all, delete-orphan')
    properties = db.relationship('Property', backref="user", cascade='all, delete-orphan')
    requests = db.relationship('Request', backref="user", cascade='all, delete-orphan')
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    messages_received = db.relationship('Message', foreign_keys='Message.receiver_id', backref='receiver', lazy='dynamic')
    reviews = db.relationship('Review', backref="user", cascade='all, delete-orphan')
    notifications_sent = db.relationship('Notification', backref='action_user', foreign_keys=[Notification.action_user_id])
    notifications_received = db.relationship('Notification', backref='user', foreign_keys=[Notification.user_id], cascade='all, delete-orphan')
    favorites = db.relationship('Favorite', backref='user', cascade='all, delete-orphan')

    def __repr__(self):
        return f'User ID: {self.id} - Username: {self.username}'


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('request.id', ondelete='CASCADE'), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=True)
    body = db.Column(db.Text, nullable=False)
    read = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Message ID: {self.id} - Sender: {self.sender_id} - Receiver: {self.receiver_id}'


class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    property_type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    area = db.Column(db.Float, nullable=True)  # Total area in square meters
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String(255), nullable=False) 
    city = db.Column(db.String(255), nullable=False) 
    state = db.Column(db.String(255), nullable=False) 
    country = db.Column(db.String(255), nullable=False) 
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    year_built = db.Column(db.Integer, nullable=True)
    negotiable = db.Column(db.Integer, default=0)
    amenities = db.Column(db.Text, nullable=True)  # Store amenities as a JSON or list
    approved = db.Column(db.Integer, default=0)
    available = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    
    images = db.relationship('PropertyImage', backref='property', lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='property', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='property', cascade='all, delete-orphan')

    def __repr__(self):
        return f'Property ID: {self.id} - Title: {self.title}'



class Request(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    sub_category = db.Column(db.String(255), nullable=True)
    property_type = db.Column(db.String(50), nullable=False)
    city = db.Column(db.String(255), nullable=True)
    state = db.Column(db.String(255), nullable=True)
    country = db.Column(db.String(255), nullable=True)
    amenities = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=False)
    min_price = db.Column(db.Float, nullable=True)
    max_price = db.Column(db.Float, nullable=True)
    location = db.Column(db.String(255), nullable=False)
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Integer, nullable=True)
    area = db.Column(db.Float, nullable=True)
    year_built = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    messages = db.relationship('Message', backref='request', cascade='all, delete-orphan')
    

    def __repr__(self):
        return f'Request ID: {self.id} - Title: {self.title}'


class Verification(db.Model):
    __tablename__ = 'verification'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    code = db.Column(db.String(255), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    expiration = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self) -> str:
        return 'User>>> {self.code}'


class Favorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Favorite ID: {self.id} - User ID: {self.user_id} - Property ID: {self.property_id}'


class PropertyImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    dp = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Image ID: {self.id} - Property ID: {self.property_id}'


class Review(db.Model):
    __tablename__ = 'review'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Review ID: {self.id} - Title: {self.title}'
