from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import PromptTemplate

class AnswerGenerator:
    def __init__(self, model="models/gemini-1.5-flash", temperature=0.7):
        """
        Google Generative AI 설정
        """
        self.llm = GoogleGenerativeAI(model=model, temperature=temperature)
        self.prompt_template = PromptTemplate.from_template(
            """당신은 질문-답변(Question-Answering)을 수행하는 친절한 AI 어시스턴트입니다.
            검색된 다음 문맥(context)을 사용하여 질문(question)에 답하세요.
            만약 주어진 문맥(context)에서 답을 찾을 수 없다면 '주어진 정보에서 질문에 대한 정보를 찾을 수 없습니다'라고 답하세요.
            한글로 답변해 주세요. 단, 기술적인 용어나 이름은 번역하지 않고 그대로 사용해 주세요.

            #Question:
            {question}

            #Context:
            {context}

            #Answer:"""
        )

    def generate_answer(self, question, context):
        """
        질문과 문맥을 기반으로 Google Generative AI를 사용하여 응답 생성.
        """
        prompt = self.prompt_template.format(question=question, context=context)
        return self.llm(prompt)
