from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directory to store uploaded files
UPLOAD_FOLDER = "./uploaded_files"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Function to read content from a .docx file
def read_docx(file_path):
    try:
        document = Document(file_path)
        content = "\n".join([paragraph.text for paragraph in document.paragraphs])
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading .docx file: {str(e)}")

# Upload .docx file API
@app.post("/api/upload-docs/")
async def upload_docs(file: UploadFile = File(...)):
    # Validate file extension
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are allowed.")
    
    # Save file to upload directory
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"message": "File uploaded successfully", "file_name": file.filename}

# List uploaded .docx files API
@app.get("/api/list-docs/")
def list_docs():
    # List .docx files in the upload directory
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".docx")]
    if not files:
        return {"message": "No files found."}
    return {"files": files}

# Download .docx file API
@app.get("/api/download-docs/{file_name}")
def download_docs(file_name: str):
    # Check if the file exists
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    
    # Return the file
    return FileResponse(file_path)

# Read and process content from a .docx file API
@app.get("/api/read-docx/{file_name}")
def read_docx_content(file_name: str):
    # Check if the file exists
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    # Read the content of the file
    content = read_docx(file_path)
    
    # Generate response using Generative AI
    try:
        response = model.generate_content(
            content + " The input will be content from the file, and not a text, answer accordingly. "
                      "This is an instruction for the bot; avoid sentences like 'Okay' or 'I understand'. "
                      "Respond with, 'From the file I can tell this and that.'"
        )
        return {"generated_response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")
