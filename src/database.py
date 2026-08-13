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
    
class Permission(db.Model):
    __tablename__ = 'permission'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())

    def __repr__(self):
        return f'Permission: {self.name}'


role_permissions = db.Table(
    'role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id', ondelete='CASCADE'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permission.id', ondelete='CASCADE'), primary_key=True),
)


class Role(db.Model):
    __tablename__ = 'role'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())

    permissions = db.relationship('Permission', secondary=role_permissions, backref='roles', lazy='dynamic')

    def __repr__(self):
        return f'Role: {self.name}'


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    role_id = db.Column(db.Integer, db.ForeignKey('role.id', ondelete='SET NULL'), nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)
    profile_picture = db.Column(db.String(255), default="default_profile.png")
    email_verified = db.Column(db.Integer, default=0)
    phone_number_verified = db.Column(db.Integer, nullable=True)
    last_seen = db.Column(db.DateTime, nullable=True)
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
    role_obj = db.relationship('Role', backref='users', foreign_keys=[role_id])

    def __repr__(self):
        return f'User ID: {self.id} - Username: {self.username}'


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('request.id', ondelete='CASCADE'), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=True)
    body = db.Column(db.Text, nullable=False)
    voice_url = db.Column(db.String(500), nullable=True)
    voice_duration = db.Column(db.Integer, nullable=True)
    read = db.Column(db.Integer, default=0)
    delivered = db.Column(db.Integer, default=0)
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
    disabled = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
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
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=True)
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


class PropertyClaim(db.Model):
    """A user's request to take over ownership of an admin-listed property.

    Verification is email-code based when the property has a contact email;
    otherwise the claimant uploads ownership documents reviewed by the admin
    (document_url holds the uploaded proof).
    """

    __tablename__ = 'property_claim'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)  # pending_verification | pending | approved | rejected
    document_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'PropertyClaim ID: {self.id} - Property {self.property_id} - {self.status}'


class PropertyUnavailability(db.Model):
    """Owner-blocked date ranges for a bookable property (hotel/shortlet)."""

    __tablename__ = 'property_unavailability'

    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())

    def __repr__(self):
        return f'Unavailability ID: {self.id} - Property {self.property_id}: {self.start_date}..{self.end_date}'


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


class PageVisit(db.Model):
    __tablename__ = 'page_visit'

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.String(64), index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='CASCADE'), nullable=True)
    path = db.Column(db.String(255), nullable=False)
    referrer = db.Column(db.String(255), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(), index=True)

    def __repr__(self):
        return f'PageVisit ID: {self.id} - Path: {self.path}'


class VisitorSession(db.Model):
    """One row per browser session (client-generated session id, per tab)."""

    __tablename__ = 'visitor_session'

    id = db.Column(db.String(64), primary_key=True)
    visitor_id = db.Column(db.String(64), index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.now(), index=True)
    last_activity_at = db.Column(db.DateTime, default=datetime.now(), index=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, nullable=True)
    page_views = db.Column(db.Integer, default=0)
    landing_path = db.Column(db.String(255), nullable=False)
    landing_title = db.Column(db.String(255), nullable=True)
    exit_path = db.Column(db.String(255), nullable=True)
    referrer = db.Column(db.String(255), nullable=True)
    source_type = db.Column(db.String(20), default='direct')
    utm_source = db.Column(db.String(100), nullable=True)
    utm_medium = db.Column(db.String(100), nullable=True)
    utm_campaign = db.Column(db.String(100), nullable=True)
    utm_term = db.Column(db.String(100), nullable=True)
    utm_content = db.Column(db.String(100), nullable=True)
    device_type = db.Column(db.String(20), default='desktop')
    browser = db.Column(db.String(50), nullable=True)
    os = db.Column(db.String(50), nullable=True)
    screen_size = db.Column(db.String(30), nullable=True)
    country = db.Column(db.String(4), nullable=True)
    is_bounce = db.Column(db.Boolean, nullable=True)

    def __repr__(self):
        return f'VisitorSession ID: {self.id} - Visitor: {self.visitor_id}'


class AnalyticsEvent(db.Model):
    """Generic analytics event: page views, custom events, performance metrics and errors.

    Keeping a single high-volume table (instead of many small ones) makes
    ingestion cheap and reporting flexible. Performance is handled with
    indexes and filtered aggregations.
    """

    __tablename__ = 'analytics_event'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), index=True, nullable=False)
    visitor_id = db.Column(db.String(64), index=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    event_type = db.Column(db.String(20), index=True, nullable=False)  # pageview | event | performance | error
    name = db.Column(db.String(100), nullable=True)  # custom event name
    category = db.Column(db.String(50), nullable=True)  # event category
    properties = db.Column(db.Text, nullable=True)  # JSON metadata for custom events
    path = db.Column(db.String(255), index=True, nullable=False)
    title = db.Column(db.String(255), nullable=True)
    referrer = db.Column(db.String(255), nullable=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id', ondelete='SET NULL'), index=True, nullable=True)
    time_on_page_ms = db.Column(db.Integer, nullable=True)
    device_type = db.Column(db.String(20), nullable=True)
    browser = db.Column(db.String(50), nullable=True)
    os = db.Column(db.String(50), nullable=True)
    screen_size = db.Column(db.String(30), nullable=True)
    country = db.Column(db.String(4), nullable=True)
    source_type = db.Column(db.String(20), nullable=True)
    utm_source = db.Column(db.String(100), nullable=True)
    utm_medium = db.Column(db.String(100), nullable=True)
    utm_campaign = db.Column(db.String(100), nullable=True)
    utm_term = db.Column(db.String(100), nullable=True)
    utm_content = db.Column(db.String(100), nullable=True)
    # performance metrics (milliseconds, cls is a score)
    ttfb = db.Column(db.Integer, nullable=True)
    dom_loaded = db.Column(db.Integer, nullable=True)
    load_time = db.Column(db.Integer, nullable=True)
    fcp = db.Column(db.Integer, nullable=True)
    lcp = db.Column(db.Integer, nullable=True)
    cls = db.Column(db.Float, nullable=True)
    js_errors = db.Column(db.Integer, default=0)
    failed_requests = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now(), index=True)

    def __repr__(self):
        return f'AnalyticsEvent ID: {self.id} - {self.event_type} - {self.path}'


class Call(db.Model):
    """In-app voice/video call between two users (WebRTC)."""

    __tablename__ = 'call'

    id = db.Column(db.String(36), primary_key=True)
    caller_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    callee_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    call_type = db.Column(db.String(10), default='audio')  # audio | video
    status = db.Column(db.String(20), default='ringing', index=True)  # ringing | active | ended | declined | missed
    ended_by = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='SET NULL'), nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(), index=True)
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())

    def __repr__(self):
        return f'Call ID: {self.id} - {self.caller_id} -> {self.callee_id} - {self.status}'


class CallSignal(db.Model):
    """WebRTC signaling messages relayed between call participants."""

    __tablename__ = 'call_signal'

    id = db.Column(db.Integer, primary_key=True)
    call_id = db.Column(db.String(36), db.ForeignKey('call.id', ondelete='CASCADE'), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    signal_type = db.Column(db.String(20), nullable=False)  # offer | answer | ice
    payload = db.Column(db.Text, nullable=False)  # JSON
    created_at = db.Column(db.DateTime, default=datetime.now(), index=True)

    def __repr__(self):
        return f'CallSignal ID: {self.id} - {self.signal_type}'
