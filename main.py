from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
import os
import shutil

app = FastAPI(
    title="Document Upload API",
    description="API for uploading and managing DOC/DOCX files. This service allows you to upload, list, and download document files.",
    version="1.0.0"
)

# 업로드된 파일을 저장할 디렉토리 설정
UPLOAD_FOLDER = "./uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.post("/api/upload-docs/", summary="Upload Document", description="Upload a .doc or .docx file to the server.")
async def upload_docs(file: UploadFile = File(...)):
    # 1. 파일 확장자 확인
    if not (file.filename.endswith(".doc") or file.filename.endswith(".docx")):
        return {"error": "Only .doc or .docx files are allowed."}

    # 2. 파일 저장
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"message": "File uploaded successfully", "file_path": file_path}

@app.get("/api/list-docs/", summary="List Uploaded Documents", description="Retrieve a list of all uploaded .doc and .docx files.")
def list_docs():
    # 1. 디렉토리 내 DOC/DOCX 파일 목록 가져오기
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".doc") or f.endswith(".docx")]
    return {"files": files}

# 특정 docs 파일 다운로드 API
@app.get("/api/download-docs/{file_name}", summary="Download Document", description="Download a specific .doc or .docx file by its file name.")
def download_docs(file_name: str):
    # 1. 파일 경로 확인
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")  # 404 에러 반환

    # 2. 파일 반환
    return FileResponse(file_path, status_code=200, media_type="application/octet-stream", filename=file_name)
