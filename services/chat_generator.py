from langchain.schema import AIMessage, HumanMessage, SystemMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from vector_db_manager import VectorDBManager

class ChatGenerator:
    def __init__(self, vector_db_manager):
        self.vector_db_manager = vector_db_manager
        self.llm = GoogleGenerativeAI(model="models/gemini-1.5-flash", temperature=0.7)
        self.message_history_store = {}

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

    def build_query(self, query_text):
        """질문을 기반으로 벡터 검색 쿼리 생성"""
        query_embedding = self.vector_db_manager.generate_embedding(query_text)
        query_body = {
            "size": 3,  # 상위 3개의 검색 결과 반환
            "query": {
                "knn": {
                    "vector_embedding": {
                        "vector": query_embedding,
                        "k": 3  # 최근접 이웃 수
                    }
                }
            }
        }
        return query_body

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
        """질문과 문맥을 기반으로 LLM을 호출하여 답변 생성"""
        # context 구조에서 본문과 참조 정보를 분리
        context_text = context.get("context", "문맥 정보가 제공되지 않았습니다.")
        references = context.get("references", [])

        # 사용자 질문 메시지 추가
        self.add_user_message(user_id, question)

        # 대화 내역 가져오기
        chat_history = self.get_session_history(user_id).messages

        # LLM 호출 메시지 리스트 생성
        input_messages = chat_history + [HumanMessage(content=f"질문: {question}\n문맥: {context_text}")]

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

