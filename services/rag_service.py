class RAGService:
    def __init__(self, retriever_manager, answer_generator):
        self.retriever_manager = retriever_manager
        self.answer_generator = answer_generator

    def generate_response(self, question):
        """
        RAG 파이프라인을 통해 최종 응답을 생성.
        """
        context = self.retriever_manager.retrieve_context(question)
        answer = self.answer_generator.generate_answer(question, context)
        return answer
