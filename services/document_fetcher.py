from langchain_community.document_loaders import WebBaseLoader
from langchain.document_loaders import UnstructuredWordDocumentLoader
from bs4 import SoupStrainer
from services.docs import Docs

class DocumentFetcher:
    def __init__(self):
        self.bs_kwargs = dict(
            parse_only=SoupStrainer("div", attrs={"class": ["newsct_article _article_body", "media_end_head_title"]})
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
            
            content = docs[0].page_content
            return Docs.from_web(title=title, url=url, content=content)

        except Exception as e:

            raise RuntimeError(f"Error fetching document: {e}")

    def load_docx(self, file_path):
        """
        Load a .docx file and return a Docs object.
        """
        try:
            loader = UnstructuredWordDocumentLoader(file_path)
            docs = loader.load()

            if not docs:
                raise RuntimeError("No content found in the .docx file.")

            content = docs[0].page_content
            return Docs.from_file(file_path=file_path, content=content)

        except Exception as e:
            raise RuntimeError(f"Error loading .docx file: {e}")
