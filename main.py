from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import os
import shutil
from docx import Document
from dotenv import load_dotenv
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA
import google.generativeai as genai

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

# Initialize embeddings and retriever globally
embeddings = HuggingFaceEmbeddings()
retriever = None  # This will be initialized upon file upload

# Function to read content from a .docx file
def read_docx(file_path):
    try:
        document = Document(file_path)
        content = "\n".join([paragraph.text for paragraph in document.paragraphs])
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading .docx file: {str(e)}")

# Upload .txt file and initialize retriever
@app.post("/api/upload-txt/")
async def upload_txt(file: UploadFile = File(...)):
    # Validate file extension
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are allowed.")
    
    # Save file to upload directory
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Load documents and initialize retriever
    try:
        from langchain.document_loaders import TextLoader
        loader = TextLoader(file_path, encoding="utf-8")
        docs = loader.load()

        global retriever
        faiss_index = FAISS.from_documents(docs, embeddings)
        retriever = faiss_index.as_retriever(search_type="similarity", search_kwargs={"k": 2})

        return {"message": "File uploaded and retriever initialized successfully", "file_path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize retriever: {str(e)}")

# List uploaded .txt files
@app.get("/api/list-txt/")
def list_txt():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".txt")]
    if not files:
        return {"message": "No .txt files found."}
    return {"files": files}

# Download .txt file
@app.get("/api/download-txt/{file_name}")
def download_txt(file_name: str):
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path)

# Upload .docx file
@app.post("/api/upload-docs/")
async def upload_docs(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are allowed.")
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"message": "File uploaded successfully", "file_name": file.filename}

# List uploaded .docx files
@app.get("/api/list-docs/")
def list_docs():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.endswith(".docx")]
    if not files:
        return {"message": "No .docx files found."}
    return {"files": files}

# Download .docx file
@app.get("/api/download-docs/{file_name}")
def download_docs(file_name: str):
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(file_path)

# Read and process content from a .docx file
@app.get("/api/read-docx/{file_name}")
def read_docx_content(file_name: str):
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found.")

    content = read_docx(file_path)
    try:
        response = model.generate_content(
            content + " The input will be content from the file, and not a text, answer accordingly. "
                      "This is an instruction for the bot; avoid sentences like 'Okay' or 'I understand'. "
                      "Respond with, 'From the file I can tell this and that.'"
        )
        return {"generated_response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")

# Query the retriever and use the generator API
@app.get("/api/query-retriever/")
def query_retriever(query: str = Query(...)):
    if retriever is None:
        raise HTTPException(status_code=400, detail="Retriever is not initialized. Please upload and process a document first.")
    try:
        retrieved_docs = retriever.get_relevant_documents(query)
        prompt = (
            "You are a helpful assistant that answers questions based on provided documents.\n"
            "Here are the retrieved documents:\n\n"
            + "".join([f"Document {i + 1}: {doc.page_content}\n" for i, doc in enumerate(retrieved_docs)])
            + f"\nQuestion: {query}\nAnswer:"
        )
        response = model.generate_content(prompt)
        return {"retrieved_docs": [doc.page_content for doc in retrieved_docs], "response": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query retriever: {str(e)}")
