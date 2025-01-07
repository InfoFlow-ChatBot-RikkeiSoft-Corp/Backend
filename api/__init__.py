from flask import Flask
from api.routes import api_bp

def create_app():
    """Flask 앱 생성 및 Blueprint 등록"""
    app = Flask(__name__, template_folder="../templates")
    app.register_blueprint(api_bp)  # API 라우트 등록
    return app
