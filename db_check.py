from services.document_fetcher import DocumentFetcher
from services.vector_db_manager import VectorDBManager
vector_db_manager = VectorDBManager()

# 모든 문서 메타데이터 가져오기
all_docs_metadata = vector_db_manager.get_all_docs_metadata()

if not all_docs_metadata:
    print("❌ 저장된 문서가 없습니다.")
else:
    print("✅ 저장된 문서 리스트:")
    for idx, meta in enumerate(all_docs_metadata, 1):
        print(f"{idx}. 제목: {meta['title']} | URL: {meta['url']}")
