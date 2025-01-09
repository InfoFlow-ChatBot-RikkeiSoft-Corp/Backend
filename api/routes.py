from flask import Blueprint, request, jsonify, render_template
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
from services.retriever_manager import RetrieverManager
from services.chat_generator import ChatGenerator
from services.chat_service import ChatService

# Blueprint 생성
api_bp = Blueprint('api', __name__)
chat_bp = Blueprint('chat', __name__)
weblink_bp = Blueprint('weblink', __name__)

# 클래스 인스턴스 생성
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager()
retriever_manager = RetrieverManager()
chat_generator = ChatGenerator(retriever_manager)

# 질문 제출 및 응답 생성 API
@chat_bp.route("/<string:user_id>", methods=["POST"])
def ask(user_id):
    data = request.get_json()
    question = data.get("question")
    print(question)

    if not question:
        return jsonify({"error": "❌ 질문을 입력해주세요!"}), 400

    try:
        context = retriever_manager.retrieve_context(question)
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
