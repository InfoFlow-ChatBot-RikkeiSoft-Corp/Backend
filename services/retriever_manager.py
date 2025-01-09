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
            docs = self.vector_db_manager.search(
                query=question, k=k, search_type=search_type, similarity_threshold=similarity_threshold
            )
            # 검색된 문서를 텍스트로 변환
            context = "\n\n".join([doc.page_content for doc in docs])
            return context if context else "주어진 정보에서 질문에 대한 정보를 찾을 수 없습니다."
        except Exception as e:
            raise RuntimeError(f"Error during context retrieval: {e}")
