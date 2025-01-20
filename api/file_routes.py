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
def upload_file():
    username = request.headers.get('username')
    print(f"\n=== 📤 Upload Request Debug Info ===")
    print(f"Username: {username}")
    
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can upload content."}), 403

    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"❌ User not found: {username}")
        return jsonify({"error": "User not found"}), 404

    print(f"✅ User authenticated: {username}")

    # 파일 업로드 처리
    if 'file' in request.files:
        print("📂 Processing file upload")
        file = request.files['file']
        
        if file.filename == '':
            print("❌ No file selected")
            return jsonify({"error": "No selected file"}), 400

        if not is_allowed_file(file.filename):
            return jsonify({"error": "File type not allowed"}), 400

        # 파일 크기 체크
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            print(f"❌ File too large: {file_size} bytes")
            return jsonify({"error": "File exceeds maximum size of 25 MB"}), 400

        try:
            print(f"📄 Processing file: {file.filename}")
            
            # 파일 메타데이터 저장
            file_metadata = FileMetadata(
                name=file.filename,
                size=file_size,
                type=file.filename.rsplit('.', 1)[1].lower(),
                upload_date=current_time,
                user_id=user.id
            )
            db.session.add(file_metadata)
            db.session.commit()
            print(f"✅ File metadata saved: {file_metadata.id}")

            # 파일 처리 및 벡터 저장
            temp_path = os.path.join("temp_uploads", secure_filename(file.filename))
            file.save(temp_path)
            print(f"✅ File saved to temp location: {temp_path}")

            docs = []
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            if file_extension == 'docx':
                docs = document_fetcher.load_docx(temp_path)
            elif file_extension == 'pdf':
                docs = document_fetcher.load_pdf(temp_path)
            elif file_extension == 'txt':
                docs = document_fetcher.load_txt(temp_path)

            if not docs:
                print("❌ Failed to process document")
                db.session.delete(file_metadata)
                db.session.commit()
                return jsonify({"error": "Failed to process document"}), 500

            print(f"✅ Document processed successfully")
            vector_db_manager.vectorstore.add_documents(docs)
            vector_db_manager.vectorstore.save_local(vector_db_manager.vectorstore_path)
            print(f"✅ Document added to vector store")

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
            print(f"❌ Error processing file: {str(e)}")
            return jsonify({"error": f"An error occurred: {str(e)}"}), 500

    # URL 업로드 요청 처리
    elif ('title' in request.form and 'url' in request.form) or request.is_json:
        print("📍 Processing URL upload request")
        
        if request.is_json:
            data = request.get_json()
            url = data.get("url", "").strip()
            title = data.get("title", "").strip()
            print(f"📍 Original JSON data - title: {title}, url: {url}")
            
            # URL이 객체인 경우 실제 URL 추출
            if isinstance(url, dict):
                if 'url' in url:
                    url = url['url']
                elif 'title' in url:
                    url = url['title']
            
            # title이 비어있는 경우 URL에서 제목 생성
            if not title:
                # URL 경로의 마지막 부분을 title로 사용
                from urllib.parse import urlparse
                path = urlparse(url).path
                title = path.split('/')[-1].replace('-', ' ').title()
                if not title:  # 경로가 비어있는 경우
                    title = urlparse(url).netloc
                print(f"📍 Generated title from URL: {title}")

            print(f"📍 Processed data - title: {title}, url: {url}")
            
            if not url:
                return jsonify({"error": "URL is required"}), 400

            try:
                # 중복 체크
                existing_weblink = WeblinkMetadata.query.filter_by(url=url).first()
                if existing_weblink:
                    print(f"⚠️ Weblink already exists: {url}")
                    return jsonify({
                        "error": "This URL has already been uploaded"
                    }), 400
                    
                # 웹링크 메타데이터 생성
                weblink = WeblinkMetadata(
                    title=title[:1000] if len(title) > 1000 else title,
                    url=url[:1000] if len(url) > 1000 else url,
                    user_id=user.id,
                    upload_date=current_time,
                    description="Uploaded via web interface"
                )
                
                print(f"📍 Creating weblink metadata for user_id: {user.id}")
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

            # 중복 체크
            existing_weblink = WeblinkMetadata.query.filter_by(url=url).first()
            if existing_weblink:
                print(f"⚠️ Weblink already exists: {url}")
                return jsonify({
                    "error": "This URL has already been uploaded"
                }), 400
                
            # 웹링크 메타데이터 생성
            weblink = WeblinkMetadata(
                title=title[:1000] if len(title) > 1000 else title,
                url=url[:1000] if len(url) > 1000 else url,
                user_id=user.id,
                upload_date=current_time,
                description="Uploaded via web interface"
            )
            
            print(f"📍 Creating weblink metadata for user_id: {user.id}")
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

    print("\n=== 📁 File Listing Debug Info ===")
    print(f"Request from username: {username}")

    sort_by = request.args.get('sort_by', 'upload_date')
    sort_order = request.args.get('order', 'desc')
    is_url = request.args.get('is_url', '').lower() == 'true'  # URL 파라미터 추가
    print(f"Sort parameters - by: {sort_by}, order: {sort_order}")
    print(f"is_url parameter: {is_url}")

    try:
        documents = []

        if is_url:
            # 웹링크 메타데이터 쿼리
            weblinks_query = WeblinkMetadata.query
            if sort_by in ['title', 'upload_date']:
                sort_field = 'title' if sort_by == 'name' else sort_by
                weblinks_query = weblinks_query.order_by(
                    getattr(WeblinkMetadata, sort_field).desc() if sort_order == 'desc' 
                    else getattr(WeblinkMetadata, sort_field)
                )
            weblinks = weblinks_query.all()
            print(f"🔗 Found {len(weblinks)} weblinks in database")

            # 웹링크 메타데이터 추가
            for weblink in weblinks:
                doc = {
                    "title": weblink.url,
                    "type": "weblink",
                    "url": weblink.url,
                    "upload_date": weblink.upload_date.isoformat()
                }
                documents.append(doc)
                print(f"🌐 Added weblink: {weblink.url}")

        else:
            # 파일 메타데이터 쿼리
            files_query = FileMetadata.query
            if sort_by in ['name', 'size', 'type', 'upload_date']:
                files_query = files_query.order_by(
                    getattr(FileMetadata, sort_by).desc() if sort_order == 'desc' 
                    else getattr(FileMetadata, sort_by)
                )
            files = files_query.all()
            print(f"📂 Found {len(files)} files in database")

            # 파일 메타데이터 추가
            for file in files:
                doc = {
                    "title": file.name,
                    "type": "file",
                    "size": file.size,
                    "file_type": file.type,
                    "upload_date": file.upload_date.isoformat()
                }
                documents.append(doc)
                print(f"📄 Added file: {file.name} ({file.type})")

        print(f"\n📊 Total documents in response: {len(documents)}")
        if is_url:
            print(f"Weblinks: {len(documents)}")
        else:
            print(f"Files: {len(documents)}")
        print("=== End Debug Info ===\n")

        return jsonify({"files": documents}), 200
    except Exception as e:
        print(f"❌ Error in list_files: {str(e)}")
        return jsonify({"error": f"Database error: {str(e)}"}), 500

@file_routes.route('/delete/<path:title>', methods=['DELETE'])
def delete_file(title):
    """
    제목을 기준으로 메타데이터와 벡터 데이터를 동기화하여 삭제
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
        # URL인 경우 WeblinkMetadata에서 URL로 검색
        weblink = WeblinkMetadata.query.filter_by(url=decoded_title).first()
        if weblink:
            print(f"Found weblink to delete: {weblink.url}")
            db.session.delete(weblink)
            db.session.commit()
            print(f"✅ Weblink deleted from database: {decoded_title}")
            
            # 벡터 데이터 삭제 시도
            try:
                result = vector_db_manager.delete_doc_by_title(weblink.title)
                print(f"Vector store deletion result: {result}")
            except Exception as ve:
                print(f"Warning: Failed to delete from vector store: {ve}")
            
            return jsonify({"message": "Weblink deleted successfully"}), 200
            
        # 파일인 경우 FileMetadata에서 검색
        file = FileMetadata.query.filter_by(name=decoded_title).first()
        if file:
            print(f"Found file to delete: {file.name}")
            db.session.delete(file)
            db.session.commit()
            print(f"✅ File deleted from database: {decoded_title}")
            
            # 벡터 데이터 삭제 시도
            try:
                result = vector_db_manager.delete_doc_by_title(file.name)
                print(f"Vector store deletion result: {result}")
            except Exception as ve:
                print(f"Warning: Failed to delete from vector store: {ve}")
            
            return jsonify({"message": "File deleted successfully"}), 200

        print(f"❌ Document not found in database: {decoded_title}")
        return jsonify({"error": f"Document not found"}), 404

    except Exception as e:
        db.session.rollback()
        error_msg = f"Database error: {str(e)}"
        print(f"❌ {error_msg}")
        return jsonify({"error": error_msg}), 500
