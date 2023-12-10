# coding: utf-8
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

# Base = declarative_base()
# metadata = Base.metadata

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True, server_default=text("nextval('user_id_seq'::regclass)"))
    username = Column(String(80), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(20))
    profile_picture = Column(String(255))
    email_verified = Column(Integer)
    phone_number_verified = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


class Message(db.Model):
    __tablename__ = 'message'

    id = Column(Integer, primary_key=True, server_default=text("nextval('message_id_seq'::regclass)"))
    receiver_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    sender_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    body = Column(Text)
    read = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    receiver = relationship('User', primaryjoin='Message.receiver_id == User.id')
    sender = relationship('User', primaryjoin='Message.sender_id == User.id')


class Notification(db.Model):
    __tablename__ = 'notification'

    id = Column(Integer, primary_key=True, server_default=text("nextval('notification_id_seq'::regclass)"))
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    action_user_id = Column(ForeignKey('user.id', ondelete='SET NULL'))
    action = Column(String(255), nullable=False)
    target_id = Column(Integer)
    type = Column(String(255), nullable=False)
    read = Column(Boolean)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    action_user = relationship('User', primaryjoin='Notification.action_user_id == User.id')
    user = relationship('User', primaryjoin='Notification.user_id == User.id')


class Property(db.Model):
    __tablename__ = 'property'

    id = Column(Integer, primary_key=True, server_default=text("nextval('property_id_seq'::regclass)"))
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    property_type = Column(String(50), nullable=False)
    price = Column(Float(53), nullable=False)
    area = Column(Float(53))
    bedrooms = Column(Integer)
    bathrooms = Column(Float(53))
    location = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)
    latitude = Column(Float(53))
    longitude = Column(Float(53))
    year_built = Column(Integer)
    amenities = Column(Text)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    approved = Column(Integer)
    available = Column(Integer)

    user = relationship('User')


class Request(db.Model):
    __tablename__ = 'request'

    id = Column(Integer, primary_key=True, server_default=text("nextval('request_id_seq'::regclass)"))
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)
    sub_category = Column(String(255))
    city = Column(String(255))
    state = Column(String(255))
    amenities = Column(String(255))
    description = Column(String(255))
    min_price = Column(Integer)
    max_price = Column(Integer)
    location = Column(String(255), nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    property_type = Column(String(255), nullable=False)
    bedrooms = Column(Integer)
    bathrooms = Column(Float(53))
    country = Column(String(255))
    area = Column(Float(53))
    year_built = Column(Integer)

    user = relationship('User')


class Verification(db.Model):
    __tablename__ = 'verification'

    id = Column(Integer, primary_key=True, server_default=text("nextval('verification_id_seq'::regclass)"))
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    code = Column(String(255), nullable=False)
    purpose = Column(String(255), nullable=False)
    expiration = Column(Integer, nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    user = relationship('User')


class Favorite(db.Model):
    __tablename__ = 'favorite'

    id = Column(Integer, primary_key=True, server_default=text("nextval('favorite_id_seq'::regclass)"))
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    property_id = Column(ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    property = relationship('Property')
    user = relationship('User')


class PropertyImage(db.Model):
    __tablename__ = 'property_image'

    id = Column(Integer, primary_key=True, server_default=text("nextval('property_image_id_seq'::regclass)"))
    property_id = Column(ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    image_url = Column(String(255), nullable=False)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    dp = Column(Integer)

    property = relationship('Property')


class Review(db.Model):
    __tablename__ = 'review'

    id = Column(Integer, primary_key=True, server_default=text("nextval('review_id_seq'::regclass)"))
    property_id = Column(ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    rating = Column(Float(53))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    property = relationship('Property')
    user = relationship('User')
