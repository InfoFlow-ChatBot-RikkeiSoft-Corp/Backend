from flask import Flask
from docx import Document
import google.generativeai as genai
from dotenv import load_dotenv
import os


load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

app = Flask(__name__)
genai.configure()
model = genai.GenerativeModel("gemini-1.5-flash")

def read_docx(file):
    try:
        document = Document(file)
        content = ""
        for paragraph in document.paragraphs:
            content += paragraph.text + "\n"
        return content
    except Exception as e:
        return f"Error reading .docx file: {str(e)}"

@app.route("/")
def index():
    file_path = r"C:\Users\toots\Downloads\demo.docx"
    content = read_docx(file_path)
    
    if "Error reading" in content:
        return content
    
    response = model.generate_content(content + "The input will be a content from the file, and not a text, answer accordingly, this is an instruction i am giving for a bot, dont include sentences like, OKay or I understand, just say, from the file i can tell this and that")
    return response.text

if __name__ == "__main__":
    app.run(debug=True)
