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

            # 'string ' 접두사 제거
            clean_title = doc.title.replace('string ', '') if isinstance(doc.title, str) else doc.title
            clean_url = doc.url.replace('string ', '') if isinstance(doc.url, str) else doc.url

            # Document 객체 생성 시 정리된 메타데이터 사용
            documents = [
                Document(
                    page_content=split,
                    metadata={
                        "title": clean_title,
                        "url": clean_url
                    }
                )
                for split in splits
            ]

            # 기존 벡터스토어에 새 문서 추가
            self.vectorstore.add_documents(documents)
            
            # 벡터스토어 저장
            self.vectorstore.save_local(self.vectorstore_path)
            print(f"✅ Document '{clean_title}' successfully added to vector store")

            return {
                "message": f"✅ Document '{clean_title}' successfully added to vector store",
                "title": clean_title,
                "url": clean_url
            }

        except Exception as e:
            print(f"❌ Error adding document to vector store: {e}")
            raise RuntimeError(f"Error adding document to vector store: {e}")

    def add_pdf_to_db(self, docs):
        """여러 문서를 벡터 DB에 추가"""
        try:
            if not isinstance(docs, list):
                docs = [docs]

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            documents = []

            for doc in docs:
                splits = text_splitter.split_text(doc.page_content)
                metadata = {
                    "title": doc.metadata['title'].replace('string ', ''),
                    "url": doc.metadata.get('url', '').replace('string ', '')
                }
                for i, split in enumerate(splits):
                    unique_id = f"{metadata['title']}_{i}"
                    documents.append(
                        Document(page_content=split, metadata=metadata, id=unique_id)
                    )

            # 벡터스토어에 문서 추가
            self.vectorstore.add_documents(documents)
            self.vectorstore.save_local(self.vectorstore_path)

            return {"message": "✅ 문서가 성공적으로 벡터 DB에 추가되었습니다.", "document_count": len(documents)}

        except Exception as e:
            raise RuntimeError(f"Error processing document: {e}")


    def add_documents(self, documents):
        """Add multiple LangChain Document objects to the vector DB."""
        for doc in documents:
            self.add_doc_to_db(doc) 

    def search(self, query, k=3, search_type="similarity", similarity_threshold=0.7):
        """벡터 DB에서 문서 검색"""
        try:
            if search_type == "similarity":
                docs = self.vectorstore.similarity_search(query, k=k)
            else:
                docs = self.vectorstore.max_marginal_relevance_search(query, k=k)

            # 검색된 문서의 메타데이터에서 'string ' 접두사 제거
            cleaned_docs = []
            for doc in docs:
                # 메타데이터 딕셔너리 복사
                cleaned_metadata = doc.metadata.copy()
                
                # title과 url 정리
                if 'title' in cleaned_metadata:
                    if cleaned_metadata['title'] == 'string':  # title이 'string'인 경우 URL에서 제목 추출
                        cleaned_metadata['title'] = cleaned_metadata.get('url', '').split('/')[-2].replace('-', ' ').title()
                    else:
                        cleaned_metadata['title'] = cleaned_metadata['title'].replace('string ', '')
                
                if 'url' in cleaned_metadata:
                    cleaned_metadata['url'] = cleaned_metadata['url'].replace('string ', '')

                # 새로운 Document 객체 생성
                cleaned_doc = Document(
                    page_content=doc.page_content,
                    metadata=cleaned_metadata
                )
                cleaned_docs.append(cleaned_doc)

            print("Debug - Cleaned documents metadata:")
            for doc in cleaned_docs:
                print(f"Title: {doc.metadata.get('title')}, URL: {doc.metadata.get('url')}")

            return cleaned_docs
        except Exception as e:
            print(f"Error during vector search: {e}")
            return []

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

    def delete_doc_by_title(self, title: str):
        """title을 기반으로 문서를 삭제"""
        try:
            print(f"📄 현재 저장된 문서 목록:")
            for doc_id, doc in self.vectorstore.docstore._dict.items():
                print(f"ID: {doc_id}, Title: {doc.metadata.get('title')}, Metadata: {doc.metadata}")

            # 파일 확장자 제거
            title_without_extension = os.path.splitext(title)[0].strip().lower()

            # docstore에서 title로 해당 ID 가져오기
            doc_ids_to_delete = [
                doc_id for doc_id, doc in self.vectorstore.docstore._dict.items()
                if doc.metadata.get("title", "").strip().lower() == title_without_extension
            ]
            print(f"📝 삭제할 문서 ID 리스트: {doc_ids_to_delete}")

            if not doc_ids_to_delete:
                all_titles = [doc.metadata.get("title", "제목 없음") for doc in self.vectorstore.docstore._dict.values()]
                print(f"Available titles in vectorstore: {all_titles}")
                return {"message": f"❌ '{title}' 제목의 문서를 찾을 수 없습니다. 저장된 제목들: {all_titles}"}

            # 삭제 수행
            self.vectorstore.delete(doc_ids_to_delete)
            self.vectorstore.save_local(self.vectorstore_path)
            print(f"✅ Vectorstore successfully saved after deletion.")

            return {"message": f"✅ '{title}' 제목의 문서가 성공적으로 삭제되었습니다."}

        except Exception as e:
            print(f"❌ Error during vector data deletion: {e}")
            raise RuntimeError(f"Error deleting document by title: {e}")
