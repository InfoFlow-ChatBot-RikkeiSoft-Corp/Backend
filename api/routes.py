from flask import Blueprint, request, jsonify, render_template
from services.answer_generator import AnswerGenerator
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
from services.retriever_manager import RetrieverManager
from services.chat_generator import ChatGenerator
from services.chat_service import ChatService
from services.RAG_manager import RAGManager
from werkzeug.utils import secure_filename

from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Ensure at least one API key is provided
if not (GOOGLE_API_KEY or OPENAI_API_KEY):
    raise ValueError("Neither GOOGLE_API_KEY nor OPENAI_API_KEY is set in the environment variables.")

# Blueprint 생성
api_bp = Blueprint('api', __name__)
chat_bp = Blueprint('chat', __name__)
weblink_bp = Blueprint('weblink', __name__)
pdf_bp = Blueprint('pdf', __name__)
rag_bp = Blueprint('rag', __name__)

# 클래스 인스턴스 생성
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager(
    openai_api_key=OPENAI_API_KEY,
    google_api_key=GOOGLE_API_KEY
)
answer_generator = AnswerGenerator(
    model="models/gemini-1.5-flash", 
    temperature=0.7               
)
retriever_manager = RetrieverManager(vector_db_manager=vector_db_manager)
rag_manager = RAGManager(
    retriever_manager=retriever_manager,
    answer_generator=answer_generator,
    document_fetcher=document_fetcher,
    vector_db_manager=vector_db_manager
)

# 질문 제출 및 응답 생성 API
@chat_bp.route("/<string:user_id>", methods=["POST"])
def ask(user_id):
    data = request.get_json()
    question = data.get("question")
    print(question)

    if not question:
        return jsonify({"error": "❌ 질문을 입력해주세요!"}), 400

    try:
        chat_generator = ChatGenerator(retriever_manager)
        context = retriever_manager.retrieve_context(question, 3)
        answer = chat_generator.generate_answer(user_id, question, context)
        ChatService.save_chat(user_id=user_id, question=question, answer=answer)
        return jsonify({"answer": answer}), 200
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": f"❌ 오류 발생: {str(e)}"}), 500
# 채팅 기록 조회 엔드포인트
@chat_bp.route("/<string:user_id>", methods=["GET"])
def get_chat_history(user_id):
    chat_history = ChatService.get_chat_history(user_id)
    if not chat_history:
        return jsonify({"message": "🔍 채팅 기록이 없습니다."}), 404

    return jsonify(
        [
            {"question": chat.question, "answer": chat.answer, "timestamp": chat.timestamp.isoformat()}
            for chat in chat_history
        ]
    ), 200  
@api_bp.route("/", methods=["GET"])
def home():
    return jsonify({
        "Message": "app up and running successfully"
    })

# 벡터 DB 구축 엔드포인트
@weblink_bp.route("/upload", methods=["POST"])
def weblink_build_vector_db():
    title = request.form.get("title")
    url = request.form.get("url")
    if not title or not url:
        return "❌ 제목과 링크를 모두 입력해주세요!", 400

    try:
        # 문서 가져오기
        doc = document_fetcher.fetch(title, url)

        # 벡터 DB에 추가
        vector_details = vector_db_manager.add_doc_to_db(doc)
        print(f"✅ '{title}' 벡터 DB에 성공적으로 저장되었습니다.")
        print("벡터 정보:", vector_details)
        
        return jsonify({"title": title}), 200
    except RuntimeError as e:
        return f"❌ 오류 발생: {str(e)}", 500


@rag_bp.route('/query', methods=['POST'])
def rag_query():
    """Handle RAG queries and return the response."""
    try:
        data = request.get_json()
        query = data.get("query")
        retriever_type = data.get("retriever_type", "similarity")
        k = data.get("k", 5)
        similarity_threshold = data.get("similarity_threshold", 0.7)

        if not query:
            return jsonify({"error": "Query is required"}), 400

        # Use RAGManager to process the query
        answer = rag_manager.query(query, retriever_type, k, similarity_threshold)
        return jsonify({"query": query, "answer": answer}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# 벡터 DB 구축 엔드포인트
@pdf_bp.route("/upload", methods=["POST"])
def pdf_build_vector_db():
    if "file" not in request.files:
        return jsonify({"error": "❌ PDF 파일을 업로드해주세요!"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "❌ 파일 이름이 비어 있습니다."}), 400

    file_path = os.path.join("temp_uploads", secure_filename(file.filename))
    file.save(file_path)

    try:
        # 문서 가져오기
        docs = document_fetcher.load_pdf(file_path)

        if docs:
            vector_details = vector_db_manager.add_pdf_to_db(docs)
                # vector_details_list.append(vector_details)
            return jsonify({"message": "✅ PDF 문서가 성공적으로 처리되었습니다.", "vector_info": vector_details}), 200
        else:
            return jsonify({"error": "❌ PDF에서 텍스트를 추출할 수 없습니다."}), 500
    except Exception as e:
        return jsonify({"error": f"❌ Error processing PDF: {str(e)}"}), 500
