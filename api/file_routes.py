from flask import Blueprint, request, jsonify
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from services.answer_generator import AnswerGenerator
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
from services.retriever_manager import RetrieverManager
from services.chat_generator import ChatGenerator
from services.chat_service import ChatService
from services.RAG_manager import RAGManager
from werkzeug.utils import secure_filename
from datetime import datetime
from models.models import db, FileMetadata,User
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
import sqlalchemy as sa
from pytz import timezone
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
from urllib.parse import unquote

# Load environment variables
load_dotenv()

# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

from dotenv import load_dotenv
import os
import uuid

file_routes = Blueprint('file_routes', __name__)

ALLOWED_FILE_TYPES = {'txt', 'docx', 'pdf'}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

tz = timezone("Asia/Ho_Chi_Minh")  # Replace with your desired time zone
current_time = datetime.now(tz)
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager(
    openai_api_key=OPENAI_API_KEY,
    google_api_key=GOOGLE_API_KEY
)

# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Ensure at least one API key is provided
if not (GOOGLE_API_KEY or OPENAI_API_KEY):
    raise ValueError("Neither GOOGLE_API_KEY nor OPENAI_API_KEY is set in the environment variables.")

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


def is_allowed_file(file_name):
    return '.' in file_name and file_name.rsplit('.', 1)[1].lower() in ALLOWED_FILE_TYPES

def is_admin(username):
    result = db.session.execute(
        sa.text("SELECT role FROM company_employee WHERE email = :email"),
        {'email': username}
    ).mappings().fetchone()

    return result and result['role'] == 'admin'

@file_routes.route('/upload', methods=['POST'])
def upload_content():
    username = request.headers.get('username')
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can upload content."}), 403

    # 파일 업로드 요청 처리
    if 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        if not file:
            return jsonify({"error": "No file provided"}), 400

        if not is_allowed_file(file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        file.seek(0, 2)  # Move to end of file
        file_size = file.tell()
        file.seek(0)

        if file_size > MAX_FILE_SIZE:
            return jsonify({"error": "File exceeds maximum size of 25 MB"}), 400

        file_name = file.filename
        file_extension = file_name.rsplit('.', 1)[1].lower()
        upload_date = current_time

        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        try:
            # Save file temporarily
            temp_path = os.path.join("temp_uploads", secure_filename(file_name))
            file.save(temp_path)

            # Initialize docs variable
            docs = []

            # Process the document based on file extension
            if file_extension == 'docx':
                docs = document_fetcher.load_docx(temp_path)
            elif file_extension == 'pdf':
                docs = document_fetcher.load_pdf(temp_path)
            elif file_extension == 'txt':
                docs = document_fetcher.load_txt(temp_path)
            else:
                return jsonify({"error": "Unsupported file format"}), 400

            # Validate docs
            if not docs or not isinstance(docs, list):
                raise RuntimeError("Failed to process document. 'docs' is invalid or empty.")

            # Process documents into text chunks
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            documents = []

            for doc in docs:
                if hasattr(doc, 'page_content') and doc.page_content:
                    splits = text_splitter.split_text(doc.page_content)
                    for split in splits:
                        documents.append(
                            Document(
                                page_content=split,
                                metadata={
                                    "title": doc.metadata.get("title", file_name),
                                    "source": doc.metadata.get("source", temp_path),
                                }
                            )
                        )
                else:
                    # Handle missing page_content
                    print(f"❌ Warning: Docs object does not have 'page_content' attribute. Adding default content.")
                    documents.append(
                        Document(
                            page_content="No content available.",
                            metadata={
                                "title": doc.metadata.get("title", file_name),
                                "source": doc.metadata.get("source", temp_path),
                            }
                        )
                    )

            # Add documents to vector store
            vector_db_manager.vectorstore.add_documents(documents)
            vector_db_manager.vectorstore.save_local(vector_db_manager.vectorstore_path)

            # Save metadata to the database
            metadata = FileMetadata(
                name=file_name, size=file_size, type=file_extension, upload_date=upload_date, user_id=user.id
            )
            db.session.add(metadata)
            db.session.commit()

            return jsonify({"message": "File uploaded successfully", "document_count": len(documents)}), 201
        except Exception as e:
            print(f"Error processing file: {e}")
            return jsonify({"error": f"An error occurred: {e}"}), 500

    # URL 업로드 요청 처리
    elif ('title' in request.form and 'url' in request.form) or request.is_json:
        if request.is_json:
            # JSON 요청 처리
            data = request.get_json()
            title = data.get("title")
            url = data.get("url")
        else:
            # form 요청 처리
            title = request.form.get("title")
            url = request.form.get("url")

        print(f"Received Weblink - Title: {title}, URL: {url}")  # 로그 추가

        if not title or not url:
            return jsonify({"error": "Title and URL are required"}), 400

        user = User.query.filter_by(username=username).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        try:
            # URL을 사용하여 문서 가져오기 및 벡터 DB 추가
            doc = document_fetcher.fetch(title, url)
            vector_details = vector_db_manager.add_doc_to_db(doc)

            # 메타데이터 저장
            metadata = FileMetadata(
                name=title,
                size=0,  # URL에서 파일 크기를 알 수 없으므로 기본값 설정
                type="url",
                upload_date=current_time,
                user_id=user.id
            )
            db.session.add(metadata)
            db.session.commit()

            return jsonify({
                "message": f"URL '{title}' has been successfully added to the vector database.",
                "vector_info": vector_details
            }), 200

        except RuntimeError as e:
            db.session.rollback()
            return jsonify({"error": f"Failed to process URL: {str(e)}"}), 500

    # 유효하지 않은 요청 처리
    else:
        return jsonify({"error": "Invalid request. Provide a file or title and URL."}), 400


@file_routes.route('/list_files', methods=['GET'])
def list_files():
    username = request.headers.get('username')
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can view files."}), 403

    print(f"Username received: {username}")

    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('order', 'asc')
    file_type = request.args.get('type')  # 추가된 타입 필터
    is_url = request.args.get('is_url')  # URL 여부 필터
    print(f"is_url: {is_url}")

    if sort_by not in ['name', 'size', 'type', 'upload_date']:
        return jsonify({"error": "Invalid sort parameter"}), 400

    try:
        # 기본 쿼리 생성
        query = FileMetadata.query

        # 타입 필터 적용
        if file_type:
            query = query.filter(FileMetadata.type == file_type)

        # URL 여부 필터 적용
        if is_url is not None:
            is_url = is_url.lower() == 'true'
            query = query.filter(FileMetadata.type == 'url' if is_url else FileMetadata.type != 'url')

        # 정렬 조건 적용
        query = query.order_by(
            getattr(FileMetadata, sort_by).asc() if sort_order == 'asc' else getattr(FileMetadata, sort_by).desc()
        )

        print(f"Sorting by: {sort_by}, Order: {sort_order}, Type: {file_type}, Is URL: {is_url}")
        files = query.all()

        # 파일 메타데이터를 제목(title) 중심으로 구성
        file_list = [
            {
                "title": file.name,  # 제목을 name 필드로 반환
                "size": file.size,
                "type": file.type,
                "upload_date": file.upload_date.isoformat()
            }
            for file in files
        ]

        return jsonify({"files": file_list}), 200
    except Exception as e:
        print(f"Error while listing files: {e}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@file_routes.route('/delete/<path:title>', methods=['DELETE'])
def delete_file(title):
    """
    제목을 기준으로 메타데이터와 벡터 데이터를 동기화하여 삭제.
    """

    # 디코딩된 title 사용
    decoded_title = unquote(title)
    print(f"Received DELETE request for title: {decoded_title}")
    username = request.headers.get('username')
    if not username:
        print("Error: Username not provided")
        return jsonify({"error": "Username not provided"}), 400
 
    if not is_admin(username):
        print(f"Access denied for user: {username}")
        return jsonify({"error": "Access denied. Only admins can delete files."}), 403
 
    # 제목을 기준으로 메타데이터 검색
    print(f"Searching for metadata with name: {decoded_title}")
    metadata = FileMetadata.query.filter_by(name=decoded_title).first()
    if not metadata:

        print(f"File with title '{decoded_title}' not found in database.")
        return jsonify({"error": f"File with title '{decoded_title}' not found"}), 404
    try:
        # 데이터베이스에서 메타데이터 삭제
        db.session.delete(metadata)
        db.session.commit()

        print(f"Metadata for file '{decoded_title}' deleted successfully.")

        # 벡터 데이터 삭제
        try:
            print(f"Attempting to delete vector data for title: {decoded_title}")
            result = vector_db_manager.delete_doc_by_title(decoded_title)
            if result.get("message", "").startswith("✅"):
                print(f"Vector data for title '{decoded_title}' deleted successfully.")
                return jsonify({
                    "message": f"File '{decoded_title}' and its vector data deleted successfully"
                }), 200
            else:
                print(f"Vector data for title '{decoded_title}' could not be deleted. Reason: {result.get('message')}")
                return jsonify({
                    "message": f"Metadata deleted, but vector data could not be deleted. Reason: {result.get('message')}"
                }), 200
        except Exception as vector_error:
            print(f"Warning: Failed to delete vector data for title '{decoded_title}'. Error: {vector_error}")
            return jsonify({
                "message": "Metadata deleted, but vector data deletion failed.",
                "error": str(vector_error)
            }), 200
 
    except Exception as e:
        print(f"Database error: {str(e)}")
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500