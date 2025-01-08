from langchain.schema import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory

class ChatGenerator:
    def __init__(self, retriever_manager):
        self.llm = GoogleGenerativeAI(model="models/gemini-1.5-flash", temperature=0.7)
        self.message_history_store = {}
        self.retriever = retriever_manager.vectorstore.as_retriever()

        # 프롬프트 템플릿 생성
        self.prompt = PromptTemplate.from_template(
            """You are an assistant for question-answering tasks. 
            Use the following pieces of retrieved context to answer the question. 
            If you don't know the answer, just say that you don't know. 
            Answer in Korean.

            #Previous Chat History:
            {chat_history}

            #Question: 
            {question} 

            #Context: 
            {context} 

            #Answer:"""
        )

        # `RunnableWithMessageHistory` 초기화
        self.rag_with_history = RunnableWithMessageHistory(
            runnable=self.llm,
            get_session_history=self.get_session_history,
            input_messages_key="chat_history",
            history_messages_key="history"
        )

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

        # 사용자 질문 메시지 추가
        self.add_user_message(user_id, question)

        # 대화 내역 가져오기
        chat_history = self.get_session_history(user_id).messages

        # LLM 호출 메시지 리스트 생성
        input_messages = chat_history + [HumanMessage(content=f"질문: {question}\n문맥: {context}")]

        try:
            # LLM 호출 및 응답 생성
            response = self.llm.invoke(input_messages)
            answer = response.content if isinstance(response, AIMessage) else response

            # AI 응답 메시지 추가
            self.add_ai_message(user_id, answer)
            return answer
        except Exception as e:
            print(f"❌ LLM 호출 오류: {e}")
            return "답변을 생성하는 중 오류가 발생했습니다."
