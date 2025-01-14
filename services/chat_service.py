from datetime import datetime
import uuid
from models.models import ChatHistory, db

## 사용 시 기존 로직에 통합 필요

class ChatService:
    @staticmethod
    def save_chat(user_id, question, answer, conversation_id=None):
        """사용자의 채팅 기록을 DB에 저장"""
        try:
            # conversation_id가 없으면 생성
            if conversation_id is None:
                conversation_id = str(uuid.uuid4())  # 고유 ID 생성

            new_chat = ChatHistory(
                user_id=user_id,
                question=question,
                answer=answer,
                conversation_id=conversation_id,  # 추가
                timestamp=datetime.utcnow()
            )
            db.session.add(new_chat)
            db.session.commit()
        except Exception as e:
            print(f"❌ Error saving chat: {e}")
            db.session.rollback()
            raise e


    @staticmethod
    def get_chat_history(user_id):
        """사용자의 채팅 기록을 가져옴"""
        return ChatHistory.query.filter_by(user_id=user_id).order_by(ChatHistory.timestamp.desc()).all()
