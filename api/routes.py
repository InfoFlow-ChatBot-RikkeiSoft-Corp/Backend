from flask import Blueprint, request, jsonify, render_template
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
from services.retriever_manager import RetrieverManager
from services.chat_generator import ChatGenerator

# Blueprint 생성
api_bp = Blueprint('api', __name__)

# 클래스 인스턴스 생성
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager()
retriever_manager = RetrieverManager()
chat_generator = ChatGenerator(retriever_manager)

# 질문 제출 및 응답 생성 API
@api_bp.route("/chat/<string:user_id>", methods=["POST"])
def ask(user_id):
    data = request.get_json()
    question = data.get("question")

    if not question:
        return jsonify({"error": "❌ 질문을 입력해주세요!"}), 400

    try:
        context = retriever_manager.retrieve_context(question)
        answer = chat_generator.generate_answer(user_id, question, context)
        return jsonify({"answer": answer}), 200
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": f"❌ 오류 발생: {str(e)}"}), 500
    
@api_bp.route("/", methods=["GET"])
def home():
    return jsonify({
        "Message": "app up and running successfully"
    })

# 벡터 DB 구축 엔드포인트
@api_bp.route("/build-vector-db", methods=["POST"])
def build_vector_db():
    title = request.form.get("title")
    url = request.form.get("url")
    if not title or not url:
        return "❌ 제목과 링크를 모두 입력해주세요!", 400

    try:
        # 문서 가져오기
        doc = document_fetcher.fetch(title, url)

        # 벡터 DB에 추가
        vector_details = vector_db_manager.add_doc_to_db(doc)
        response_html = f"<h3>✅ '{title}' 벡터 DB가 성공적으로 구축되었습니다!</h3><hr>"
        for vector in vector_details:
            response_html += f"""
            <p><b>Vector {vector["vector_index"]}:</b></p>
            <p>Embedding (first 5 elements): {vector["embedding_excerpt"]}</p>
            <p>Document excerpt: {vector["content_excerpt"]}...</p>
            <hr>
            """
        return response_html
    except RuntimeError as e:
        return f"❌ 오류 발생: {str(e)}", 500
