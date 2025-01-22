from flask_restx import Namespace, Resource, fields, reqparse
from flask import request
from services.answer_generator import AnswerGenerator
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
from services.retriever_manager import RetrieverManager
from services.RAG_manager import RAGManager
from werkzeug.utils import secure_filename
from datetime import datetime
from models.models import db, FileMetadata,User, WeblinkMetadata
import sqlalchemy as sa
from pytz import timezone
from werkzeug.datastructures import FileStorage
import os
from urllib.parse import unquote


# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

file_ns = Namespace('file', description="File API operations")

ALLOWED_FILE_TYPES = {'txt', 'docx', 'pdf'}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

tz = timezone("Asia/Ho_Chi_Minh")  # Replace with your desired time zone
current_time = datetime.now(tz)
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager(
    openai_api_key=OPENAI_API_KEY,
    google_api_key=GOOGLE_API_KEY
)

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

# URL 파라미터와 헤더 정의
list_files_parser = reqparse.RequestParser()
list_files_parser.add_argument('username', location='headers', required=True, help='Username for authentication')
list_files_parser.add_argument('sort_by', location='args', required=False, default='upload_date', help='Sort field (e.g., name, size, type, upload_date)')
list_files_parser.add_argument('order', location='args', required=False, default='desc', help='Sort order (asc or desc)')
list_files_parser.add_argument('is_url', location='args', required=False, type=str, default='false', help='Filter for weblinks only (true or false)')

# Swagger 모델 (응답 정의)
file_metadata_model = file_ns.model('FileMetadata', {
    'title': fields.String(description='Title of the file or URL'),
    'type': fields.String(description='Type (file or weblink)'),
    'size': fields.Integer(description='Size of the file in bytes', required=False),
    'file_type': fields.String(description='File extension', required=False),
    'url': fields.String(description='URL of the weblink', required=False),
    'upload_date': fields.String(description='Upload date in ISO format'),
})

# 삭제 API 요청 파라미터 정의
delete_parser = reqparse.RequestParser()
delete_parser.add_argument('username', location='headers', required=True, help='Username for authentication')

# Swagger 응답 모델 정의
delete_response_model = file_ns.model('DeleteResponse', {
    'message': fields.String(description='Deletion success message')
})

weblink_metadata_model = file_ns.model('WeblinkMetadata', {
    'title': fields.String(description='Weblink title'),
    'url': fields.String(description='Weblink URL'),
    'upload_date': fields.String(description='Upload date in ISO format')
})

upload_parser = reqparse.RequestParser()
upload_parser.add_argument('username', location='headers', required=True, help='Username for authentication')
upload_parser.add_argument('file', type=FileStorage, location='files', required=False, help='File to upload')
upload_parser.add_argument('title', type=str, required=False, help='Title for the URL')
upload_parser.add_argument('url', type=str, required=False, help='URL to upload')


def is_allowed_file(file_name):
    return '.' in file_name and file_name.rsplit('.', 1)[1].lower() in ALLOWED_FILE_TYPES

def is_admin(username):
    result = db.session.execute(
        sa.text("SELECT role FROM company_employee WHERE email = :email"),
        {'email': username}
    ).mappings().fetchone()

    return result and result['role'] == 'admin'
def process_file(file, user):
    """Process the uploaded file and add it to the vector store."""
    file_name = secure_filename(file.filename)
    file_size = len(file.read())
    file.seek(0)

    if file_size > 25 * 1024 * 1024:  # 25 MB
        raise ValueError("File exceeds maximum size of 25 MB")

    file_metadata = FileMetadata(
        name=file_name,
        size=file_size,
        type=file_name.rsplit('.', 1)[1].lower(),
        upload_date=datetime.utcnow(),
        user_id=user.id
    )

    # Save file metadata
    db.session.add(file_metadata)
    db.session.commit()

    # Save file locally
    temp_path = os.path.join("temp_uploads", file_name)
    file.save(temp_path)

    # Process file and add to vector store
    docs = []
    file_extension = file_name.rsplit('.', 1)[1].lower()
    if file_extension == 'docx':
        docs = document_fetcher.load_docx(temp_path)
    elif file_extension == 'pdf':
        docs = document_fetcher.load_pdf(temp_path)
    elif file_extension == 'txt':
        docs = document_fetcher.load_txt(temp_path)

    if not docs:
        db.session.delete(file_metadata)
        db.session.commit()
        raise ValueError("Failed to process document")

    vector_db_manager.vectorstore.add_documents(docs)
    vector_db_manager.vectorstore.save_local(vector_db_manager.vectorstore_path)

    return file_metadata

@file_ns.route('/upload')
class UploadFile(Resource):
    @file_ns.expect(upload_parser)
    @file_ns.response(201, 'File uploaded successfully', model=file_metadata_model)
    @file_ns.response(400, 'Bad Request')
    @file_ns.response(403, 'Access denied')
    @file_ns.response(500, 'Internal Server Error')
    def post(self):
        """Upload a file or a URL."""
        try:
            print("\n=== 📤 Upload Request Debug Info ===")
            
            # 전체 요청 데이터 출력
            print("Request Data:")
            print(f"Files: {request.files}")
            print(f"Form: {request.form}")
            print(f"Headers: {request.headers}")
            print(f"JSON: {request.get_json(silent=True)}")
            
            args = upload_parser.parse_args()
            username = args['username']
            print(f"Parsed username: {username}")

            if not username:
                print("❌ Error: Username not provided")
                return {"error": "Username not provided"}, 400

            if not is_admin(username):
                print(f"❌ Access denied for user: {username}")
                return {"error": "Access denied. Only admins can upload content."}, 403

            user = User.query.filter_by(username=username).first()
            if not user:
                print(f"❌ User not found: {username}")
                return {"error": "User not found"}, 404

            print(f"✅ User authenticated: {username}")

            # JSON 데이터 처리
            json_data = request.get_json(silent=True)
            if json_data and 'url' in json_data:
                url = json_data['url']
                title = json_data.get('title') or url.split('/')[-1].replace('-', ' ').title()
                
                print(f"\n🔗 Processing URL upload from JSON:")
                print(f"URL: {url}")
                print(f"Title: {title}")

                if not url.startswith(('http://', 'https://')):
                    print("❌ Invalid URL format")
                    return {"error": "Invalid URL format. URL must start with http:// or https://"}, 400

                try:
                    weblink = WeblinkMetadata(
                        title=title[:1000],
                        url=url[:1000],
                        user_id=user.id,
                        upload_date=datetime.utcnow()
                    )
                    db.session.add(weblink)
                    db.session.commit()
                    print("✅ URL metadata saved")

                    doc = document_fetcher.fetch(title, url)
                    vector_db_manager.add_doc_to_db(doc)
                    print("✅ Document added to vector database")

                    return {
                        "message": "URL uploaded successfully",
                        "metadata": weblink.to_dict()
                    }, 201

                except Exception as e:
                    print(f"❌ URL processing error: {str(e)}")
                    db.session.rollback()
                    return {"error": f"URL processing error: {str(e)}"}, 500

            # 파일 업로드 처리
            elif 'file' in request.files:
                file = request.files['file']
                print(f"\n📁 Processing file upload: {file.filename}")
                
                if not file or not file.filename:
                    print("❌ No file selected")
                    return {"error": "No file selected"}, 400
                
                if not is_allowed_file(file.filename):
                    print(f"❌ Invalid file type: {file.filename}")
                    return {"error": f"Invalid file type. Allowed types are: {', '.join(ALLOWED_FILE_TYPES)}"}, 400

                try:
                    file_metadata = process_file(file, user)
                    print(f"✅ File processed successfully: {file_metadata.name}")
                    return {
                        "message": "File uploaded successfully",
                        "metadata": {
                            "id": file_metadata.id,
                            "name": file_metadata.name,
                            "size": file_metadata.size,
                            "type": file_metadata.type,
                            "upload_date": file_metadata.upload_date.isoformat()
                        }
                    }, 201

                except Exception as e:
                    print(f"❌ File processing error: {str(e)}")
                    return {"error": f"File processing error: {str(e)}"}, 500

            # Form 데이터에서 URL 처리
            elif request.form.get('url'):
                url = request.form.get('url')
                title = request.form.get('title') or url.split('/')[-1].replace('-', ' ').title()
                
                print(f"\n🔗 Processing URL upload:")
                print(f"URL: {url}")
                print(f"Title: {title}")

                if not url.startswith(('http://', 'https://')):
                    print("❌ Invalid URL format")
                    return {"error": "Invalid URL format. URL must start with http:// or https://"}, 400

                try:
                    weblink = WeblinkMetadata(
                        title=title[:1000],
                        url=url[:1000],
                        user_id=user.id,
                        upload_date=datetime.utcnow()
                    )
                    db.session.add(weblink)

                    db.session.commit()
                    print("✅ URL metadata saved")

                    doc = document_fetcher.fetch(title, url)
                    vector_db_manager.add_doc_to_db(doc)
                    print("✅ Document added to vector database")

                    return {
                        "message": "URL uploaded successfully",
                        "metadata": weblink.to_dict()
                    }, 201

                except Exception as e:
                    print(f"❌ URL processing error: {str(e)}")
                    db.session.rollback()
                    return {"error": f"URL processing error: {str(e)}"}, 500

            else:
                print("❌ No file or URL provided")
                return {"error": "Please provide either a file or URL"}, 400

        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            return {"error": f"An unexpected error occurred: {str(e)}"}, 500

        finally:
            print("=== End Upload Debug Info ===\n")


@file_ns.route('/list_files')
class ListFiles(Resource):
    @file_ns.expect(list_files_parser)  # 헤더와 URL 파라미터 정의
    @file_ns.response(200, 'Success', model=[file_metadata_model])
    @file_ns.response(400, 'Bad Request')
    @file_ns.response(403, 'Access denied')
    @file_ns.response(500, 'Database error')
    def get(self):
        """List all files and weblinks."""
        args = list_files_parser.parse_args()  # 헤더와 URL 파라미터 파싱
        username = args['username']
        sort_by = args['sort_by']
        sort_order = args['order']
        is_url = args['is_url'].lower() == 'true'

        print("\n=== 📁 File Listing Debug Info ===")
        print(f"Request from username: {username}")
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
                for weblink in weblinks:
                    documents.append({
                        "title": weblink.url,
                        "type": "weblink",
                        "url": weblink.url,
                        "upload_date": weblink.upload_date.isoformat()
                    })

            else:
                # 파일 메타데이터 쿼리
                files_query = FileMetadata.query
                if sort_by in ['name', 'size', 'type', 'upload_date']:
                    files_query = files_query.order_by(
                        getattr(FileMetadata, sort_by).desc() if sort_order == 'desc' 
                        else getattr(FileMetadata, sort_by)
                    )
                files = files_query.all()
                for file in files:
                    documents.append({
                        "title": file.name,
                        "type": "file",
                        "size": file.size,
                        "file_type": file.type,
                        "upload_date": file.upload_date.isoformat()
                    })

            return {"files": documents}, 200
        except Exception as e:
            print(f"❌ Error in list_files: {str(e)}")
            return {"error": f"Database error: {str(e)}"}, 500
@file_ns.route('/delete/<path:title>')
class DeleteFile(Resource):
    @file_ns.expect(delete_parser)
    @file_ns.response(200, 'File or weblink deleted successfully', model=delete_response_model)
    @file_ns.response(400, 'Bad Request')
    @file_ns.response(403, 'Access denied')
    @file_ns.response(404, 'Document not found')
    @file_ns.response(500, 'Database error')
    def delete(self, title):
        """Delete a file or weblink by title."""
        args = delete_parser.parse_args()
        username = args['username']

        decoded_title = unquote(title)
        print(f"Received DELETE request for title: {decoded_title}")

        if not username:
            print("Error: Username not provided")
            return {"error": "Username not provided"}, 400

        if not is_admin(username):
            print(f"Access denied for user: {username}")
            return {"error": "Access denied. Only admins can delete files."}, 403

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
                    result = VectorDBManager.delete_doc_by_title(weblink.title)
                    print(f"Vector store deletion result: {result}")
                except Exception as ve:
                    print(f"Warning: Failed to delete from vector store: {ve}")

                return {"message": "Weblink deleted successfully"}, 200

            # 파일인 경우 FileMetadata에서 검색
            file = FileMetadata.query.filter_by(name=decoded_title).first()
            if file:
                print(f"Found file to delete: {file.name}")
                db.session.delete(file)
                db.session.commit()
                print(f"✅ File deleted from database: {decoded_title}")

                # 벡터 데이터 삭제 시도
                try:
                    result = VectorDBManager.delete_doc_by_title(file.name)
                    print(f"Vector store deletion result: {result}")
                except Exception as ve:
                    print(f"Warning: Failed to delete from vector store: {ve}")

                return {"message": "File deleted successfully"}, 200

            print(f"❌ Document not found in database: {decoded_title}")
            return {"error": f"Document not found"}, 404

        except Exception as e:
            db.session.rollback()
            error_msg = f"Database error: {str(e)}"
            print(f"❌ {error_msg}")
            return {"error": error_msg}, 500