from models.models import ChatHistory, db

class ChatService:
    @staticmethod
    def save_chat(user_id, question, answer):
        """사용자의 채팅 기록을 DB에 저장"""
        new_chat = ChatHistory(user_id=user_id, question=question, answer=answer)
        db.session.add(new_chat)
        db.session.commit()

    @staticmethod
    def get_chat_history(user_id):
        """사용자의 채팅 기록을 가져옴"""
        return ChatHistory.query.filter_by(user_id=user_id).order_by(ChatHistory.timestamp.desc()).all()
