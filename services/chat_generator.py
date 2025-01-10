from flask import current_app
from langchain.schema import AIMessage, HumanMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from models.models import LLMPrompt, db  # LLMPrompt 모델 가져오기

class ChatGenerator:
    def __init__(self, retriever_manager):
        self.llm = GoogleGenerativeAI(model="models/gemini-1.5-flash", temperature=0.7)
        self.message_history_store = {}
        self.retriever = retriever_manager.vectorstore.as_retriever()

        # 활성화된 프롬프트 가져오기 및 설정
        with current_app.app_context():
            self.prompt_instruction = self.get_prompt_instruction()
        # 프롬프트 내용 출력
        # print(f"🔎 현재 프롬프트 내용:\n{self.prompt_instruction}\n")
        self.set_prompt_template()

        # `RunnableWithMessageHistory` 초기화
        self.rag_with_history = RunnableWithMessageHistory(
            runnable=self.llm,
            get_session_history=self.get_session_history,
            input_messages_key="chat_history",
            history_messages_key="history"
        )

    def get_prompt_instruction(self):
        """DB에서 활성화된 프롬프트 설명 부분 가져오기"""
        active_prompt = LLMPrompt.query.filter_by(is_active=True).first()
        if active_prompt:
            print(f"✅ 활성화된 프롬프트 로드됨: {active_prompt.prompt_name}")
            return active_prompt.prompt_text  # 설명 부분만 반환
        else:
            print("❌ 활성화된 프롬프트가 없습니다. 기본 프롬프트를 사용합니다.")
            return "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Answer in Korean."

    def set_prompt_template(self):
        """프롬프트 템플릿 설정"""
        self.prompt = PromptTemplate.from_template(
            f"""{self.prompt_instruction}

            #Previous Chat History:
            {{chat_history}}

            #Question: 
            {{question}} 

            #Context: 
            {{context}} 

            #Answer:"""
        )
        # print(self.prompt)

    def get_session_history(self, user_id: str) -> ChatMessageHistory:
        if user_id not in self.message_history_store:
            self.message_history_store[user_id] = ChatMessageHistory()
        return self.message_history_store[user_id]

    def add_user_message(self, user_id: str, content: str):
        chat_history = self.get_session_history(user_id)
        chat_history.add_message(HumanMessage(content=content))

    def add_ai_message(self, user_id: str, content: str):
        chat_history = self.get_session_history(user_id)
        chat_history.add_message(AIMessage(content=content))

    def generate_answer(self, user_id, question, context):
        # context 구조에서 본문과 참조 정보를 분리
        context_text = context.get("context", "문맥 정보가 제공되지 않았습니다.")
        references = context.get("references", [])

        # 사용자 질문 메시지 추가
        self.add_user_message(user_id, question)

        # 대화 내역 가져오기
        chat_history = self.get_session_history(user_id).messages
        # chat_history = "\n".join([message.content for message in self.get_session_history(user_id).messages])
        # 프롬프트 템플릿에 데이터를 삽입하여 완성된 프롬프트 생성
        formatted_prompt = self.prompt.format(
            chat_history=chat_history,
            question=question,
            context=context_text
        )

        # 디버깅용 출력
        print(f"📝 최종 프롬프트:\n{formatted_prompt}")

        # LLM 호출 메시지 리스트 생성
        input_messages = [HumanMessage(content=formatted_prompt)]

        # LLM 호출 메시지 리스트 생성
        # input_messages = chat_history + [HumanMessage(content=f"질문: {question}\n문맥: {context_text}")]

        try:
            # LLM 호출 및 응답 생성
            response = self.llm.invoke(input_messages)
            answer = response.content if isinstance(response, AIMessage) else response

            # 참조 문서 정보를 답변에 추가
            if references:
                reference_texts = "\n".join([f"- {ref['title']} ({ref['url']})" for ref in references])
                answer += f"\n\n참고 자료:\n{reference_texts}"

            # AI 응답 메시지 추가
            self.add_ai_message(user_id, answer)
            return answer
        except Exception as e:
            print(f"❌ LLM 호출 오류: {e}")
            return "답변을 생성하는 중 오류가 발생했습니다."