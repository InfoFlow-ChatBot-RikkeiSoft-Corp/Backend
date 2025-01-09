from flask import Blueprint, request, jsonify, redirect, url_for
from models.models import db, User, Log, Token, FileMetadata
from flask import Blueprint, request, jsonify
from models.models import db, User, Log
import sqlalchemy as sa
from datetime import datetime, timedelta
import jwt
from functools import wraps
from flask import current_app as app
import os
from dotenv import load_dotenv
from pytz import timezone
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import re

load_dotenv()

tz = timezone("Asia/Ho_Chi_Minh")
current_time = datetime.utcnow()

SECRET_KEY = os.getenv('SECRET_KEY')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

if not SECRET_KEY or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("Ensure SECRET_KEY, GOOGLE_CLIENT_ID, and GOOGLE_CLIENT_SECRET are set in environment variables.")

auth_routes = Blueprint('auth_routes', __name__)
email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
password_regex = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!.%*?&]{8,}$'

def is_valid_username(username):
    return re.match(email_regex, username) is not None

def token_required(f):
    """Decorator to protect routes with JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith("Bearer "):
            return jsonify({'error': 'Token is missing or malformed!'}), 401
        try:
            token = token.split(" ")[1]

            # Check if token is revoked
            invalid_token = Token.query.filter_by(token=token, revoked=True).first()
            if invalid_token:
                return jsonify({'error': 'Token has been revoked. Please log in again.'}), 401

            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid user associated with token!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired! Please log in again.'}), 401
        except Exception as e:
            return jsonify({'error': f'Token is invalid: {str(e)}'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

@auth_routes.route('/signup', methods=['POST'])
def signup():
    """Allow signup for everyone."""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400

    username = data.get('username')
    password = data.get('password')

    if not is_valid_username(username):
        return jsonify({'error': 'Enter a valid username'}), 400

    if not re.match(password_regex, password):
        return jsonify({'error': 'Password must be at least 8 characters and include numbers and letters'}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    try:
        user = User(username=username, created_at=current_time)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({'message': 'Account created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@auth_routes.route('/login', methods=['POST'])
def login():
    """Authenticate a user, log their login details, and return a JWT token."""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400

    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    # Generate a new token
    token = jwt.encode({
        'user_id': user.id,
        'exp': current_time + timedelta(hours=1)
    }, SECRET_KEY, algorithm='HS256')

    try:
        # Save the new token in the database
        token_entry = Token(user_id=user.id, token=token, issued_at=current_time, revoked=False)
        db.session.add(token_entry)

        # Log the login event
        log_entry = Log(user_id=user.id, description=f"User {username} logged in")
        db.session.add(log_entry)
        db.session.commit()

        return jsonify({'message': 'Login successful', 'token': token}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Failed to log login event: {str(e)}"}), 500


@auth_routes.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Log out a user and invalidate their token."""
    token = request.headers.get('Authorization').split(" ")[1]
    try:
        # Mark the token as revoked in the database
        invalid_token = Token.query.filter_by(token=token).first()
        if invalid_token:
            invalid_token.revoked = True

        log_entry = Log(user_id=current_user.id, description=f"User {current_user.username} logged out")
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Failed to log logout event: {str(e)}"}), 500

    return jsonify({'message': 'Logout successful'}), 200

@auth_routes.route('/google-login', methods=['POST'])
def google_login():
    """Authenticate a user via Google SSO."""
    data = request.get_json()
    token = data.get('id_token')

    if not token:
        return jsonify({'error': 'Google ID token is missing'}), 400

    try:
        # Validate token and fetch user info
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)

        username = id_info['email']

        # Check if user exists; if not, create one
        user = User.query.filter_by(username=username).first()
        if not user:
            user = User(username=username, password_hash="SSO_USER", created_at=current_time)
            db.session.add(user)
            db.session.commit()

        # Generate JWT token
        jwt_token = jwt.encode({
            'user_id': user.id,
            'exp': current_time + timedelta(hours=1)
        }, SECRET_KEY, algorithm='HS256')

        # Log the login event
        try:
            token_entry = Token(user_id=user.id, token=jwt_token, issued_at=current_time, revoked=False)
            db.session.add(token_entry)
            log_entry = Log(user_id=user.id, description=f"User {username} logged in via Google SSO")
            db.session.add(log_entry)
            db.session.commit()
        except Exception as log_error:
            db.session.rollback()
            print(f"Failed to create log entry: {log_error}")

        return jsonify({'message': 'Google login successful', 'token': jwt_token}), 200

    except Exception as e:
        print("Error:", str(e))  # Debug: Log the error
        return jsonify({'error': f"Failed to authenticate via Google: {str(e)}"}), 500


@auth_routes.route('/protected', methods=['GET'])
@token_required
def protected_route(current_user):
    return jsonify({"message": f"Welcome {current_user.username}!"}), 200