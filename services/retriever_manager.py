from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class RetrieverManager:

    def __init__(self, vector_db_manager):
        """
        VectorDBManager 객체를 통해 벡터스토어를 관리.
        """
        self.vector_db_manager = vector_db_manager

    def retrieve_context(self, question, k=3, search_type="similarity", similarity_threshold=0.7):
        """
        질문에 대한 컨텍스트를 검색.
        """
        try:

            # 벡터 DB에서 문서 검색
            docs = self.vector_db_manager.search(
                query=question, k=k, search_type=search_type, similarity_threshold=similarity_threshold
            )

            # 검색된 문서의 본문과 메타데이터를 기반으로 컨텍스트 생성
            references = []
            context_list = []

            for doc in docs:
                content = doc.page_content  # 본문 내용
                metadata = doc.metadata  # 메타데이터 (제목, URL 등)
                title = metadata.get("title", "제목 없음")
                url = metadata.get("url", "URL 없음")

                context_list.append(f"{content}\n출처: {title} ({url})")
                references.append({"title": title, "url": url})

            # 컨텍스트 본문 조합
            context = "\n\n".join(context_list)

            # 결과 반환
            return {
                "context": context if context else "주어진 정보에서 질문에 대한 정보를 찾을 수 없습니다.",
                "references": references
            }
        except Exception as e:
            raise RuntimeError(f"Error during context retrieval: {e}")