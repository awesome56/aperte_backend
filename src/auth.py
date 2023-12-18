from src.constants.http_status_codes import HTTP_400_BAD_REQUEST
from src.constants.http_status_codes import HTTP_404_NOT_FOUND
from src.constants.http_status_codes import HTTP_409_CONFLICT
from src.constants.http_status_codes import HTTP_401_UNAUTHORIZED
from src.constants.http_status_codes import HTTP_200_OK
from src.constants.http_status_codes import HTTP_201_CREATED
from src.constants.http_status_codes import HTTP_202_ACCEPTED
from src.constants.http_status_codes import HTTP_204_NO_CONTENT
from src.database import User, Verification, db
from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import check_password_hash, generate_password_hash
import validators
from flask_jwt_extended import jwt_required, create_access_token, create_refresh_token, get_jwt_identity
from src.constants.functions import check_password, generate_random_string
from datetime import datetime, timedelta, timezone
from flask_mail import Message, Mail
from sqlalchemy import func, or_
import time
from flasgger import swag_from

auth = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

mail = Mail()


@auth.post('/register')
@swag_from('./docs/auth/register.yml')
def register():

    full_name = ""
    username = ""
    email = ""
    password = ""

    if request.is_json:
        full_name = request.json['full_name']
        username = request.json['username']
        email = request.json['email']
        password = request.json['password']
    else:
        full_name = request.form['full_name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
    

    if not full_name or not username or not email or not password:
        return jsonify({'error': "Full name, Username, Email and Password must not be empty"}), HTTP_400_BAD_REQUEST

    if not check_password(password):
        return jsonify({'error': "Password must contain an upper, a symbol, a number and must be more than 5 characters"}), HTTP_400_BAD_REQUEST
    
    if len(full_name) < 3:
        return jsonify({'error': "Name must be more than 2 characters"}), HTTP_400_BAD_REQUEST
    
    if not validators.email(email):
        return jsonify({'error': "Email must be a valid email"}), HTTP_400_BAD_REQUEST

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({'error': "Email already exists"}), HTTP_409_CONFLICT
    
    if User.query.filter_by(username=username).first() is not None:
        return jsonify({'error': "Username already exists"}), HTTP_409_CONFLICT
    
    pwd_hash = generate_password_hash(password)

    user = User(full_name=full_name, username=username, email=email, password=pwd_hash, email_verified=0, created_at=datetime.now(), updated_at=datetime.now())
    db.session.add(user)
    db.session.commit()

    code = generate_random_string(6)
    purpose = "verifyemail"
    expiration = 5
    message = "Here is your email verification code: " + str(code) + ". This code expires in " + str(expiration) + " min."

    code_hash = generate_password_hash(code)

    old_verifications = Verification.query.filter_by(user_id = user.id, purpose=purpose)
    for old_verification in old_verifications:
        db.session.delete(old_verification)

    verification = Verification(user_id=user.id, code=code_hash, purpose=purpose, expiration=expiration, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(verification)
    db.session.commit()

    #Send email
    msg = Message(subject='Verify Email', recipients=[email])
    msg.body = message

    mail.send(msg)

    return jsonify({
        'message': "User created",
        'user': {
            'full_name': full_name, 'username' : username, 'email' : email, 'email_verified': 0
        }
    }), HTTP_201_CREATED


@auth.post('/login')
@swag_from('./docs/auth/login.yml')
def login():

    email = ""
    password = ""

    if request.is_json:
        email = request.json['email']
        password = request.json['password']
    else:
        email = request.form['email']
        password = request.form['password']

    if not email or not password:
        return jsonify({'error': "Name and Password must not be empty"}), HTTP_401_UNAUTHORIZED
    
    # if not validators.email(email):
    #     return jsonify({'error': "Email must be a valid email"}), HTTP_401_UNAUTHORIZED

    user = User.query.filter(or_(User.email == email, User.username == email)).first()

    if user is None:
        return jsonify({'error': "Credentials does not match"}), HTTP_401_UNAUTHORIZED

    if user:
        is_pass_correct = check_password_hash(user.password, password)

        if is_pass_correct:

            if user.email_verified == 0:
                code = generate_random_string(6)
                purpose = "verifyemail"
                expiration = 5
                message = "Here is your email verification code: " + str(code) + ". This code expires in " + str(expiration) + " min."

                code_hash = generate_password_hash(code)

                old_verifications = Verification.query.filter_by(user_id = user.id, purpose=purpose)
                for old_verification in old_verifications:
                    db.session.delete(old_verification)

                verification = Verification(user_id=user.id, code=code_hash, purpose=purpose, expiration=expiration, created_at=datetime.now(), updated_at=datetime.now())

                db.session.add(verification)
                db.session.commit()

                #Send email
                msg = Message(subject='Verify Email', recipients=[user.email])
                msg.body = message

                mail.send(msg)

                return jsonify({'msg': "Pls verify email"}), HTTP_200_OK
            
            refresh = create_refresh_token(identity=user.id)
            access = create_access_token(identity=user.id)

            # response = jsonify({
            #     'user': {
            #         'access': access,
            #         'full_name': user.full_name,
            #         'username' : user.username,
            #         'email': user.email,
            #         'email_verified': user.email_verified
            #     }
            # })

            # response.set_cookie('refresh_token', refresh, httponly=True, samesite='Strict')

            # response.set_cookie('refresh_token', refresh, httponly=False, samesite='None')

            # return response, HTTP_202_ACCEPTED

            return jsonify({
                'user': {
                    'refresh': refresh,
                    'access': access,
                    'full_name': user.full_name,
                    'username' : user.username,
                    'email': user.email,
                    'email_verified': user.email_verified
                }
            }), HTTP_202_ACCEPTED
        
    return jsonify({'error': "Unauthorized"}), HTTP_401_UNAUTHORIZED


@auth.post("/verifyemail/<email>")
@swag_from('./docs/auth/verifyemail.yml')
def verify_password(email):

    if not validators.email(email):
        return jsonify({'error': "Email must be a valid email"}), HTTP_400_BAD_REQUEST

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': "Email not found"}), HTTP_404_NOT_FOUND
    
    code = request.json['code']

    verification = Verification.query.filter_by(user_id=user.id, purpose="verifyemail").first()

    if not verification:
        return jsonify({'error': "Token error"}), HTTP_400_BAD_REQUEST

    is_code_correct = check_password_hash(verification.code, code)

    if not is_code_correct:
        return jsonify({'error': "Token invalid"}), HTTP_400_BAD_REQUEST
    
    time_interval = timedelta(minutes=verification.expiration)

    current_time = datetime.now()

    if  current_time - verification.created_at >= time_interval:
        db.session.delete(verification)
        db.session.commit()
        return jsonify({'error': "Token expired"}), HTTP_400_BAD_REQUEST

    user.email_verified = 1

    db.session.delete(verification)
    db.session.commit()

    #Send email
    msg = Message(subject='Email verification successful', recipients=[email])
    msg.body = "Your email verification is successful"

    mail.send(msg)

    refresh = create_refresh_token(identity=user.id)
    access = create_access_token(identity=user.id)

    # response = jsonify({
    #             'user': {
    #                 'access': access,
    #                 'full_name': user.full_name,
    #                 'username' : user.username,
    #                 'email': user.email,
    #                 'email_verified': user.email_verified
    #             }
    #         })

    # response.set_cookie('refresh_token', refresh, httponly=True, samesite='Strict')

    # response.set_cookie('refresh_token', refresh, httponly=False, samesite='None')

    # return response, HTTP_202_ACCEPTED

    return jsonify({
        'user': {
            'refresh': refresh,
            'access': access,
            'full_name': user.full_name,
            'username' : user.username,
            'email': user.email,
            'email_verified': user.email_verified
        }
    }), HTTP_202_ACCEPTED


@auth.get("/resendverify/<email>")
@swag_from('./docs/auth/resendverify.yml')
def resend_verify(email):

    if not validators.email(email):
        return jsonify({'error': "Email must be a valid email"}), HTTP_400_BAD_REQUEST

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'error': "Email not found"}), HTTP_404_NOT_FOUND
    
    if user.email_verified == 1:
        return jsonify({'error': "User email already verified"}), HTTP_409_CONFLICT

    code = generate_random_string(6)
    purpose = "verifyemail"
    expiration = 5
    message = "Here is your email verification code: " + str(code) + ". This code expires in " + str(expiration) + " min."

    code_hash = generate_password_hash(code)

    old_verifications = Verification.query.filter_by(user_id = user.id, purpose=purpose)
    for old_verification in old_verifications:
        db.session.delete(old_verification)

    verification = Verification(user_id=user.id, code=code_hash, purpose=purpose, expiration=expiration, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(verification)
    db.session.commit()

    #Send email
    msg = Message(subject='Verify Email', recipients=[email])
    msg.body = message

    mail.send(msg)

    return jsonify({'msg': "Pls verify email"}), HTTP_200_OK


@auth.get("/user")
@jwt_required()
@swag_from('./docs/user/user.yml')
def user():
    user_id = get_jwt_identity()
    user = User.query.filter_by(id=user_id).first()
    return jsonify({
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.full_name,
                    'phone_number': user.phone_number,
                    'profile_picture': user.profile_picture,
                    'email_verified': user.email_verified,
                    'phone_number_verified': user.phone_number_verified,
                    'created_at': user.created_at,
                    'updated_at': user.updated_at,
            }), HTTP_200_OK

@auth.get("/token/refresh")
@jwt_required(refresh=True)
@swag_from('./docs/auth/refreshtoken.yml')
def refresh_users_token():
    identity = get_jwt_identity()
    access = create_access_token(identity=identity)
    return jsonify({
                    'access': access
            }), HTTP_200_OK

@auth.get("/forgotpassword/<email>")
@swag_from('./docs/auth/forgotpassword.yml')
def forgot_password(email):

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': "Email not found"}), HTTP_404_NOT_FOUND
    
    code = generate_random_string(6)
    purpose = "resetpassword"
    expiration = 5
    message = "Here is your reset password verification code: " + str(code) + ". This code expires in " + str(expiration) + " min."

    old_verifications = Verification.query.filter_by(user_id = user.id, purpose=purpose)
    for old_verification in old_verifications:
        db.session.delete(old_verification)
            
    db.session.commit()

    code_hash = generate_password_hash(code)

    verification = Verification(user_id=user.id, code=code_hash, purpose=purpose, expiration=expiration, created_at=datetime.now(), updated_at=datetime.now())

    db.session.add(verification)
    db.session.commit()

    #Send email
    msg = Message(subject='Password Reset', recipients=[email])
    msg.body = message

    mail.send(msg)

    return jsonify({'msg': "Token sent to email"}), HTTP_201_CREATED


@auth.post("/resetpassword/<email>")
@swag_from('./docs/auth/resetpassword.yml')
def reset_password(email):

    if not validators.email(email):
        return jsonify({'error': "Email must be a valid email"}), HTTP_400_BAD_REQUEST

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': "Email not found"}), HTTP_404_NOT_FOUND
    
    code = request.json['code']
    password = request.json['password']
    comfirm_password = request.json['comfirm_password']

    if not comfirm_password == password:
        return jsonify({'error': "Password missmatch"}), HTTP_400_BAD_REQUEST

    if not check_password(password):
        return jsonify({'error': "Password must contain an upper, a symbol, a number and must be more than 5 characters"}), HTTP_400_BAD_REQUEST

    verification = Verification.query.filter_by(user_id=user.id, purpose="resetpassword").first()

    if not verification:
        return jsonify({'error': "Token error"}), HTTP_400_BAD_REQUEST

    is_code_correct = check_password_hash(verification.code, code)

    if not is_code_correct:
        return jsonify({'error': "Token invalid"}), HTTP_400_BAD_REQUEST
    
    if check_password_hash(user.password, password):
        return jsonify({'error': "New password must be diffrent from Old password"}), HTTP_400_BAD_REQUEST
    
    time_interval = timedelta(minutes=verification.expiration)

    current_time = datetime.now()

    if current_time - verification.created_at >= time_interval:
        db.session.delete(verification)
        db.session.commit()
        return jsonify({'error': "Token expired"}), HTTP_400_BAD_REQUEST
    
    pwd_hash = generate_password_hash(password)

    user.password = pwd_hash

    db.session.delete(verification)

    db.session.commit()

    #Send email
    msg = Message(subject='Password Reset Successful', recipients=[email])
    msg.body = "Your password as been successfully changed"

    mail.send(msg)

    return jsonify({'msg': "Password change successful"}), HTTP_200_OK
