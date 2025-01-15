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

# 요청 바디 모델 (JSON Body)
ask_question_model = chat_ns.model('AskQuestion', {
    'question': fields.String(required=True, description='질문 내용'),
})
new_conversation_model = chat_ns.model('NewConversation', {
    'title': fields.String(required=False, description='새 채팅 제목', default="새 채팅"),
})
# 요청 바디 모델 정의
weblink_model = weblink_ns.model('WeblinkUpload', {
    'title': fields.String(required=True, description='문서 제목'),
    'url': fields.String(required=True, description='웹 링크 URL'),
})

# 헤더 파라미터 설정
chat_headers_parser = reqparse.RequestParser()
chat_headers_parser.add_argument('userId', location='headers', required=True, help='User ID 헤더 값')
chat_headers_parser.add_argument('conversationId', location='headers', required=True, help='Conversation ID 헤더 값')

new_conversation_headers_parser = reqparse.RequestParser()
new_conversation_headers_parser.add_argument('userId', location='headers', required=True, help='User ID 헤더 값')

# ======= Chat Namespace =======

@chat_ns.route('/new')
class NewConversation(Resource):
    @chat_ns.expect(new_conversation_headers_parser, new_conversation_model)  # 요청 바디와 헤더 추가
    def post(self):
        """Start a new conversation."""
        user_id = request.headers.get("userId")
        title = request.json.get("title", "새 채팅")

        if not user_id:
            return {"error": "사용자 ID가 필요합니다."}, 400

        try:
            new_conversation_id = ChatService.new_conversation(user_id=user_id, title=title)
            return {"conversation_id": new_conversation_id}, 201
        except Exception as e:
            return {"error": f"❌ 오류 발생: {str(e)}"}, 500


@chat_ns.route('/ask')
class AskQuestion(Resource):
    @chat_ns.expect(ask_question_model, chat_headers_parser)  # 요청 바디와 헤더 명세
    def post(self):
        """Submit a question and get a response."""
        data = request.get_json()
        question = data.get("question")
        user_id = request.headers.get("userId")
        conversation_id = request.headers.get("conversationId")

        # 디버깅 로그 추가
        print(f"📨 Received Headers: {request.headers}")
        print(f"📨 user_id: {user_id}, conversation_id: {conversation_id}, question: {question}")

        # 필수 값 확인
        if not user_id:
            return {"error": "Missing user_id in headers"}, 400
        if not conversation_id:
            return {"error": "Missing conversation_id in headers"}, 400
        if not question:
            return {"error": "❌ 질문을 입력해주세요!"}, 400

        try:
            context = retriever_manager.retrieve_context(question)
            retriever = vector_db_manager.get_retriever(search_type="similarity", k=5, similarity_threshold=0.7)
            chat_generator = ChatGenerator(retriever=retriever)
            answer = chat_generator.generate_answer(conversation_id, question, context)
            ChatService.save_chat(conversation_id=conversation_id, user_id=user_id, question=question, answer=answer)
            return {"answer": answer}, 200
        except Exception as e:
            return {"error": f"❌ 오류 발생: {str(e)}"}, 500


@chat_ns.route('/<string:user_id>')
class ChatHistory(Resource):
    def get(self, user_id):
        """Get chat history for a user."""
        chat_history = ChatService.get_chat_history(user_id)
        if not chat_history:
            return jsonify({"message": "🔍 채팅 기록이 없습니다."}), 404

        return jsonify(
            [
                {"question": chat.question, "answer": chat.answer, "timestamp": chat.timestamp.isoformat()}
                for chat in chat_history
            ]
        ), 200


# ======= Weblink Namespace (example) =======
@weblink_ns.route('/upload')
class WeblinkUpload(Resource):
    @weblink_ns.expect(weblink_model)  # 요청 바디와 헤더 추가
    def post(self):
        """Upload a weblink document."""
        data = request.get_json()  # JSON 데이터 가져오기
        title = data.get("title")
        url = data.get("url")

        if not title or not url:
            return {"error": "❌ 제목과 링크를 모두 입력해주세요!"}, 400

        try:
            doc = document_fetcher.fetch(title, url)
            vector_details = vector_db_manager.add_doc_to_db(doc)
            return {"title": title, "vector_details": vector_details}, 200
        except Exception as e:
            return {"error": f"❌ 오류 발생: {str(e)}"}, 500


# ======= PDF Namespace =======
@pdf_ns.route('/upload')
class PDFUpload(Resource):
    def post(self):
        """Upload a PDF document and build vector DB."""
        if "file" not in request.files:
            return jsonify({"error": "❌ PDF 파일을 업로드해주세요!"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "❌ 파일 이름이 비어 있습니다."}), 400

        file_path = os.path.join("temp_uploads", secure_filename(file.filename))
        file.save(file_path)

        try:
            docs = document_fetcher.load_pdf(file_path)
            if docs:
                vector_details = vector_db_manager.add_pdf_to_db(docs)
                return jsonify({"message": "✅ PDF 문서가 성공적으로 처리되었습니다.", "vector_info": vector_details}), 200
            else:
                return jsonify({"error": "❌ PDF에서 텍스트를 추출할 수 없습니다."}), 500
        except Exception as e:
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
