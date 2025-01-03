from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import os
import shutil

app = FastAPI()

# 업로드된 파일을 저장할 디렉토리 설정
UPLOAD_FOLDER = "./uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.post("/upload-docs/")
async def upload_docs(file: UploadFile = File(...)):
    # 1. 파일 확장자 확인
    if not (file.filename.endswith(".doc") or file.filename.endswith(".docx")):
        return {"error": "Only .doc or .docx files are allowed."}

    # 2. 파일 저장
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"message": "File uploaded successfully", "file_path": file_path}

@app.get("/list-docs/")
def list_docs():
    # 1. 디렉토리 내 DOC/DOCX 파일 목록 가져오기
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".doc") or f.endswith(".docx")]
    return {"files": files}

# 특정 docs 파일 다운로드 API
@app.get("/download-docs/{file_name}")
def download_docs(file_name: str):
    # 1. 파일 경로 확인
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        return {"error": "File not found"}

    # 2. 파일 반환
    return FileResponse(file_path)
