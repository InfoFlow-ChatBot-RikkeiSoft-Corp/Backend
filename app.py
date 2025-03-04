from flask import Flask, jsonify
from models.models import db
from api.file_routes import file_routes
from api.auth_routes import auth_routes
from api.routes import chat_bp, weblink_bp, pdf_bp, rag_bp, api_bp
from api.admin_routes import admin_bp
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
import os

# Load environment variables
load_dotenv()

app = Flask(__name__)

# 앱에 CORS 설정 적용
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)


# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db.init_app(app)

USER_AGENT = os.getenv("USER_AGENT")
if USER_AGENT:
    os.environ["USER_AGENT"] = USER_AGENT


# Register Blueprints
app.register_blueprint(file_routes, url_prefix='/api/files')
app.register_blueprint(auth_routes, url_prefix='/api/auth')
app.register_blueprint(chat_bp, url_prefix='/api/chat')
app.register_blueprint(weblink_bp, url_prefix='/api/weblink')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(pdf_bp, url_prefix='/api/pdf')
app.register_blueprint(rag_bp, url_prefix='/api/rag')
app.register_blueprint(api_bp, url_prefix='/api')

# Access environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")

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
