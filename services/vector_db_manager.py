from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langchain_community.docstore.in_memory import InMemoryDocstore
import os


class VectorDBManager:
    def __init__(self):
        self.submitted_docs = []  # 제출된 Docs 객체 목록
        self.embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        self.vectorstore_path = "faiss_index"

        # 벡터스토어 로드 (없으면 빈 DB 생성)
        if os.path.exists(self.vectorstore_path):
            try:
                self.vectorstore = FAISS.load_local(
                    self.vectorstore_path,
                    self.embedding_model,
                    allow_dangerous_deserialization=True  # 보안 설정 추가
                )
                print("✅ 기존 FAISS 벡터스토어를 로드했습니다.")
            except Exception as e:
                print(f"❌ FAISS 벡터스토어 로드 실패: {e}")
                # 빈 벡터스토어 생성
                self.vectorstore = FAISS(FAISS.build_index(), self.embedding_model)
        else:
            self.vectorstore = FAISS(FAISS.build_index(), self.embedding_model)
            print("🔄 새 빈 FAISS 벡터스토어를 생성했습니다.")

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

            # 기존 벡터스토어에 새 문서 추가
            self.vectorstore.add_documents(documents)
            print(f"✅ '{doc.title}' 문서가 벡터 DB에 성공적으로 추가되었습니다.")

            # 벡터스토어 저장
            self.vectorstore.save_local(self.vectorstore_path)
            self.vectorstore = FAISS.load_local(
                    self.vectorstore_path,
                    self.embedding_model,
                    allow_dangerous_deserialization=True  # 보안 설정 추가
                )
            print(f"✅ '{doc.title}' 문서가 벡터 DB에 성공적으로 추가 및 로드되었습니다.")

            # 제출된 문서 저장
            self.submitted_docs.append(doc)

            # 상위 3개 청크 정보
            vector_details = []
            for i in range(min(3, len(documents))):
                vector_details.append({
                    "vector_index": i + 1,
                    "embedding_excerpt": self.vectorstore.index.reconstruct(i)[:5],  # 임베딩 일부 출력
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
    def get_all_docs_metadata(self):
        """벡터 DB에 저장된 모든 문서의 메타데이터(title, url)를 반환"""
        if not self.vectorstore:
            print("❌ FAISS 벡터스토어가 초기화되지 않았습니다.")
            return []

        metadata_list = []
        for doc_id, doc in self.vectorstore.docstore._dict.items():  # docstore 내부 dict 접근
            if doc is None:
                continue
            title = doc.metadata.get("title", "제목 없음")
            url = doc.metadata.get("url", "URL 없음")
            metadata_list.append({"title": title, "url": url})

        return metadata_list