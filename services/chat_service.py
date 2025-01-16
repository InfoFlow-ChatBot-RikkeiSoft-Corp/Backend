from models.models import ChatHistory, Conversation, db

class ChatService:
    @staticmethod
    def new_conversation(user_id, title):
        """사용자가 새로운 conversation 엶"""
        new_conversation = Conversation(user_id=user_id, title=title)
        db.session.add(new_conversation)
        db.session.commit()
        return new_conversation.id

    @staticmethod
    def save_chat(conversation_id, user_id, question, answer):
        """사용자의 채팅 기록을 DB에 저장"""
        if not user_id:
            raise ValueError("user_id는 필수입니다.")

        new_chat = ChatHistory(
            conversation_id=conversation_id,
            user_id=user_id,
            question=question,
            answer=answer
        )
        db.session.add(new_chat)
        db.session.commit()
    
    @staticmethod
    def get_conversation(user_id):
        """사용자의 conversation 조회"""
        if not user_id:
            raise ValueError("user_id는 필수입니다.")
    
    @staticmethod
    def get_user_conversations(user_id: str):
        """특정 사용자에 대한 모든 대화(conversation) 가져오기"""
        conversations = Conversation.query.filter_by(user_id=user_id).order_by(Conversation.created_at.desc()).all()
        return conversations
    @staticmethod
    def get_conversation_by_id(conversation_id):
        """대화 ID를 통해 특정 대화를 반환합니다."""
        return Conversation.query.filter_by(id=conversation_id).first()
    @staticmethod
    def get_conversation_chat_history(conversation_id: int, limit: int = 20):
        """특정 conversation의 채팅 기록 가져오기"""
        chat_history = ChatHistory.query.filter_by(conversation_id=conversation_id).order_by(ChatHistory.timestamp.asc()).limit(limit).all()
        return chat_history

    @staticmethod
    def get_recent_chat_history(conversation_id, limit=10):
        """
        특정 conversation_id에 대한 최신 chat history를 가져옵니다.
        
        :param conversation_id: 대화 ID
        :param limit: 가져올 대화 수 (기본값: 10)
        :return: 최신 대화 리스트
        """
        chat_history = (
            ChatHistory.query
            .filter_by(conversation_id=conversation_id)  # 특정 conversation_id 필터링
            .order_by(ChatHistory.timestamp.desc())  # 최신 순으로 정렬
            .limit(limit)  # 상위 limit개의 결과만 가져오기
            .all()  # 결과 리스트 반환
        )
        return chat_history
