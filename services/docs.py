from datetime import datetime

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


    def get_excerpt(self, length=300):
        """본문 내용의 일부를 반환 (기본 300자)"""
        return self.content[:length] + "..." if len(self.content) > length else self.content
