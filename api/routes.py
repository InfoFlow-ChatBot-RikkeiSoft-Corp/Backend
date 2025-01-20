from flask_restx import Namespace, Resource, fields, reqparse
from flask import request, jsonify
from werkzeug.utils import secure_filename
from services.answer_generator import AnswerGenerator
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
from services.retriever_manager import RetrieverManager
from services.chat_generator import ChatGenerator
from services.chat_service import ChatService
from services.RAG_manager import RAGManager
import os
from models.models import WeblinkMetadata, FileMetadata
from flask_sqlalchemy import SQLAlchemy
from models.models import db

# 환경 변수 로드
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# 서비스 객체 생성
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager(openai_api_key=OPENAI_API_KEY, google_api_key=GOOGLE_API_KEY)
answer_generator = AnswerGenerator(model="models/gemini-1.5-flash", temperature=0.7)
retriever_manager = RetrieverManager(vector_db_manager=vector_db_manager)
rag_manager = RAGManager(retriever_manager=retriever_manager, answer_generator=answer_generator, document_fetcher=document_fetcher, vector_db_manager=vector_db_manager)

# Namespaces 생성
chat_ns = Namespace('chat', description='Chat API operations')
weblink_ns = Namespace('weblink', description='Weblink API operations')
pdf_ns = Namespace('pdf', description='PDF Vector DB operations')
rag_ns = Namespace('rag', description='RAG Query operations')
api_ns = Namespace('api', description='General API operations')

# Request Body Models (JSON Body)
ask_question_model = chat_ns.model('AskQuestion', {
    'question': fields.String(required=True, description='Question content'),
})
new_conversation_model = chat_ns.model('NewConversation', {
    'title': fields.String(required=False, description='New conversation title', default="New Conversation"),
})
# Request Body Model Definition
weblink_model = weblink_ns.model('WeblinkUpload', {
    'title': fields.String(required=True, description='Document title'),
    'url': fields.String(required=True, description='Weblink URL'),
})
# Conversation Model (Displayed in Swagger Documentation)
conversation_model = chat_ns.model(
    "Conversation",
    {
        "id": fields.Integer(description="Conversation ID"),
        "user_id": fields.String(description="User ID"),
        "title": fields.String(description="Conversation title"),
        "created_at": fields.DateTime(description="Conversation creation date"),
        "updated_at": fields.DateTime(description="Conversation update date"),
    },
)

# Chat History Model
chat_history_model = chat_ns.model(
    "ChatHistory",
    {
        "id": fields.Integer(description="History ID"),
        "conversation_id": fields.String(description="Conversation ID"),
        "question": fields.String(description="User question"),
        "answer": fields.String(description="AI response"),
        "timestamp": fields.DateTime(description="Creation time"),
    },
)

# Header Parameter Configuration
chat_headers_parser = reqparse.RequestParser()
chat_headers_parser.add_argument('userId', location='headers', required=True, help='User ID header value')
chat_headers_parser.add_argument('conversationId', location='headers', required=True, help='Conversation ID header value')

new_conversation_headers_parser = reqparse.RequestParser()
new_conversation_headers_parser.add_argument('userId', location='headers', required=True, help='User ID header value')

# ======= Chat Namespace =======

@chat_ns.route('/new')
class NewConversation(Resource):
    @chat_ns.expect(new_conversation_headers_parser, new_conversation_model)  # Add request body and headers
    def post(self):
        """Start a new conversation."""
        user_id = request.headers.get("userId")
        title = request.json.get("title", "New Conversation")

        if not user_id:
            return {"error": "User ID is required."}, 400

        try:
            new_conversation_id = ChatService.new_conversation(user_id=user_id, title=title)
            return {"conversation_id": new_conversation_id}, 201
        except Exception as e:
            return {"error": f"❌ Error occurred: {str(e)}"}, 500


@chat_ns.route('/ask')
class AskQuestion(Resource):
    @chat_ns.expect(ask_question_model, chat_headers_parser)
    def post(self):
        """Submit a question and get a response."""
        data = request.get_json()
        question = data.get("question")
        user_id = request.headers.get("userId")
        conversation_id = request.headers.get("conversationId")

        # Debugging logs
        print(f"📨 Received Headers: {request.headers}")
        print(f"📨 user_id: {user_id}, conversation_id: {conversation_id}, question: {question}")

        # Validate input
        if not user_id:
            return {"error": "Missing user_id in headers"}, 400
        if not conversation_id:
            return {"error": "Missing conversation_id in headers"}, 400
        if not question:
            return {"error": "❌ Please enter a question!"}, 400

        try:
            # Step 1: Use `handle_user_query` to check for relevant documents
            results = vector_db_manager.handle_user_query(question)
            
            if not results:
                # No relevant documents found
                return {"error": "No relevant documents found for this query."}, 404

            # Step 2: Generate a response if relevant documents are found
            context = [doc.page_content for doc, score in results]
            retriever = vector_db_manager.get_retriever(search_type="similarity", k=5, similarity_threshold=0.7)
            chat_generator = ChatGenerator(retriever=retriever)
            # Debugging: Log context before generating answer
            print(f"📝 Context for answer generation: {context}")
            
            answer = chat_generator.generate_answer(conversation_id, question, context)

            # Step 3: Save the chat and return the answer
            ChatService.save_chat(conversation_id=conversation_id, user_id=user_id, question=question, answer=answer)
            return {"answer": answer}, 200

        except Exception as e:
            # Handle errors gracefully
            return {"error": f"❌ Error occurred: {str(e)}"}, 500

# 1. Retrieve all conversations of a specific user
@chat_ns.route("/")
class UserConversations(Resource):
    @chat_ns.doc(
        description="Retrieve all conversation lists for a specific user.",
        responses={
            200: "Successfully returned the conversation list.",
            400: "user_id not provided.",
            500: "Server error occurred."
        }
    )
    @chat_ns.param("userId", "User ID (included in headers)", _in="header", required=True)
    def get(self):
        """Return a list of user's conversations."""
        user_id = request.headers.get("userId")
        if not user_id:
            return {"error": "user_id not provided."}, 400

        try:
            conversations = ChatService.get_user_conversations(user_id)
            conversation_list = [
                {
                    "id": conv.id,
                    "user_id": conv.user_id,
                    "title": conv.title or f"Conversation {conv.id}",
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                }
                for conv in conversations
            ]
            return {"conversations": conversation_list}, 200
        except Exception as e:
            return {"error": str(e)}, 500


@chat_ns.route("/<int:conversation_id>/history")
class ConversationChatHistory(Resource):
    @chat_ns.doc(
        description="Retrieve chat history for a specific conversation.",
        params={"limit": "Number of chat history records to retrieve (default: 20)"}
    )
    @chat_ns.param("userId", "User ID (included in headers)", _in="header", required=True)
    @chat_ns.response(200, "Success", [chat_history_model])
    @chat_ns.response(403, "Forbidden")
    @chat_ns.response(500, "Server error")
    def get(self, conversation_id):
        """Return chat history based on conversation ID."""
        user_id = request.headers.get("userId")
        if not user_id:
            return {"error": "user_id not provided."}, 400
        
        limit = request.args.get("limit", default=20, type=int)
        try:
            # 1. Check if the conversation belongs to the user_id
            conversation = ChatService.get_conversation_by_id(conversation_id)
            if not conversation or conversation.user_id != user_id:
                return {"error": "Unauthorized. You cannot access another user's chat history."}, 403

            # 2. Retrieve chat history
            chat_history = ChatService.get_conversation_chat_history(str(conversation_id), limit)
            chat_history_list = [
                {
                    "id": chat.id,
                    "conversation_id": chat.conversation_id,
                    "question": chat.question,
                    "answer": chat.answer,
                    "timestamp": chat.timestamp.isoformat(),
                }
                for chat in chat_history
            ]
            return {"chat_history": chat_history_list}, 200
        except Exception as e:
            return {"error": str(e)}, 500

# ======= Weblink Namespace =======
@weblink_ns.route('/upload')
class WeblinkUpload(Resource):
    @weblink_ns.expect(weblink_model)
    def post(self):
        """Upload a weblink document."""
        data = request.get_json()
        title = data.get("title")
        url = data.get("url")
        user_id = request.headers.get("userId")

        if not title or not url:
            return {"error": "❌ Please enter both the title and the link!"}, 400

        try:
            # WeblinkMetadata 사용
            weblink = WeblinkMetadata(
                title=title,
                url=url,
                user_id=user_id
            )
            db.session.add(weblink)
            db.session.commit()

            doc = document_fetcher.fetch(title, url)
            vector_details = vector_db_manager.add_doc_to_db(doc)
            
            return {
                "message": "✅ Weblink successfully uploaded",
                "metadata": weblink.to_dict(),
                "vector_details": vector_details
            }, 200
        except Exception as e:
            db.session.rollback()
            return {"error": f"❌ Error occurred: {str(e)}"}, 500


# ======= PDF Namespace =======
@pdf_ns.route('/upload')
class PDFUpload(Resource):
    def post(self):
        """Upload a PDF file to vector DB."""
        if 'file' not in request.files:
            return jsonify({"error": "❌ No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "❌ No file selected"}), 400

        if not file.filename.endswith('.pdf'):
            return jsonify({"error": "❌ Only PDF files are allowed"}), 400

        # 파일 메타데이터를 files 테이블에 저장
        try:
            file_metadata = FileMetadata(
                name=file.filename,
                size=len(file.read()),
                type='pdf',
                user_id=request.headers.get('userId', 1)  # 기본값 1 설정
            )
            file.seek(0)  # 파일 포인터를 다시 처음으로
            
            db.session.add(file_metadata)
            db.session.commit()

            # 벡터 DB 처리
            file_path = os.path.join("temp_uploads", secure_filename(file.filename))
            file.save(file_path)

            docs = document_fetcher.load_pdf(file_path)
            if docs:
                vector_details = vector_db_manager.add_pdf_to_db(docs)
                return jsonify({
                    "message": "✅ PDF 문서가 성공적으로 처리되었습니다.", 
                    "metadata": {
                        "id": file_metadata.id,
                        "name": file_metadata.name,
                        "size": file_metadata.size,
                        "type": file_metadata.type,
                        "upload_date": file_metadata.upload_date.isoformat()
                    },
                    "vector_info": vector_details
                }), 200
            else:
                db.session.delete(file_metadata)
                db.session.commit()
                return jsonify({"error": "❌ PDF에서 텍스트를 추출할 수 없습니다."}), 500

        except Exception as e:
            db.session.rollback()  # 에러 발생 시 트랜잭션 롤백
            return jsonify({"error": f"❌ Error processing PDF: {str(e)}"}), 500


# ======= RAG Namespace =======
@rag_ns.route('/query')
class RAGQuery(Resource):
    def post(self):
        """Handle RAG queries and return a response."""
        data = request.get_json()
        query = data.get("query")
        retriever_type = data.get("retriever_type", "similarity")
        k = data.get("k", 5)
        similarity_threshold = data.get("similarity_threshold", 0.7)

        if not query:
            return jsonify({"error": "❌ Query is required"}), 400

        try:
            answer = rag_manager.query(query, retriever_type, k, similarity_threshold)
            return jsonify({"query": query, "answer": answer}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


# ======= General API Namespace =======
@api_ns.route('/')
class Home(Resource):
    def get(self):
        """Health check route."""
        return jsonify({"Message": "App up and running successfully"}), 200


@api_ns.route('/delete_doc')
class DeleteDoc(Resource):
    def post(self):
        """Delete a document by title."""
        data = request.get_json()
        title = data.get("title")

        if not title:
            return jsonify({"error": "❌ title을 입력해주세요!"}), 400

        result = vector_db_manager.delete_doc_by_title(title)
        return jsonify(result), 200
