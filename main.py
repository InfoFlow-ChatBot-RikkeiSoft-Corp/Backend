from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
import os
import shutil
from docx import Document
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Configure Generative AI
if api_key:
    genai.configure(api_key=api_key)
else:
    raise ValueError("Google API key not found in environment variables.")

model = genai.GenerativeModel("gemini-1.5-flash")

app = FastAPI()

# 업로드된 파일을 저장할 디렉토리 설정
UPLOAD_FOLDER = "./uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# TXT 파일 업로드 API
@app.post("/upload-txt/")
async def upload_txt(file: UploadFile = File(...)):
    # 1. 파일 확장자 확인
    if not file.filename.endswith(".txt"):
        return {"error": "Only .txt files are allowed."}

    # 2. 파일 저장
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"message": "File uploaded successfully", "file_path": file_path}

# 업로드된 파일 목록 반환 API
@app.get("/list-txt/")
def list_txt():
    # 1. 디렉토리 내 TXT 파일 목록 가져오기    
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".txt")]
    return {"files": files}

# 특정 TXT 파일 다운로드 API
@app.get("/download-txt/{file_name}")
def download_txt(file_name: str):
    # 1. 파일 경로 확인
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        return {"error": "File not found"}

    # 2. 파일 반환
    return FileResponse(file_path)

# Directory to store uploaded files
UPLOAD_FOLDER = "./uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Function to read content from a .docx file
def read_docx(file_path):
    try:
        document = Document(file_path)
        content = ""
        for paragraph in document.paragraphs:
            content += paragraph.text + "\n"
        return content
    except Exception as e:
        return f"Error reading .docx file: {str(e)}"

# Read and process content from a .docx file
@app.get("/read-docx/{file_name}")
def read(file_name: str):
    # 1. Check if the file exists
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        return {"error": "File not found"}

    # 2. Read content from the file
    content = read_docx(file_path)
    if "Error reading" in content:
        return {"error": content}
    
    # 3. Generate response using Generative AI
    try:
        response = model.generate_content(
            content + " The input will be a content from the file, and not a text, answer accordingly, this is an instruction I am giving for a bot, don't include sentences like 'Okay' or 'I understand', just say 'From the file I can tell this and that.'"
        )
        return {"generated_response": response.text}
    except Exception as e:
        return {"error": f"Error generating response: {str(e)}"}
