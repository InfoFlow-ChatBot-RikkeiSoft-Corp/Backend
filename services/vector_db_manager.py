from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document  # Document 클래스 import


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
            # Document 객체 생성 (본문과 메타데이터 포함)
            documents = [
                Document(page_content=split, metadata={"title": doc.title, "url": doc.url})
                for split in splits
            ]
            # 임베딩 및 벡터 저장
            vectorstore = FAISS.from_documents(documents, embedding=self.embedding_model)
            vectorstore.save_local(self.vectorstore_path)

            # 제출된 문서 저장
            self.submitted_docs.append(doc)

            # 상위 3개 청크 정보
            vector_details = []
            for i in range(min(3, len(splits))):
                vector_details.append({
                    "vector_index": i + 1,
                    "embedding_excerpt": vectorstore.index.reconstruct(i)[:5],  # 임베딩 일부 출력
                    "content_excerpt": documents[i].page_content[:300],  # 청크 본문 일부 출력
                    "title": documents[i].metadata["title"],  # 문서 제목 추가
                    "url": documents[i].metadata["url"],  # 문서 URL 추가
                })

            return vector_details
        except Exception as e:
            raise RuntimeError(f"Error processing document: {e}")

    def get_submitted_docs(self):
        """제출된 모든 문서 반환"""
        return self.submitted_docs
