from langchain_community.document_loaders import WebBaseLoader
from bs4 import SoupStrainer
from services.docs import Docs  # Docs 클래스 import

class DocumentFetcher:
    def __init__(self):
        self.bs_kwargs = dict(
            parse_only=SoupStrainer("div", attrs={"class": ["newsct_article _article_body", "media_end_head_title"]})
        )

    def fetch(self, title, url):
        """주어진 URL에서 문서를 가져와 Docs 객체 반환"""
        try:
            loader = WebBaseLoader(web_paths=(url,), bs_kwargs=self.bs_kwargs)
            docs = loader.load()

            if not docs:
                raise RuntimeError("No content found. Please check if the provided URL is correct.")
            
            content = docs[0].page_content  # 첫 번째 문서의 본문 내용
            return Docs(title=title, url=url, content=content)
        except Exception as e:
            raise RuntimeError(f"Error fetching document: {e}")
