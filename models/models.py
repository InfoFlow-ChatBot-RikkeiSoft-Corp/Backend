from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password):
        if not password:
            raise ValueError("Password cannot be empty")
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class FileMetadata(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    size = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(10), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class Log(db.Model):
    __tablename__ = 'logs'
    id = db.Column(db.Integer, primary_key=True)  # Primary key
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # Foreign key linking to User table
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)  # Automatically set timestamp
    description = db.Column(db.String(255), nullable=False)  # Description of the log

    def __init__(self, user_id, description=None):
        self.user_id = user_id
        self.description = description

class ChatHistory(db.Model):
    __tablename__ = 'chat_history'
    
    id = db.Column(db.Integer, primary_key=True)  # 고유 ID
    conversation_id = db.Column(db.String(255), nullable=False) # 대화 ID
    user_id = db.Column(db.String(255), nullable=False)  # 사용자 ID
    question = db.Column(db.Text, nullable=False)  # 사용자 질문
    answer = db.Column(db.Text, nullable=False)  # AI 응답
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)  # 시간
    
    def to_dict(self):
        """ChatHistory 객체를 JSON 직렬화 가능한 딕셔너리로 변환"""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "question": self.question,
            "answer": self.answer,
            "timestamp": self.timestamp.isoformat()  # datetime 객체를 문자열로 변환
        }

    def __repr__(self):
        return f"timestamp: {self.timestamp}\nquestion: {self.question}\nanswer: {self.answer}...>"

    
class LLMPrompt(db.Model):
    __tablename__ = "llm_prompts"

    id = db.Column(db.Integer, primary_key=True)
    prompt_name = db.Column(db.String(255), nullable=False, unique=True)
    prompt_text = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(255), nullable=False)
    updated_by = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<LLMPrompt {self.prompt_name}>"
 
class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=True)  # 사용자 지정 제목
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
