import os
from langchain.prompts import PromptTemplate
from langchain.schema import Document as LangChainDocument
from vector_db_manager import VectorDBManager
from document_fetcher import DocumentFetcher
from answer_generator import AnswerGenerator
from chat_generator import ChatGenerator
from docs import Docs

class RAGManager:
    def __init__(self, retriever_manager, answer_generator, document_fetcher, vector_db_manager):
        """
        Initialize the RAGManager with dependencies.
        """
        self.retriever_manager = retriever_manager
        self.answer_generator = answer_generator
        self.document_fetcher = document_fetcher
        
    def add_documents(self, file_paths):
        """
        Load documents from file paths and add them to the vector database.
        """
        for file_path in file_paths:
            try:
                print(f"Loading document: {file_path}")
                doc = self.doc_fetcher.load_docx(file_path)
                langchain_doc = doc.to_langchain_document()
                self.vector_db.add_documents([langchain_doc])
                print(f"Successfully added document: {file_path}")
            except Exception as e:
                print(f"Failed to process file '{file_path}': {e}")


    def fetch_and_add_document(self, title, url):
        """
        Fetch a document from a URL and add it to the vector database.
        """
        try:
            print(f"Fetching document from URL: {url}")
            doc = self.doc_fetcher.fetch(title, url)
            langchain_doc = doc.to_langchain_document()
            self.retriever_manager.vector_db_manager.add_documents([langchain_doc])
            print(f"Successfully added document from URL: {url}")
        except Exception as e:
            print(f"Failed to fetch document from URL '{url}': {e}")

    def query(self, query, retriever_type="similarity", k=5, similarity_threshold=0.7):
        """
        Execute the RAG pipeline: retrieve documents and generate an answer.
        """
        context = self.retriever_manager.retrieve_context(
            question=query, k=k, search_type=retriever_type, similarity_threshold=similarity_threshold
        )

        if not context or context["context"] == "주어진 정보에서 질문에 대한 정보를 찾을 수 없습니다.":
            return context

        # Convert retrieved context into LangChainDocument objects
        documents = [
            LangChainDocument(page_content=ref.get("context", ""), metadata=ref)
            for ref in context.get("references", [])
        ]

        # Pass the properly formatted documents to generate_answer
        return self.answer_generator.generate_answer(question=query, documents=documents)