from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAI, OpenAIEmbeddings
import os

class VectorDBManager:
    def __init__(self, openai_api_key,vectorstore_path="./vectorstore_local"):
        self.submitted_docs = [] 
        self.vectorstore = None
        self.embedding_model = None
        self.vectorstore_path = vectorstore_path
        
        if openai_api_key:
            self.embedding_model = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        else:
            self.embedding_model = OpenAIEmbeddings(openai_api_key=openai_api_key)
            
        # Load existing vectorstore if available
        if os.path.exists(self.vectorstore_path):
            print(f"Loading existing vectorstore from {self.vectorstore_path}")
            self.vectorstore = FAISS.load_local(
                self.vectorstore_path,
                self.embedding_model,
                allow_dangerous_deserialization=True
            )
        else:
            print(f"No existing vectorstore found at {self.vectorstore_path}. Initializing a new one.")

    def generate_embedding(self, text):
        """임베딩 생성"""
        if not self.embedding_model:
            raise ValueError("Embedding model is not initialized.")
        return self.embedding_model.embed_query(text)

    def add_doc_to_db(self, text):
        try:
            print(f"Processing document: {text.metadata['url']}")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = text_splitter.split_text(text.page_content)

            if not splits:
                raise RuntimeError("Text splitting failed. No valid chunks generated.")

            if self.vectorstore is None:
                print("Initializing new FAISS vectorstore.")
                self.vectorstore = FAISS.from_texts(splits, embedding=self.embedding_model)
            else:
                print("Adding texts to existing FAISS vectorstore.")
                self.vectorstore.add_texts(splits)

            # Save the vectorstore locally
            self.vectorstore.save_local(self.vectorstore_path)
            print(f"Vectorstore saved at {self.vectorstore_path}.")
        except Exception as e:
            raise RuntimeError(f"Error processing document: {e}")

    def add_documents(self, documents):
        """Add multiple LangChain Document objects to the vector DB."""
        for doc in documents:
            self.add_doc_to_db(doc) 

    def search(self, query, k=3, search_type="similarity", similarity_threshold=0.7):
        """
        Simple search in vector store.
        """
        if not self.vectorstore:
            raise ValueError("Vectorstore is not initialized. Add documents first.")

        retriever = self.get_retriever(search_type, k, similarity_threshold)
        return retriever.get_relevant_documents(query)

    def get_retriever(self, search_type, k, similarity_threshold):
        """Retrieve documents from the vectorstore."""
        if self.vectorstore is None:
            raise ValueError("Vectorstore is not initialized. Add documents first.")

        return self.vectorstore.as_retriever(search_type=search_type, k=k, similarity_threshold=similarity_threshold)

    def get_submitted_docs(self):
        """Return all submitted documents."""
        return self.submitted_docs