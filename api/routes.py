from flask import Blueprint, request, jsonify, render_template
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
from services.retriever_manager import RetrieverManager
from services.answer_generator import AnswerGenerator
from services.rag_service import RAGService

# Blueprint 생성
api_bp = Blueprint('api', __name__)

# 클래스 인스턴스 생성
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager()
retriever_manager = RetrieverManager()
answer_generator = AnswerGenerator(model="models/gemini-1.5-flash", temperature=0)
rag_service = RAGService(retriever_manager, answer_generator)

# 질문 제출 및 응답 생성 API
@api_bp.route("/chat", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question")

    if not question:
        return jsonify({"error": "❌ 질문을 입력해주세요!"}), 400

    try:
        answer = rag_service.generate_response(question)
        return jsonify({"answer": answer}), 200
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": f"❌ 오류 발생: {str(e)}"}), 500
    
@api_bp.route("/", methods=["GET"])
def home():
    docs_list = vector_db_manager.get_submitted_docs()  # 제출된 뉴스 문서 리스트
    return render_template("index.html", docs_list=docs_list)

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
