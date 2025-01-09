from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class RetrieverManager:
    def __init__(self, vectorstore_path="faiss_index"):
        # Embedding 설정
        self.embedding = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

        try:
            # FAISS 벡터스토어 로드 (보안 설정 추가)
            self.vectorstore = FAISS.load_local(
                vectorstore_path,
                self.embedding,
                allow_dangerous_deserialization=True  # 역직렬화 허용
            )
            print("✅ FAISS 벡터스토어가 성공적으로 로드되었습니다.")
        except Exception as e:
            print("🔄 빈 벡터스토어를 생성 중입니다...")
            # 빈 벡터스토어 생성 및 저장
            self.vectorstore = FAISS.from_texts([], embedding=self.embedding)
            self.vectorstore.save_local("faiss_index")
            print("✅ 빈 벡터스토어 생성 완료")

    def retrieve_context(self, question, k=3):
        if not self.vectorstore:
            raise RuntimeError("FAISS 벡터스토어가 초기화되지 않았습니다.")
        docs = self.vectorstore.as_retriever().invoke(question)
        context = "\n\n".join([doc.page_content for doc in docs])
        return context if context else "주어진 정보에서 질문에 대한 정보를 찾을 수 없습니다."
