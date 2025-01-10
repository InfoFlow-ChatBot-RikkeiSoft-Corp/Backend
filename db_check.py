from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager

from dotenv import load_dotenv
import os
# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# 서비스 객체 생성
document_fetcher = DocumentFetcher()
vector_db_manager = VectorDBManager(
    openai_api_key=OPENAI_API_KEY,
    google_api_key=GOOGLE_API_KEY
)

# 모든 문서 메타데이터 가져오기
all_docs_metadata = vector_db_manager.get_all_docs_metadata()

if not all_docs_metadata:
    print("❌ 저장된 문서가 없습니다.")
else:
    print("✅ 저장된 문서 리스트:")
    for idx, meta in enumerate(all_docs_metadata, 1):
        print(f"{idx}. 제목: {meta['title']} | URL: {meta['url']}")
