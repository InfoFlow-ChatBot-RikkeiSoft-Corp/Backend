from flask import Blueprint, request, jsonify, redirect, url_for
from models.models import db, User, Log, Token, Conversation
import jwt
import re
import os
import uuid
from datetime import datetime, timedelta
from functools import wraps

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

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

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

        return jsonify({'message': 'Login successful', 'token': jwt_token}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Failed to log login event: {str(e)}"}), 500

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
        id_info = id_token.verify_oauth2_token(
            id_token_jwt,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
    except Exception as e:
        return jsonify({"error": f"ID token verification failed: {str(e)}"}), 401

    email = id_info.get("email")
    user = User.query.filter_by(username=email).first()
    if not user:
        user = User(username=email, password_hash=None, created_at=current_time)
        db.session.add(user)
        db.session.commit()

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
        log_entry = Log(user_id=user.id, description=f"User {user.username} logged in")
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f"Failed to log login event: {str(e)}"}), 500

    return f"""
    <script>
      window.opener.postMessage({{'type': 'google-auth-success', 'jwt': '{jwt_token}'}}, '*');
      window.close();
    </script>
    """

###############################################################################
# CONVERSATION ROUTES
###############################################################################
@auth_routes.route('/conversations', methods=['GET'])
@token_required
def get_conversations(current_user):
    """
    Example: GET /conversations?titlesOnly=true
    Returns all conversations for the logged-in user, optionally only ID/title/timestamp
    """
    print(f"📍 GET /conversations request from user: {current_user.username}")
    titles_only = request.args.get('titlesOnly') == 'true'
    
    try:
        if titles_only:
            print("📍 Fetching titles only")
            convs = db.session.query(Conversation.id, Conversation.title, Conversation.timestamp) \
                              .filter_by(user_id=current_user.id) \
                              .order_by(Conversation.timestamp.desc()).all()
            print(f"📍 Found {len(convs)} conversations")
            data = []
            for c_id, c_title, c_ts in convs:
                data.append({
                    "id": c_id,
                    "title": c_title,
                    "timestamp": c_ts
                })
            print(f"📍 Returning data: {data}")
            return jsonify(data), 200
        else:
            print("📍 Fetching full conversation data")
            convs = Conversation.query.filter_by(user_id=current_user.id) \
                                      .order_by(Conversation.timestamp.desc()).all()
            print(f"📍 Found {len(convs)} conversations")
            data = []
            for c in convs:
                conv_data = {
                    "id": c.id,
                    "gid": c.gid,
                    "title": c.title,
                    "timestamp": c.timestamp,
                    "messages": c.messages,
                    "model": c.model,
                    "systemPrompt": c.systemPrompt
                }
                print(f"📍 Conversation data: {conv_data}")
                data.append(conv_data)
            return jsonify(data), 200
    except Exception as e:
        print(f"❌ Error in get_conversations: {str(e)}")
        return jsonify({"error": f"Failed to fetch conversations: {str(e)}"}), 500

@auth_routes.route('/conversations/search', methods=['GET'])
@token_required
def search_conversations(current_user):
    """
    Example: GET /conversations/search?in=convo&q=someTerm
             GET /conversations/search?q=titleTerm
    """
    print(f"📍 Search request from user: {current_user.username}")
    in_param = request.args.get('in')
    q = request.args.get('q', '')
    print(f"📍 Search parameters - in: {in_param}, query: {q}")

    try:
        if in_param == 'convo':
            print("📍 Searching in messages")
            found = Conversation.query.filter(
                Conversation.user_id == current_user.id,
                Conversation.messages.ilike(f'%{q}%')
            ).all()
        else:
            print("📍 Searching in titles")
            found = Conversation.query.filter(
                Conversation.user_id == current_user.id,
                Conversation.title.ilike(f'%{q}%')
            ).all()

        print(f"📍 Found {len(found)} conversations")
        data = []
        for c in found:
            conv_data = {
                "id": c.id,
                "title": c.title,
                "timestamp": c.timestamp,
                "messages": "[]"  # if you want to omit the actual messages
            }
            print(f"📍 Conversation data: {conv_data}")
            data.append(conv_data)
        return jsonify(data), 200
    except Exception as e:
        print(f"❌ Error in search_conversations: {str(e)}")
        return jsonify({"error": f"Search failed: {str(e)}"}), 500

@auth_routes.route('/conversations/<int:conv_id>', methods=['GET'])
@token_required
def get_conversation(current_user, conv_id):
    print(f"📍 GET conversation {conv_id} request from user: {current_user.username}")
    
    try:
        conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
        if not conversation:
            print(f"❌ Conversation {conv_id} not found")
            return jsonify({"error": "Conversation not found"}), 404
        
        response_data = {
            "id": conversation.id,
            "title": conversation.title,
            "timestamp": conversation.timestamp,
            "messages": conversation.messages,
            "model": conversation.model,
            "systemPrompt": conversation.systemPrompt
        }
        print(f"📍 Returning conversation data: {response_data}")
        return jsonify(response_data), 200
    except Exception as e:
        print(f"❌ Error in get_conversation: {str(e)}")
        return jsonify({"error": f"Failed to fetch conversation: {str(e)}"}), 500

@auth_routes.route('/conversations', methods=['POST'])
@token_required
def create_conversation(current_user):
    data = request.get_json()
    title = data.get('title', 'New Conversation')
    messages = data.get('messages', "[]")
    model = data.get('model', None)
    system_prompt = data.get('systemPrompt', None)

    new_conv = Conversation(
        user_id=current_user.id,
        title=title,
        messages=messages,
        model=model,
        systemPrompt=system_prompt,
        timestamp=int(datetime.now().timestamp())  # or store an integer
    )
    db.session.add(new_conv)
    db.session.commit()
    return jsonify({"message": "Conversation created", "id": new_conv.id}), 201

@auth_routes.route('/conversations/<int:conv_id>', methods=['PATCH'])
@token_required
def update_conversation(current_user, conv_id):
    conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    data = request.get_json()
    title = data.get('title')
    messages = data.get('messages')
    if title is not None:
        conversation.title = title
    if messages is not None:
        conversation.messages = messages
    conversation.timestamp = int(datetime.now().timestamp())

    db.session.commit()
    return jsonify({"message": "Conversation updated"}), 200

@auth_routes.route('/conversations/<int:conv_id>', methods=['DELETE'])
@token_required
def delete_conversation(current_user, conv_id):
    conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    db.session.delete(conversation)
    db.session.commit()
    return jsonify({"message": "Conversation deleted"}), 200
