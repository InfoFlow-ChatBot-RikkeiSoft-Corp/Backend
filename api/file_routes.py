from flask import Blueprint, request, jsonify
from datetime import datetime
from models import db, FileMetadata,User
import sqlalchemy as sa
from pytz import timezone

file_routes = Blueprint('file_routes', __name__)

ALLOWED_FILE_TYPES = {'txt', 'docx', 'pdf'}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

tz = timezone("Asia/Ho_Chi_Minh")  # Replace with your desired time zone
current_time = datetime.now(tz)

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

    file_name = file.filename
    file_type = file_name.rsplit('.', 1)[1].lower()
    upload_date = current_time

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        metadata = FileMetadata(name=file_name, size=file_size, type=file_type, upload_date=upload_date, user_id= user.id)
        db.session.add(metadata)
        db.session.commit()
        return jsonify({"message": "File uploaded successfully", "file_id": metadata.id}), 201
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


