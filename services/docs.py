from datetime import datetime
from langchain.schema import Document as LangChainDocument

class Docs:
    def __init__(self, title, url, content):
        self.title = title.replace('string ', '') if isinstance(title, str) else title
        self.url = url.replace('string ', '') if isinstance(url, str) else url
        self.content = content
        self.submitted_at = datetime.now()
        self.metadata = {
            "title": self.title,
            "url": self.url
        }

    def to_langchain_document(self):
        """Convert to LangChain-compatible Document object."""
        return LangChainDocument(
            page_content=self.content,
            metadata={
                "title": self.title.replace('string ', '') if isinstance(self.title, str) else self.title,
                "url": self.url.replace('string ', '') if isinstance(self.url, str) else self.url
            }
        )

    def get_excerpt(self, length=300):
        """본문 내용의 일부를 반환 (기본 300자)"""
        return self.content[:length] + "..." if len(self.content) > length else self.content

    @staticmethod
    def from_web(title, url, content):
        """웹 문서 데이터를 기반으로 Docs 객체 생성"""
        clean_title = title.replace('string ', '') if isinstance(title, str) else title
        clean_url = url.replace('string ', '') if isinstance(url, str) else url
        return Docs(title=clean_title, url=clean_url, content=content)

    @staticmethod
    def from_file(file_path, content):
        """파일 데이터를 기반으로 Docs 객체 생성"""
        title = file_path.split("\\")[-1].split(".")[0]
        clean_title = title.replace('string ', '')
        clean_file_path = file_path.replace('string ', '')
        return Docs(title=clean_title, url=clean_file_path, content=content)