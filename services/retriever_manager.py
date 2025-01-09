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

        # FAISS 검색
        docs = self.vectorstore.as_retriever(search_kwargs={"k": k}).invoke(question)

        # 검색된 문서의 본문과 메타데이터를 포함한 컨텍스트 생성
        references = []
        context_list = []

        for doc in docs:
            content = doc.page_content  # 본문 내용
            metadata = doc.metadata  # 메타데이터 (제목, URL 등)
            title = metadata.get("title", "제목 없음")
            url = metadata.get("url", "URL 없음")

            context_list.append(f"{content}\n출처: {title} ({url})")
            references.append({"title": title, "url": url})

        # 컨텍스트 본문 조합 및 반환
        context = "\n\n".join(context_list)
        if not context:
            return "주어진 정보에서 질문에 대한 정보를 찾을 수 없습니다."

        # 응답 형식 (본문과 참조 정보 반환)
        return {
            "context": context,
            "references": references
        }
