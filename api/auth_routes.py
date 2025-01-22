from flask import Blueprint, request, jsonify, redirect, url_for
from models.models import db, User, Log, Token, Conversation
import jwt
import re
import os
import uuid
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy import text
import requests as py_requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv
from pytz import timezone

load_dotenv()

auth_routes = Blueprint('auth_routes', __name__)

SECRET_KEY = os.getenv('SECRET_KEY')
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

if not SECRET_KEY or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("Ensure SECRET_KEY, GOOGLE_CLIENT_ID, and GOOGLE_CLIENT_SECRET are set.")

# Regex
email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
password_regex = r'^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!.%*?&]{8,}$'

tz = timezone("Asia/Ho_Chi_Minh")
current_time = datetime.utcnow()

def is_valid_username(username):
    return re.match(email_regex, username) is not None

def token_required(f):
    """Decorator to protect routes with JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith("Bearer "):
            return jsonify({'error': 'Token is missing or malformed!'}), 401
        token_str = token.split(" ")[1]

        # Check if token is revoked
        invalid_token = Token.query.filter_by(token=token_str, revoked=True).first()
        if invalid_token:
            return jsonify({'error': 'Token has been revoked. Please log in again.'}), 401

        try:
            data = jwt.decode(token_str, SECRET_KEY, algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid user associated with token!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired! Please log in again.'}), 401
        except Exception as e:
            return jsonify({'error': f'Token is invalid: {str(e)}'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

###############################################################################
# AUTH ROUTES
###############################################################################


@auth_routes.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400

    username = data['username']
    password = data['password']

    if not is_valid_username(username):
        return jsonify({'error': 'Enter a valid username'}), 400

    if not re.match(password_regex, password):
        return jsonify({'error': 'Password must be at least 8 chars & include nums and letters'}), 400

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
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400

    username = data['username']
    password = data['password']

    # 1) Authenticate user from your "users" table
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    # 2) Now check admin status from "company_employee" by matching email
    try:
        # Raw SQL query to fetch the role from your "company_employee" table
        result = db.session.execute(
            text("SELECT role FROM company_employee WHERE email = :email"),
            {"email": username}
        )
        row = result.fetchone()  # returns None if no match
        role = row[0] if row else None
        
        # Admin if "role" == "admin"
        is_admin = (role == 'admin')
    except Exception as e:
        return jsonify({'error': f"Admin check failed: {str(e)}"}), 500

    # 3) Generate your JWT token & log the user in as before
    now = datetime.utcnow()
    jwt_token = jwt.encode({
        'user_id': user.id,
        'exp': now + timedelta(hours=1),
        'iat': now,
        'jti': str(uuid.uuid4())
    }, SECRET_KEY, algorithm='HS256')

    try:
        token_entry = Token(user_id=user.id, token=jwt_token, issued_at=now, revoked=False)
        db.session.add(token_entry)
        log_entry = Log(user_id=user.id, description=f"User {username} logged in")
        db.session.add(log_entry)
        db.session.commit()

        # 4) Return is_admin in your JSON response
        return jsonify({
            'message': 'Login successful',
            'token': jwt_token,
            'is_admin': is_admin,
            'user_id':user.id
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Failed to log login event: {str(e)}"}), 500


@auth_routes.route('/get-user-details', methods=['GET'])
@token_required
def get_user_details(current_user):
    """Fetches user details for authenticated users."""
    try:
        # Fetch role from "company_employee" table
        result = db.session.execute(
            text("SELECT role FROM company_employee WHERE email = :email"),
            {"email": current_user.username}
        )
        row = result.fetchone()
        is_admin = row[0] == 'admin' if row else False

        return jsonify({
            "user_id": current_user.id,
            "username": current_user.username,
            "is_admin": is_admin
        }), 200
    except Exception as e:
        return jsonify({"error": f"Failed to fetch user details: {str(e)}"}), 500


@auth_routes.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    token_str = request.headers.get('Authorization').split(" ")[1]
    try:
        # Mark the token as revoked
        invalid_token = Token.query.filter_by(token=token_str).first()
        if invalid_token:
            invalid_token.revoked = True
        log_entry = Log(user_id=current_user.id, description=f"User {current_user.username} logged out")
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Failed to log logout event: {str(e)}"}), 500

    return jsonify({'message': 'Logout successful'}), 200


###############################################################################
# GOOGLE LOGIN
###############################################################################
@auth_routes.route('/google-redirect')
def google_redirect():
    from urllib.parse import urlencode
    google_oauth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": "http://127.0.0.1:5000/api/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{google_oauth_endpoint}?{urlencode(params)}"
    return redirect(url)

@auth_routes.route('/google/callback')
def google_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "No code provided"}), 400

    # Exchange the code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": "http://127.0.0.1:5000/api/auth/google/callback",
        "grant_type": "authorization_code",
    }
    resp = py_requests.post(token_url, data=data)
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch tokens from Google"}), 400

    tokens = resp.json()
    id_token_jwt = tokens.get("id_token")

    try:
        # Verify Google ID token
        id_info = id_token.verify_oauth2_token(
            id_token_jwt,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        email = id_info.get("email")
        if not email:
            return jsonify({"error": "Email not found in Google response"}), 400

        # Fetch or create user
        user = User.query.filter_by(username=email).first()
        if not user:
            user = User(username=email, password_hash=None, created_at=current_time)
            db.session.add(user)
            db.session.commit()

        # Check role from company_employee
        result = db.session.execute(
            text("SELECT role FROM company_employee WHERE email = :email"),
            {"email": email}
        )
        row = result.fetchone()
        is_admin = row[0] == 'admin' if row else False

        # Generate JWT token
        now = datetime.utcnow()
        jwt_token = jwt.encode({
            'user_id': user.id,
            'exp': now + timedelta(hours=1),
            'iat': now,
            'jti': str(uuid.uuid4())
        }, SECRET_KEY, algorithm='HS256')

        # Save token in DB and log the login event
        try:
            token_entry = Token(user_id=user.id, token=jwt_token, issued_at=now, revoked=False)
            log_entry = Log(user_id=user.id, description=f"User {user.username} logged in via Google")
            db.session.add(token_entry)
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f"Failed to log login event: {str(e)}"}), 500

        # Send token back to frontend
        return f"""
        <script>
          window.opener.postMessage({{'type': 'google-auth-success', 'jwt': '{jwt_token}', 'user_id': {user.id}, 'is_admin': {str(is_admin).lower()}}}, '*');
          window.close();
        </script>
        """
    except Exception as e:
        return jsonify({"error": f"ID token verification failed: {str(e)}"}), 401
