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

load_dotenv()  # Load environment variables from .env file

tz = timezone("Asia/Ho_Chi_Minh")  # Replace with your desired time zone
current_time = datetime.now(tz)

SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set in the environment variables.")

auth_routes = Blueprint('auth_routes', __name__)

def token_required(f):
    """Decorator to protect routes with JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or not token.startswith("Bearer "):
            return jsonify({'error': 'Token is missing or malformed!'}), 401
        try:
            token = token.split(" ")[1]
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
    """Allow signup only for employees listed in the company_employee database."""
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'error': 'Username and password are required'}), 400

    username = data.get('username')
    password = data.get('password')

    if len(username) < 3 or len(password) < 8:
        return jsonify({'error': 'Username must be at least 3 characters and password at least 8 characters'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 409

    employee = db.session.execute(
        sa.text("SELECT * FROM company_employee WHERE email = :email"),
        {'email': username}
    ).mappings().fetchone()

    if not employee:
        return jsonify({'error': 'You must be an employee to sign up'}), 403
    
    tz = timezone("Asia/Kolkata")  # Replace with your desired time zone
    current_time = datetime.now(tz)

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

    # Debug: Log incoming data
    app.logger.debug(f"Login attempt received with data: {data}")

    if not data or 'username' not in data or 'password' not in data:
        app.logger.error("Missing username or password in request")
        return jsonify({'error': 'Username and password are required'}), 400

    username = data.get('username')
    password = data.get('password')

    # Debug: Log received username
    app.logger.debug(f"Attempting to authenticate user: {username}")

    user = User.query.filter_by(username=username).first()

    # Debug: Check if user exists
    if not user:
        app.logger.warning(f"User not found: {username}")
        return jsonify({'error': 'Invalid credentials'}), 401

    # Debug: Verify password
    if not user.check_password(password):
        app.logger.warning(f"Invalid password for user: {username}")
        return jsonify({'error': 'Invalid credentials'}), 401

    # Check employee in company database
    employee = db.session.execute(
        sa.text("SELECT * FROM company_employee WHERE email = :email"),
        {'email': username}
    ).mappings().fetchone()

    # Debug: Log employee lookup
    app.logger.debug(f"Employee lookup result for {username}: {employee}")

    if not employee:
        app.logger.warning(f"User {username} not found in company employee database")
        return jsonify({'error': 'User not found in company employee database'}), 403

    # Get role or set default
    role = employee.get('role', 'unknown')

    # Generate token
    try:
        token = jwt.encode({
            'user_id': user.id,
            'exp': current_time + timedelta(hours=1)
        }, SECRET_KEY, algorithm='HS256')
        app.logger.debug(f"JWT generated for user {username}")
    except Exception as e:
        app.logger.error(f"Failed to generate JWT for user {username}: {str(e)}")
        return jsonify({'error': 'Failed to generate authentication token'}), 500

    # Log login event
    try:
        log_entry = Log(user_id=user.id, description=f"User {username} logged in")
        db.session.add(log_entry)
        db.session.commit()
        app.logger.info(f"User {username} logged in successfully")
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Failed to log login event for user {username}: {str(e)}")
        return jsonify({'error': f"Failed to log login event: {str(e)}"}), 500

    return jsonify({'message': 'Login successful', 'token': token, 'role': role}), 200


@auth_routes.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Log out a user and invalidate their token."""
    try:
        log_entry = Log(user_id=current_user.id, description=f"User {current_user.username} logged out")
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Failed to log logout event: {str(e)}"}), 500

    return jsonify({'message': 'Logout successful'}), 200
