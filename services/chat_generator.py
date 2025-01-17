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
        """
        질문과 문맥을 기반으로 LLM을 호출하여 답변 생성.
        """
        try:
            # 디버깅을 위한 로그 추가
            print("\n=== Debug Info ===")
            print("Received context:", context)
            
            # 1. 문맥 정보 분리
            context_text = context.get("context", "문맥 정보가 제공되지 않았습니다.")
            references = context.get("references", [])

            # 2. 대화 히스토리 가져오기
            chat_history_object = ChatService.get_recent_chat_history(conversation_id, 10)
            chat_history = [history.to_dict() for history in chat_history_object]

            # 디버깅 로그: 대화 히스토리 확인
            print(f"📄 Debug: Retrieved Chat History for conversation_id={conversation_id}")
            for i, msg in enumerate(chat_history):
                print(f"  - {i + 1}: {msg}")

            # 3. LLM 호출을 위한 데이터 준비
            input_data = {
                "instruction": self.prompt_instruction,
                "chat_history": chat_history,
                "question": question,
                "context": context_text,
            }

            # 디버깅 로그: 입력 데이터 확인
            input_data_str = json.dumps(input_data, indent=4, ensure_ascii=False)
            print(f"📝 Debug: Input Data for LLM:\n{input_data_str}")

            # 4. LLM 호출 및 응답 처리
            response = self.llm.invoke(input_data_str)
            print(f"✅ Debug: LLM Response:\n{response}")

            # 응답 내용 처리
            answer = response["output"] if isinstance(response, dict) else response

            # 5. 사용자 질문 메시지 추가
            self.add_user_message(conversation_id, question)

            # 6. AI 응답 메시지 저장
            self.add_ai_message(conversation_id, answer)

            # 참고 자료 형식 수정
            if context.get("references"):
                reference_texts = []
                print("\nProcessing references:")
                for ref in context["references"]:
                    print("Original reference:", ref)
                    title = ref.get("title", "").replace("string ", "") if ref.get("title") else ""
                    url = ref.get("url", "").replace("string ", "") if ref.get("url") else ""
                    print(f"Cleaned title: {title}")
                    print(f"Cleaned url: {url}")
                    
                    if url and url != "URL 없음":
                        reference_texts.append(f"- {title} ({url})")
                    else:
                        reference_texts.append(f"- {title}")
                
                if reference_texts:
                    print("\nFinal reference texts:", reference_texts)
                    answer += "\n\n참고 자료:\n" + "\n".join(reference_texts)

            print("\nFinal answer:", answer)
            print("=== End Debug Info ===\n")

            return answer

        except Exception as e:
            print(f"Error generating answer: {e}")
            raise RuntimeError(f"Error generating answer: {e}")
