from flask import Flask, jsonify
from flask_cors import CORS
import os
from datetime import timedelta
from src.auth import auth, mail
from src.users import users
from src.properties import properties
# from src.messages import messages
from src.requests import requests
# from src.notifications import notifications
from src.reviews import reviews
# from src.operations import operations
from src.rooms import rooms
from src.slots import slots
from src.bookings import bookings
from src.admin import admin
from src.favorites import favorites
from src.tracking import tracking
from src.admin_analytics import analytics_bp
from src.messages import messages
from src.calls import calls
from src.database import db
from flask_jwt_extended import JWTManager
from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_405_METHOD_NOT_ALLOWED
from src.constants.http_status_codes import HTTP_500_INTERNAL_SERVER_ERROR
from flask_migrate import Migrate
from flasgger import Swagger, swag_from
from src.config.swagger import template, swagger_config
from flask_mail import Mail

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True )

    if test_config is None:
        app.config.from_mapping(
            SECRET_KEY=os.environ.get("SECRET_KEY"),
            SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL"),
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY'),
            JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=1),
            JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),

            DEBUG=False,
            TESTING=False,
            MAIL_SERVER='smtp.gmail.com',
            MAIL_PORT=587,
            MAIL_USE_TLS=True,
            MAIL_USE_SSL=False,
            MAIL_DEBUG=False,
            MAIL_USERNAME='awesononeil@gmail.com',
            MAIL_PASSWORD='iggxuqxoxnndpuem',
            MAIL_DEFAULT_SENDER='awesononeil@gmail.com',
            MAIL_MAX_EMAILS=None,
            MAIL_ASCII_ATTACHMENTS=False,

            SWAGGER={
                'title': "Aperte API",
                'uiversion': 3
            },
            TURN_SECRET=os.environ.get('TURN_SECRET'),
            TURN_REALM=os.environ.get('TURN_REALM'),
            TURN_URLS=[u for u in (os.environ.get('TURN_URLS') or '').split(',') if u] or None,
        )
    else:
        app.config.from_mapping(test_config)

    # app.config['DEBUG'] = True
    # app.config['TESTING'] = False
    # app.config['MAIL_SERVER'] = 'smtp.gmail.com'  # Gmail SMTP server
    # app.config['MAIL_PORT'] = 587  # Port for TLS
    # app.config['MAIL_USE_TLS'] = True  # Use TLS (True/False)
    # app.config['MAIL_USE_SSL'] = False  # Don't use SSL (True/False)
    # # app.config['MAIL_DEBUG'] = app.debug  # Debugging (True/False)
    # app.config['MAIL_USERNAME'] = 'awesononeil@gmail.com'  # Your Gmail email
    # app.config['MAIL_PASSWORD'] = 'iggxuqxoxnndpuem'  # Your Gmail password or app password
    # app.config['MAIL_DEFAULT_SENDER'] = 'awesononeil@gmail.com'  # Default sender email
    # app.config['MAIL_MAX_EMAILS'] = None  # Max number of emails (None for unlimited)
    # # app.config['MAIL_SUPPRESS_SEND'] = app.testing  # Suppress sending (True/False)
    # app.config['MAIL_ASCII_ATTACHMENTS'] = False  # ASCII attachments (True/False)

    CORS(app)

    db.app = app
    db.init_app(app)

    mail.app = app
    mail.init_app(app)

    Migrate(app, db)
    JWTManager(app)

    # mail = Mail()
    # mail.init_app(app)

    app.register_blueprint(auth)
    app.register_blueprint(users)
    app.register_blueprint(properties)
    app.register_blueprint(requests)
    # app.register_blueprint(messages)
    app.register_blueprint(reviews)
    # app.register_blueprint(notifications)
    # app.register_blueprint(operations)
    app.register_blueprint(rooms)
    app.register_blueprint(slots)
    app.register_blueprint(bookings)
    app.register_blueprint(admin)
    app.register_blueprint(favorites)
    app.register_blueprint(tracking)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(messages)
    app.register_blueprint(calls)

    Swagger(app, config=swagger_config, template=template)

    # Seed the permission catalog + built-in roles (idempotent)
    with app.app_context():
        try:
            import src.database as dbmod
            from src.database import Permission, Role
            from src.constants.permissions import PERMISSION_CATALOG, BUILTIN_ROLES
            # permissions
            for p in PERMISSION_CATALOG:
                if not Permission.query.filter_by(name=p['name']).first():
                    dbmod.db.session.add(Permission(name=p['name'], description=p['description']))
            dbmod.db.session.commit()
            all_perms = Permission.query.all()
            perms_by_name = {p.name: p for p in all_perms}
            # roles
            for r in BUILTIN_ROLES:
                role = Role.query.filter_by(name=r['name']).first()
                if not role:
                    role = Role(name=r['name'], description=r['description'])
                    dbmod.db.session.add(role)
                    dbmod.db.session.flush()
                if r['permissions'] == '__all__':
                    role.permissions = all_perms
                else:
                    role.permissions = [perms_by_name[n] for n in r['permissions'] if n in perms_by_name]
            dbmod.db.session.commit()
            # Backfill any user missing role_id using their legacy role string
            missing = dbmod.User.query.filter(dbmod.User.role_id.is_(None)).all() if hasattr(dbmod, 'User') else []
            for u in missing:
                r = Role.query.filter_by(name=u.role).first()
                if r:
                    u.role_id = r.id
            dbmod.db.session.commit()
        except Exception:
            # Tables may not exist yet during migrations; skip silently
            pass

    @app.errorhandler(HTTP_400_BAD_REQUEST)
    def handle_400(e):
        return jsonify({'error': "Bad request"}), HTTP_400_BAD_REQUEST
    
    @app.errorhandler(HTTP_404_NOT_FOUND)
    def handle_404(e):
        return jsonify({'error': "Not found"}), HTTP_404_NOT_FOUND
    
    @app.errorhandler(HTTP_405_METHOD_NOT_ALLOWED)
    def handle_405(e):
        return jsonify({'error': "Method not allowed for the request"}), HTTP_405_METHOD_NOT_ALLOWED
    
    @app.errorhandler(HTTP_500_INTERNAL_SERVER_ERROR)
    def handle_500(e):
        return jsonify({'error': "Something went wrong, we are working on it"}), HTTP_500_INTERNAL_SERVER_ERROR

    return app
