from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_openai import OpenAI, OpenAIEmbeddings
import os

class VectorDBManager:
    def __init__(self, openai_api_key, google_api_key):
        self.submitted_docs = [] 
        self.vectorstore = None
        self.embedding_model = None
        self.vectorstore_path = "faiss_db"
        
        # Initialize embedding model based on the available API key
        if google_api_key:
            os.environ["GOOGLE_API_KEY"] = google_api_key
            self.embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        elif openai_api_key:
            self.embedding_model = OpenAIEmbeddings(openai_api_key=openai_api_key)
        else:
            raise ValueError("Either google_api_key or openai_api_key must be provided.")
            
        # 벡터스토어 로드 (없으면 빈 DB 생성)
        if os.path.exists(self.vectorstore_path):
            try:
                self.vectorstore = FAISS.load_local(
                    self.vectorstore_path, 
                    self.embedding_model,
                    allow_dangerous_deserialization=True
                    )
                print("✅ 기존 FAISS 벡터스토어를 로드했습니다.")
            except Exception as e:
                print(f"❌ FAISS 벡터스토어 로드 실패: {e}. 새 벡터스토어 생성 중...")
                self.initialize_empty_vectorstore()
        else:
            print("🔄 새 빈 FAISS 벡터스토어를 생성합니다.")
            self.initialize_empty_vectorstore()

    def initialize_empty_vectorstore(self):
        """빈 벡터스토어 초기화 (기본 문서 추가)"""
        default_doc = Document(page_content="This is a default document.", metadata={"title": "Default"})
        self.vectorstore = FAISS.from_documents([default_doc], embedding=self.embedding_model)
        self.vectorstore.save_local(self.vectorstore_path)
        print("✅ 기본 문서를 사용하여 벡터스토어를 초기화했습니다.")

    def generate_embedding(self, text):
        """generate text embedding"""
        if not self.embedding_model:
            raise ValueError("Embedding model is not initialized.")
        return self.embedding_model.embed_query(text)

    def add_doc_to_db(self, doc):
        try:
            print(f"Processing document: {doc.metadata.get('title', '제목 없음')}")
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

            print(vector_details)


            # Save the vectorstore locally
            # self.vectorstore.save_local(self.vectorstore_path)
            # print(f"Vectorstore saved at {self.vectorstore_path}.")
        except Exception as e:
            raise RuntimeError(f"Error processing document: {e}")

    def add_documents(self, documents):
        """Add multiple LangChain Document objects to the vector DB."""
        for doc in documents:
            self.add_doc_to_db(doc) 

    def search(self, query, k, search_type, similarity_threshold):
        """
        Simple search in vector store.
        """
        if not self.vectorstore:
            raise ValueError("Vectorstore is not initialized. Add documents first.")

        retriever = self.get_retriever(search_type, k, similarity_threshold)
        return retriever.invoke(query)

    def get_retriever(self, search_type, k, similarity_threshold):
        """Retrieve documents from the vectorstore."""
        if self.vectorstore is None:
            raise ValueError("Vectorstore is not initialized. Add documents first.")

        return self.vectorstore.as_retriever(search_type=search_type, k=k, similarity_threshold=similarity_threshold)

    def get_submitted_docs(self):
        """Return all submitted documents."""
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
    def get_top_k_vectors(self, k=5):
        """상위 K개의 벡터를 조회하여 반환합니다."""
        try:
            if not self.vectorstore:
                raise RuntimeError("FAISS 벡터스토어가 초기화되지 않았습니다.")

            if len(self.vectorstore.docstore._dict) == 0:
                print("❌ 벡터스토어에 저장된 문서가 없습니다.")
                return []

            # 상위 K개의 문서 정보를 가져오기
            documents = list(self.vectorstore.docstore._dict.values())[:k]
            top_k_info = [{"title": doc.metadata.get("title", "N/A"), "content_excerpt": doc.page_content[:300]} for doc in documents]

            return top_k_info

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            return []


