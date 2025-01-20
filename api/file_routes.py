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
        return jsonify({"error": "Access denied. Only admins can upload content."}), 403

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

    # URL 업로드 요청 처리
    elif ('title' in request.form and 'url' in request.form) or request.is_json:
        print("📍 Processing URL upload request")
        
        if request.is_json:
            data = request.get_json()
            title = data.get("title", "").strip()
            url = data.get("url", "").strip()
            print(f"📍 Original JSON data - title: {title}, url: {url}")
            
            # URL이 객체인 경우 실제 URL 추출
            if isinstance(url, dict):
                if 'url' in url:
                    url = url['url']
                elif 'title' in url:  # title 필드에 URL이 있는 경우
                    url = url['title']
                else:
                    print("❌ URL object doesn't contain expected fields")
                    return jsonify({"error": "Invalid URL format"}), 400
            
            # title이 객체인 경우 실제 title 추출
            if isinstance(title, dict):
                if 'title' in title:
                    title = title['title']
                elif 'url' in title:  # url 필드에 title이 있는 경우
                    title = title['url']
                else:
                    print("❌ Title object doesn't contain expected fields")
                    return jsonify({"error": "Invalid title format"}), 400
        else:
            title = request.form.get("title", "").strip()
            url = request.form.get("url", "").strip()

        print(f"📍 Processed data - title: {title}, url: {url}")

        if not title or not url:
            return jsonify({"error": "Both title and URL are required"}), 400

        try:
            # URL 문자열에서 실제 URL 추출 (따옴표로 둘러싸인 URL 추출)
            url_match = re.search(r'https?://[^\s\'"]+', url)
            if url_match:
                url = url_match.group(0)
            
            print(f"📍 Final URL: {url}")

            # URL이 실제 URL 형식인지 확인
            if not url.startswith(('http://', 'https://')):
                print(f"❌ Invalid URL format: {url}")
                return jsonify({"error": "Invalid URL format. URL must start with http:// or https://"}), 400

            # title에서 실제 URL이나 제목 추출
            if isinstance(title, str):
                # URL이 포함된 경우 URL 추출
                url_in_title = re.search(r'https?://[^\s\'"]+', title)
                if url_in_title:
                    title = url_in_title.group(0)
                else:
                    # 객체 형태의 문자열에서 title 또는 url 값 추출
                    title_match = re.search(r'title\s*:\s*"([^"]+)"', title)
                    if title_match:
                        title = title_match.group(1)
                    else:
                        # 기본값으로 URL의 마지막 부분 사용
                        title = url.split('/')[-1]

            print(f"📍 Final title: {title}")

            print(f"📍 Creating weblink metadata for user_id: {user.id}")
            # Save weblink metadata to weblinks table
            weblink = WeblinkMetadata(
                title=title[:500] if len(title) > 500 else title,
                url=url[:1000] if len(url) > 1000 else url,
                user_id=user.id,
                upload_date=current_time,
                description="Uploaded via web interface"
            )
            db.session.add(weblink)
            db.session.commit()
            print(f"✅ Weblink metadata saved with ID: {weblink.id}")

            # Fetch and process the document
            print(f"📍 Fetching document from URL: {url}")
            doc = document_fetcher.fetch(title, url)
            if not doc:
                print(f"❌ Failed to fetch document from URL: {url}")
                db.session.delete(weblink)
                db.session.commit()
                return jsonify({"error": "Failed to fetch document content"}), 400

            # Add to vector store
            print("📍 Adding document to vector store")
            vector_details = vector_db_manager.add_doc_to_db(doc)
            print(f"✅ Document added to vector store: {vector_details}")

            return jsonify({
                "message": "Weblink uploaded successfully",
                "metadata": weblink.to_dict(),
                "vector_details": vector_details
            }), 200

        except Exception as e:
            db.session.rollback()
            error_msg = f"Error processing URL: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"❌ Exception type: {type(e)}")
            print(f"❌ Exception details: {str(e)}")
            return jsonify({"error": error_msg}), 500

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
        # 파일 메타데이터 검색 및 삭제
        file_metadata = FileMetadata.query.filter_by(name=decoded_title).first()
        if file_metadata:
            db.session.delete(file_metadata)
            print(f"✅ File metadata deleted: {decoded_title}")
        
        # 웹링크 메타데이터 검색 및 삭제
        weblink_metadata = WeblinkMetadata.query.filter_by(title=decoded_title).first()
        if weblink_metadata:
            db.session.delete(weblink_metadata)
            print(f"✅ Weblink metadata deleted: {decoded_title}")

        if not file_metadata and not weblink_metadata:
            print(f"Document with title '{decoded_title}' not found in database.")
            return jsonify({"error": f"Document with title '{decoded_title}' not found"}), 404

        db.session.commit()

        # 벡터 데이터 삭제
        try:
            print(f"Attempting to delete vector data for title: {decoded_title}")
            result = vector_db_manager.delete_doc_by_title(decoded_title)
            if result.get("message", "").startswith("✅"):
                print(f"Vector data for title '{decoded_title}' deleted successfully.")
                return jsonify({
                    "message": f"Document '{decoded_title}' and its vector data deleted successfully"
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
        db.session.rollback()
        error_msg = f"Database error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500