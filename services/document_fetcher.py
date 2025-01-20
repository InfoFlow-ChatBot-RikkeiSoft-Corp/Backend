from langchain_community.document_loaders import PDFPlumberLoader
from langchain_community.vectorstores import FAISS
from bs4 import SoupStrainer
from langchain.schema import Document as LangChainDocument
from pdf2image import convert_from_path
import pytesseract
from services.docs import Docs
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.document_loaders import UnstructuredWordDocumentLoader
from bs4 import SoupStrainer
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import os
import docx2txt
from langchain_core.documents import Document

class DocumentFetcher:
    def __init__(self):
        self.bs_kwargs = dict(
            parse_only=SoupStrainer(["h1", "p", "div"])

        )

    def fetch(self, title, url):
        """
        Fetch a document from a given URL and return a Docs object.
        """
        try:
            loader = WebBaseLoader(web_paths=(url,), bs_kwargs=self.bs_kwargs)
            docs = loader.load()

            if not docs:
                raise RuntimeError("No content found. Please check if the provided URL is correct.")
            
            page_content = docs[0].page_content
            # 제목에서 'string ' 접두사 제거
            clean_title = title.replace('string ', '') if isinstance(title, str) else title
            
            return Docs.from_web(
                title=clean_title,
                url=url,
                content=page_content
            )

        except Exception as e:
            print(f"Error fetching document: {e}")
            raise RuntimeError(f"Error fetching document: {e}")

    def load_txt(self, file_path):
        """
        Load a .txt file and return a list of Document objects.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # 파일 이름에서 title 추출
            file_name = os.path.basename(file_path)
            title = os.path.splitext(file_name)[0]
            
            # LangChain Document 객체로 변환
            return [Document(
                page_content=content,
                metadata={
                    "source": file_path,
                    "title": title,
                    "type": "txt"
                }
            )]
        except Exception as e:
            print(f"❌ Error loading TXT file: {e}")
            raise RuntimeError(f"Error loading TXT file: {e}")

    def load_docx(self, file_path):
        """
        docx 파일을 로드하여 Document 객체로 변환
        """
        print(f"📄 Loading DOCX file: {file_path}")
        try:
            # docx2txt 사용 (더 빠른 처리)
            import docx2txt
            text = docx2txt.process(file_path)
            
            # 파일명 추출
            filename = os.path.basename(file_path)
            
            # 텍스트 분할 (너무 긴 문서 처리)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=100,
                length_function=len,
            )
            
            # 청크로 분할
            texts = text_splitter.split_text(text)
            print(f"✅ Split document into {len(texts)} chunks")
            
            # Document 객체 생성
            docs = []
            for i, chunk in enumerate(texts):
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "source": file_path,
                        "title": filename,
                        "id": f"{filename}_chunk_{i}",
                        "type": "docx",
                        "chunk": i
                    }
                )
                docs.append(doc)
            
            print(f"✅ Successfully loaded DOCX file: {filename}")
            return docs

        except Exception as e:
            print(f"❌ Error loading DOCX file: {str(e)}")
            return []

    def extract_text_with_ocr(self, file_path):
        """
        Perform OCR on an image-based PDF and return extracted text.
        """
        try:
            images = convert_from_path(file_path)
            text = ""
            for page_num, image in enumerate(images, start=1):
                print(f"Processing page {page_num} with OCR...")
                text += pytesseract.image_to_string(image, lang='eng')

            if text.strip():
                print("Extracted content using OCR (first 500 characters):")
                print(text[:500])
            else:
                print("No text could be extracted using OCR.")
            return text
        except Exception as e:
            print(f"Error during OCR processing: {e}")
            return ""

    def load_pdf(self, file_path):
        """
        Load a .pdf file and return LangChain Documents. Use OCR as a fallback if necessary.
        """
        try:
            loader = PDFPlumberLoader(file_path)
            documents = loader.load_and_split()

            if documents:
                print("Extracted content using PDFPlumberLoader (first document):")
                print(documents[0].page_content[:500])

                # 파일 이름에서 title 추출
                file_name = os.path.basename(file_path)
                title = os.path.splitext(file_name)[0]

                return [
                    LangChainDocument(
                        page_content=doc.page_content,
                        metadata={"source": file_path, "title": title}  # title 추가
                    )
                    for doc in documents
                ]
            else:
                print("No content extracted using PDFPlumberLoader. Falling back to OCR...")
                ocr_text = self.extract_text_with_ocr(file_path)
                if ocr_text.strip():
                    file_name = os.path.basename(file_path)
                    title = os.path.splitext(file_name)[0]
                    return [LangChainDocument(page_content=ocr_text, metadata={"source": file_path, "title": title})]
                else:
                    print("No text could be extracted from PDF.")
                    return []

        except FileNotFoundError:
            print(f"Error: File not found at path {file_path}")
            return []
        except PermissionError:
            print(f"Error: Permission denied for file at path {file_path}")
            return []
        except Exception as e:
            # General exception handling
            print(f"Error processing PDF file: {e}")
            return []
