import numpy as np
from langchain_google_genai import GoogleGenerativeAI

class ChatGenerator:
    def __init__(self):
        # Google Generative AI 임베딩 생성기 초기화
        self.llm = GoogleGenerativeAI(model="models/gemini-1.5-flash")
        
    def generate_embedding(self, query_text):
        """질문을 임베딩 벡터로 변환"""
        embedding = self.embedding_model.embed_query(query_text)
        return embedding

    def build_query(self, query_text):
        """질문을 기반으로 벡터 검색 쿼리 생성"""
        query_embedding = self.generate_embedding(query_text)
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
