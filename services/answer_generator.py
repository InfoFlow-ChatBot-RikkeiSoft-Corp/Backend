from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate

class AnswerGenerator:
    def __init__(self, model="models/gemini-1.5-flash", temperature=0.7):
        """
        Google Generative AI 설정
        """
        self.llm = GoogleGenerativeAI(model=model, temperature=temperature)
        self.prompt_template = PromptTemplate.from_template(
            """You are a helpful assistant that provides answers based on the given documents.
            Here are the documents:
            {documents}
            Question: {query}
            Answer:"""
        )

    def generate_answer(self, question, documents):
        """
        질문과 문서 데이터를 기반으로 응답 생성.
        """
        if not documents:
            return "Cannot find answer from the information given."

        docs_content = "\n".join([f"Document {i + 1}: {doc.page_content}" for i, doc in enumerate(documents)])
        full_prompt = self.prompt_template.format(documents=docs_content, query=question)
        return self.llm(full_prompt).content
