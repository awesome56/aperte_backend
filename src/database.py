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
    role = db.Column(db.String(20), nullable=False, default='user')
    phone_number = db.Column(db.String(30), nullable=True)
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
    bookings = db.relationship('Booking', backref='customer', cascade='all, delete-orphan')

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
    category = db.Column(db.String(50), nullable=False, default='property')
    property_type = db.Column(db.String(50), nullable=False)
    purpose = db.Column(db.String(20), nullable=False, default='rent')
    attributes = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default='USD')
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
    contact_phone = db.Column(db.String(30), nullable=True)
    contact_email = db.Column(db.String(255), nullable=True)
    contact_website = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
    
    images = db.relationship('PropertyImage', backref='property', lazy='dynamic', cascade='all, delete-orphan')
    videos = db.relationship('PropertyVideo', backref='property', lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='property', cascade='all, delete-orphan')
    messages = db.relationship('Message', backref='property', cascade='all, delete-orphan')
    rooms = db.relationship('Room', backref='property', cascade='all, delete-orphan')
    slots = db.relationship('Slot', backref='property', cascade='all, delete-orphan')
    bookings = db.relationship('Booking', backref='property', cascade='all, delete-orphan')

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


class PropertyVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    video_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Video ID: {self.id} - Property ID: {self.property_id}'


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


class Room(db.Model):
    __tablename__ = 'room'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    beds = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    amenities = db.Column(db.Text, nullable=True)
    available = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    images = db.relationship('RoomImage', backref='room', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'Room ID: {self.id} - Type: {self.room_type}'


class RoomImage(db.Model):
    __tablename__ = 'room_image'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id', ondelete='CASCADE'), nullable=False)
    image_url = db.Column(db.String(255), nullable=False)
    dp = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Room Image ID: {self.id} - Room ID: {self.room_id}'


class Slot(db.Model):
    __tablename__ = 'slot'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='available')
    booked_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Slot ID: {self.id} - Date: {self.date}'


class Booking(db.Model):
    __tablename__ = 'booking'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id', ondelete='SET NULL'), nullable=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('slot.id', ondelete='SET NULL'), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    check_in = db.Column(db.Date, nullable=True)
    check_out = db.Column(db.Date, nullable=True)
    guests = db.Column(db.Integer, default=1)
    nights = db.Column(db.Integer, nullable=True)
    total = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Booking ID: {self.id} - Status: {self.status}'
