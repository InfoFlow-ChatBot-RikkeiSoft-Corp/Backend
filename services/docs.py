from datetime import datetime
from langchain.schema import Document as LangChainDocument

class Docs:
    def __init__(self, title, url, content):
        self.title = title  # 문서 제목
        self.url = url  # 문서 URL
        self.content = content  # 전체 문서 본문
        self.submitted_at = datetime.now()  # 제출 시간
        self.metadata = {
            "title": self.title,
            "url": self.url
        }

    def to_langchain_document(self):
        """Convert to LangChain-compatible Document object."""
        return LangChainDocument(
            page_content=self.content,
            metadata={"title": self.title, "url": self.url}
        )

    def get_excerpt(self, length=300):
        """본문 내용의 일부를 반환 (기본 300자)"""
        return self.content[:length] + "..." if len(self.content) > length else self.content

    @staticmethod
    def from_web(title, url, content):
        """웹 문서 데이터를 기반으로 Docs 객체 생성"""
        return Docs(title=title, url=url, content=content)

    @staticmethod
    def from_file(file_path, content):
        """파일 데이터를 기반으로 Docs 객체 생성"""
        title = file_path.split("\\")[-1].split(".")[0]
        return Docs(title=title, url=file_path, content=content)
