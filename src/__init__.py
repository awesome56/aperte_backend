from flask import Flask, jsonify
import os
from src.auth import auth, mail
from src.users import users
from src.properties import properties
# from src.messages import messages
from src.requests import requests
# from src.notifications import notifications
from src.reviews import reviews
# from src.operations import operations
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
            }
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

    Swagger(app, config=swagger_config, template=template)

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
