from flask import current_app
from langchain.schema import AIMessage, HumanMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from models.models import LLMPrompt  # LLMPrompt 모델 가져오기
from services.prompt import get_default_prompt_template
from operator import itemgetter
from services.chat_service import ChatService
import json

class ChatGenerator:
    def __init__(self, retriever):
        self.llm = GoogleGenerativeAI(model="models/gemini-1.5-flash", temperature=0.7)
        self.retriever = retriever  # 외부에서 전달된 벡터 검색 retriever
        self.prompt = get_default_prompt_template()

        self.chain = (
            {
                "instruction": itemgetter("instruction"),
                "context": itemgetter("context"), # 문서 검색기
                "question": itemgetter("question"),  # 입력을 그대로 전달하는 Runnable
                "chat_history": itemgetter("chat_history"),
            }
            | self.prompt  # 프롬프트 생성
            | self.llm # LLM 실행
            | StrOutputParser()  # 출력 파싱
        )

        self.message_history_store = {}

        # 활성화된 프롬프트 가져오기 및 설정
        with current_app.app_context():
            self.prompt_instruction = self.get_prompt_instruction()
        
        self.set_prompt_template()

        # `RunnableWithMessageHistory` 초기화
        self.rag_with_history = RunnableWithMessageHistory(
            runnable=self.chain,
            get_session_history=self.get_session_history,
            input_messages_key="question",
            history_messages_key="chat_history"
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
        """`prompt.py`에서 가져온 프롬프트 템플릿을 설정"""
        self.prompt = get_default_prompt_template()

    def get_session_history(self, conversation_id: str) -> ChatMessageHistory:
        if conversation_id not in self.message_history_store:
            print(f"🔄 새 대화 히스토리 생성됨: {conversation_id}")
            self.message_history_store[conversation_id] = ChatMessageHistory()
        else:
            print(f"✅ 기존 대화 히스토리 가져오기: {conversation_id}")
        return self.message_history_store[conversation_id]

    def add_user_message(self, conversation_id: str, content: str):
        chat_history = self.get_session_history(conversation_id)
        chat_history.add_message(HumanMessage(content=content))
        print(f"✅ 사용자 메시지 저장됨: {content}")  # 디버깅 로그

    def add_ai_message(self, conversation_id: str, content: str):
        chat_history = self.get_session_history(conversation_id)
        chat_history.add_message(AIMessage(content=content))
        print(f"✅ AI 응답 메시지 저장됨: {content}")  # 디버깅 로그


    def generate_answer(self, conversation_id, question, context):
        """질문과 문맥을 기반으로 LLM을 호출하여 답변 생성"""
        try:
            # context 구조에서 본문과 참조 정보를 분리
            context_text = context.get("context", "문맥 정보가 제공되지 않았습니다.")
            references = context.get("references", [])

            # 대화 히스토리 가져오기
            chat_history_object = ChatService.get_recent_chat_history(conversation_id, 10)
            # JSON 직렬화 가능한 리스트로 변환
            chat_history = [history.to_dict() for history in chat_history_object]
            # 디버깅 로그: 대화 히스토리 출력
            # print(f"📝 대화 히스토리 (conversation_id={conversation_id}):{chat_history}")
            # for i, msg in enumerate(chat_history):
            #     msg_type = "User" if isinstance(msg, HumanMessage) else "AI"
            #     print(f"{i+1}. [{msg_type}] {msg.question} {msg.answer}")
            
            print(f"확인 {self.prompt_instruction}")
            # 디버깅 로그: `invoke()` 호출 시 전달하는 데이터 출력
            input_data = {
                "instruction": self.prompt_instruction,
                "chat_history": chat_history,
                "question": question,
                "context": context_text
            }
            print(f"📊 `invoke()` Input Data: {chat_history}")

            # response = self.rag_with_history.invoke(input_data)
            input_data_str = json.dumps(input_data, indent=4, ensure_ascii=False)
            response = self.llm.invoke(input_data_str)
            # response = self.rag_with_history.invoke(
            #     {
            #         "instruction": self.prompt_instruction,
            #         "chat_history": chat_history,
            #         "question": question,
            #         "context": context_text
            #     },
            #     config={"configurable": {"session_id": conversation_id}},
            # )
            print(f"📝 최종 응답:\n{response}")
            answer = response["output"] if isinstance(response, dict) else response
            # 사용자 질문 메시지 추가
            self.add_user_message(conversation_id, question)
            # AI 응답 메시지 저장
            self.add_ai_message(conversation_id, answer)

            # 참조 문서 정보를 답변에 추가
            if references:
                reference_texts = "\n".join([f"- {ref['title']} ({ref['url']})" for ref in references])
                answer += f"\n\n참고 자료:\n{reference_texts}"

            # AI 응답 메시지 추가
            self.add_ai_message(user_id, answer)
            return answer

        except Exception as e:
            print(f"❌ Chain 호출 오류: {e}")
            return "답변을 생성하는 중 오류가 발생했습니다."