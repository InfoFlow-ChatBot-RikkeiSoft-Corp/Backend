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
from models.models import db, FileMetadata,User, WeblinkMetadata
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
import sqlalchemy as sa
from pytz import timezone
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os
from urllib.parse import unquote
import re

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
    print(f"📍 Received request with username: {username}")
    
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can upload files."}), 403

    # URL 업로드 처리
    if request.is_json:
        data = request.get_json()
        url = data.get('url', '').strip()
        title = data.get('title', '').strip()
        
        print(f"📍 Processing URL upload request")
        print(f"📍 Original JSON data - title: {title}, url: {url}")

        if not url:
            return jsonify({"error": "URL is required"}), 400

        try:
            # URL에서 기본 제목 추출 (title이 비어있는 경우)
            if not title:
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                title = os.path.basename(parsed_url.path) or parsed_url.netloc
                title = title.replace('-', ' ').replace('_', ' ').title()

            print(f"📍 Processed data - title: {title}, url: {url}")

            # 웹링크 메타데이터 생성
            weblink_metadata = WeblinkMetadata(
                title=title,
                url=url,
                user_id=17,  # 임시 user_id
                description=f"Uploaded from {url}"
            )
            
            db.session.add(weblink_metadata)
            db.session.commit()

            # 문서 가져오기 및 벡터 DB에 추가
            try:
                doc = document_fetcher.fetch(title, url)
                if doc:
                    langchain_doc = doc.to_langchain_document()
                    vector_db_manager.vectorstore.add_documents([langchain_doc])
                    vector_db_manager.vectorstore.save_local(vector_db_manager.vectorstore_path)
                    
                    return jsonify({
                        "message": "✅ Weblink successfully uploaded",
                        "metadata": {
                            "id": weblink_metadata.id,
                            "title": weblink_metadata.title,
                            "url": weblink_metadata.url,
                            "upload_date": weblink_metadata.upload_date.isoformat(),
                            "user_id": weblink_metadata.user_id,
                            "description": weblink_metadata.description
                        }
                    }), 201
                else:
                    db.session.delete(weblink_metadata)
                    db.session.commit()
                    return jsonify({"error": "Failed to fetch document content"}), 500

            except Exception as e:
                db.session.delete(weblink_metadata)
                db.session.commit()
                print(f"Error fetching document: {e}")
                return jsonify({"error": f"Failed to fetch document: {str(e)}"}), 500

        except Exception as e:
            db.session.rollback()
            print(f"Error processing URL: {e}")
            return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    # 파일 업로드 처리
    elif 'file' in request.files:
        # Get user object early
        user = User.query.filter_by(username=username).first()
        if not user:
            print(f"❌ User not found for username: {username}")
            return jsonify({"error": "User not found"}), 404

        print(f"✅ Found user: {user.username} (ID: {user.id})")

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

            try:
                # Save file metadata to files table
                file_metadata = FileMetadata(
                    name=file_name,
                    size=file_size,
                    type=file_extension,
                    upload_date=upload_date,
                    user_id=user.id
                )
                db.session.add(file_metadata)
                db.session.commit()

                # Process file and add to vector store
                temp_path = os.path.join("temp_uploads", secure_filename(file_name))
                file.save(temp_path)

                docs = []
                if file_extension == 'docx':
                    docs = document_fetcher.load_docx(temp_path)
                elif file_extension == 'pdf':
                    docs = document_fetcher.load_pdf(temp_path)
                elif file_extension == 'txt':
                    docs = document_fetcher.load_txt(temp_path)

                if not docs:
                    db.session.delete(file_metadata)
                    db.session.commit()
                    return jsonify({"error": "Failed to process document"}), 500

                # Add to vector store
                vector_db_manager.vectorstore.add_documents(docs)
                vector_db_manager.vectorstore.save_local(vector_db_manager.vectorstore_path)

                return jsonify({
                    "message": "File uploaded successfully",
                    "metadata": {
                        "id": file_metadata.id,
                        "name": file_metadata.name,
                        "size": file_metadata.size,
                        "type": file_metadata.type,
                        "upload_date": file_metadata.upload_date.isoformat()
                    }
                }), 201

            except Exception as e:
                db.session.rollback()
                print(f"Error processing file: {e}")
                return jsonify({"error": f"An error occurred: {e}"}), 500

    else:
        return jsonify({"error": "Invalid request. Either file or URL required"}), 400


@file_routes.route('/list_files', methods=['GET'])
def list_files():
    username = request.headers.get('username')
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can view files."}), 403

    print(f"Username received: {username}")

    sort_by = request.args.get('sort_by', 'upload_date')
    sort_order = request.args.get('order', 'desc')

    try:
        # 파일 메타데이터 쿼리
        files_query = FileMetadata.query
        if sort_by in ['name', 'size', 'type', 'upload_date']:
            files_query = files_query.order_by(
                getattr(FileMetadata, sort_by).desc() if sort_order == 'desc' 
                else getattr(FileMetadata, sort_by)
            )
        files = files_query.all()

        # 웹링크 메타데이터 쿼리
        weblinks_query = WeblinkMetadata.query
        if sort_by in ['title', 'upload_date']:  # 웹링크에서 사용 가능한 정렬 필드
            sort_field = 'title' if sort_by == 'name' else sort_by
            weblinks_query = weblinks_query.order_by(
                getattr(WeblinkMetadata, sort_field).desc() if sort_order == 'desc' 
                else getattr(WeblinkMetadata, sort_field)
            )
        weblinks = weblinks_query.all()

        # 통합 문서 리스트 생성
        documents = []
        
        # 파일 메타데이터 추가
        for file in files:
            documents.append({
                "title": file.name,
                "type": "file",
                "size": file.size,
                "file_type": file.type,
                "upload_date": file.upload_date.isoformat()
            })
        
        # 웹링크 메타데이터 추가
        for weblink in weblinks:
            documents.append({
                "title": weblink.title,
                "type": "weblink",
                "url": weblink.url,
                "upload_date": weblink.upload_date.isoformat()
            })

        # 정렬 적용 (날짜 기준)
        if sort_by == 'upload_date':
            documents.sort(
                key=lambda x: x['upload_date'],
                reverse=(sort_order == 'desc')
            )

        return jsonify({"files": documents}), 200
    except Exception as e:
        print(f"Error while listing files: {e}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500



@file_routes.route('/delete/<path:title>', methods=['DELETE'])
def delete_file(title):
    """
    제목을 기준으로 메타데이터와 벡터 데이터를 동기화하여 삭제.
    """
    decoded_title = unquote(title)
    print(f"Received DELETE request for title: {decoded_title}")
    
    username = request.headers.get('username')
    if not username:
        print("Error: Username not provided")
        return jsonify({"error": "Username not provided"}), 400
 
    if not is_admin(username):
        print(f"Access denied for user: {username}")
        return jsonify({"error": "Access denied. Only admins can delete files."}), 403
 
    try:
        # URL인 경우 WeblinkMetadata에서 검색
        weblink_metadata = WeblinkMetadata.query.filter_by(url=decoded_title).first()
        if weblink_metadata:
            title_for_vector = weblink_metadata.title  # 벡터 DB 삭제를 위한 title
            db.session.delete(weblink_metadata)
            print(f"✅ Weblink metadata deleted: {decoded_title}")
        else:
            # 파일인 경우 FileMetadata에서 검색
            file_metadata = FileMetadata.query.filter_by(name=decoded_title).first()
            if file_metadata:
                title_for_vector = os.path.splitext(file_metadata.name)[0]  # 확장자 제거
                db.session.delete(file_metadata)
                print(f"✅ File metadata deleted: {decoded_title}")
            else:
                print(f"Document with title/url '{decoded_title}' not found in database.")
                return jsonify({"error": f"Document with title/url '{decoded_title}' not found"}), 404

        db.session.commit()

        # 벡터 데이터 삭제
        try:
            print(f"Attempting to delete vector data for title: {title_for_vector}")
            result = vector_db_manager.delete_doc_by_title(title_for_vector)
            if result.get("message", "").startswith("✅"):
                print(f"Vector data deleted successfully.")
                return jsonify({
                    "message": f"Document and its vector data deleted successfully"
                }), 200
            else:
                print(f"Vector data could not be deleted. Reason: {result.get('message')}")
                return jsonify({
                    "message": f"Metadata deleted, but vector data could not be deleted. Reason: {result.get('message')}"
                }), 200
        except Exception as vector_error:
            print(f"Warning: Failed to delete vector data. Error: {vector_error}")
            return jsonify({
                "message": "Metadata deleted, but vector data deletion failed.",
                "error": str(vector_error)
            }), 200

    except Exception as e:
        db.session.rollback()
        error_msg = f"Database error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500