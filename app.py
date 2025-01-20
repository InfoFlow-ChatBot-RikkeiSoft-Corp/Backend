from flask import Flask, jsonify
from models.models import db
from api.file_routes import file_routes
from api.auth_routes import auth_routes
from api.routes import chat_ns, weblink_ns, pdf_ns, rag_ns, api_ns
from api.admin_routes import admin_bp
from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
import os

from flask_restx import Api, Resource

# Load environment variables
load_dotenv()

app = Flask(__name__)
api = Api(app, title='My API', version='1.0', description='A simple Flask API with Swagger')

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
app.register_blueprint(admin_bp, url_prefix='/api/admin')

# Register Namespaces
api.add_namespace(chat_ns, path='/api/chat')
# api.add_namespace(weblink_ns, path='/api/weblink')
api.add_namespace(pdf_ns, path='/api/pdf')
api.add_namespace(rag_ns, path='/api/rag')
api.add_namespace(api_ns, path='/api')

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
