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
import sqlalchemy as sa
from pytz import timezone

from dotenv import load_dotenv
import os
import uuid

file_routes = Blueprint('file_routes', __name__)

ALLOWED_FILE_TYPES = {'txt', 'docx', 'pdf'}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

tz = timezone("Asia/Ho_Chi_Minh")  # Replace with your desired time zone
current_time = datetime.now(tz)

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
def upload_file():
    username = request.headers.get('username')
    if not username:
        return jsonify({"error": "Username not provided"}), 400

    if not is_admin(username):
        return jsonify({"error": "Access denied. Only admins can upload files."}), 403

    file = request.files.get('file')

    print("Headers:", request.headers)
    print("Files:", request.files)
    print("Form data:", request.form)

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

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
    file_type = file_name.rsplit('.', 1)[1].lower()
    upload_date = current_time

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        # Save file temporarily
        temp_path = os.path.join("temp_uploads", file_name)
        file.save(temp_path)

        # Process document and add to vector DB
        docs = document_fetcher.load_docx(temp_path) if file_name.endswith("docx") else document_fetcher.load_pdf(temp_path)

        if docs:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            documents = []

            for doc in docs:
                splits = text_splitter.split_text(doc.page_content)
                for i, split in enumerate(splits):
                    unique_id = f"{file_name}_{uuid.uuid4().hex}"  # Generate unique ID
                    documents.append(
                        Document(page_content=split, metadata={"title": file_name, "source": temp_path}, id=unique_id)
                    )

            vector_db_manager.vectorstore.add_documents(documents)
            vector_db_manager.vectorstore.save_local(vector_db_manager.vectorstore_path)

            # Save metadata to the database
            metadata = FileMetadata(
                name=file_name, size=file_size, type=file_type, upload_date=upload_date, user_id=user.id
            )
            db.session.add(metadata)
            db.session.commit()

            return jsonify({"message": "File uploaded successfully", "document_count": len(documents)}), 201
        else:
            return jsonify({"error": "Failed to process the document content"}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
    finally:
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


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


