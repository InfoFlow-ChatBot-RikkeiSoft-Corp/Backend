from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class VectorDBManager:
    def __init__(self):
        self.submitted_docs = []  # 제출된 Docs 객체 목록
        self.embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        self.vectorstore_path = "faiss_index"

    def add_doc_to_db(self, doc):
        """Docs 객체를 벡터 DB에 추가"""
        try:
            # 텍스트 분할
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = text_splitter.split_text(doc.content)

            if not splits:
                raise RuntimeError("Text splitting failed. No valid chunks generated.")

            # 임베딩 및 벡터 저장
            vectorstore = FAISS.from_texts(splits, embedding=self.embedding_model)
            vectorstore.save_local(self.vectorstore_path)

            # 제출된 문서 저장
            self.submitted_docs.append(doc)

            # 상위 3개 청크 정보
            vector_details = []
            for i in range(min(3, len(splits))):
                vector_details.append({
                    "vector_index": i + 1,
                    "embedding_excerpt": vectorstore.index.reconstruct(i)[:5],  # 임베딩 일부 출력
                    "content_excerpt": splits[i][:300],  # 청크 본문 일부 출력
                })

            return vector_details
        except Exception as e:
            raise RuntimeError(f"Error processing document: {e}")

    def get_submitted_docs(self):
        """제출된 모든 문서 반환"""
        return self.submitted_docs
