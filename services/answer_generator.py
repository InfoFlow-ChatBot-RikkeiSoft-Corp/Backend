from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate

## chat_generator에 통합 가능

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

        # 문서 데이터를 텍스트로 변환하여 프롬프트에 포함
        docs_content = "\n".join([f"Document {i + 1}: {doc.page_content}" for i, doc in enumerate(documents)])
        full_prompt = self.prompt_template.format(documents=docs_content, query=question)

        try:
            # LLM 호출 및 프롬프트 전달
            response = self.llm.invoke(full_prompt)

            # 응답 처리
            if hasattr(response, 'content'):  # 응답이 객체 형태일 때
                answer = response.content
            elif isinstance(response, str):  # 응답이 문자열일 때
                answer = response
            else:
                raise ValueError("Unexpected response format from LLM.")

            # 참조 문서 정보를 답변에 추가
            references = [
                {"title": doc.metadata.get("title", "제목 없음"), "url": doc.metadata.get("url", "URL 없음")}
                for doc in documents
            ]
            if references:
                reference_texts = "\n".join([
                    f"- {ref['title']}" if ref['url'] == "URL 없음" else f"- {ref['title']} ({ref['url']})"
                    for ref in references
                ])
                answer += f"\n\n참고 자료:\n{reference_texts}"

            # 디버깅 로그
            print(f"✅ 최종 응답: {answer}")
            return answer

        except Exception as e:
            print(f"❌ Error generating answer: {e}")  # 디버깅 로그 추가
            raise RuntimeError(f"Error generating answer: {e}")