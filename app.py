from flask import Flask, jsonify
from models.models import db
from api.file_routes import file_routes
from api.auth_routes import auth_routes
from api.routes import chat_bp, weblink_bp
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

# Register Blueprints
app.register_blueprint(file_routes, url_prefix='/api/files')
app.register_blueprint(auth_routes, url_prefix='/api/auth')
app.register_blueprint(chat_bp, url_prefix='/api/chat')
app.register_blueprint(weblink_bp, url_prefix='/api/weblink')

@app.route('/')
def index():
    return jsonify({"message": "Server is running"}), 200

# Create database tables
try:
    with app.app_context():
        db.create_all()
except Exception as e:
    print(f"Database setup error: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)
