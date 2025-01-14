from flask import Blueprint, request, jsonify
from datetime import datetime
from models.models import db, FileMetadata,User
from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
import sqlalchemy as sa
from pytz import timezone
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

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
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can upload files."}), 403

    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file provided"}), 400

    if not is_allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return jsonify({"error": "File exceeds maximum size of 25 MB"}), 400

    file_name = secure_filename(file.filename)
    file_path = os.path.join("temp_uploads", file_name)
    file_type = file_name.rsplit('.', 1)[1].lower()

    # 중복된 파일 이름 확인
    existing_file = FileMetadata.query.filter_by(name=file_name).first()
    if existing_file:
        return jsonify({"error": "❌ 해당 파일은 이미 업로드되어 있습니다."}), 400

    # 중복 방지 파일 저장
    file.save(file_path)

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        metadata = FileMetadata(name=file_name, size=file_size, type=file_type, upload_date=current_time, user_id=user.id)
        db.session.add(metadata)
        db.session.commit()

        docs = document_fetcher.load_pdf(file_path)
        existing_vectors = vector_db_manager.get_all_docs_metadata()

        for doc in docs:
            if any(meta['title'] == doc.metadata['title'] for meta in existing_vectors):
                return jsonify({"error": f"❌ 문서 '{doc.metadata['title']}'가 이미 벡터 DB에 존재합니다."}), 400

        vector_details = vector_db_manager.add_pdf_to_db(docs)
        return jsonify({"message": "✅ PDF 문서가 성공적으로 처리되었습니다.", "vector_info": vector_details}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500


@file_routes.route('/delete/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    username = request.headers.get('username')
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can delete files."}), 403

    metadata = FileMetadata.query.get(file_id)
    if not metadata:
        return jsonify({"error": "File not found"}), 404

    try:
        db.session.delete(metadata)
        db.session.commit()
        return jsonify({"message": "File deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Database error: {str(e)}"}), 500

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

    if sort_by not in ['name', 'size', 'type', 'upload_date']:
        return jsonify({"error": "Invalid sort parameter"}), 400

    try:
        query = FileMetadata.query.order_by(
            getattr(FileMetadata, sort_by).asc() if sort_order == 'asc' else getattr(FileMetadata, sort_by).desc()
        )
        print(f"Sorting by: {sort_by}, Order: {sort_order}")
        files = query.all()

        file_list = [
            {
                "id": file.id,
                "name": file.name,
                "size": file.size,
                "type": file.type,
                "upload_date": file.upload_date.isoformat()
            }
            for file in files
        ]

        return jsonify({"files": file_list}), 200
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500


