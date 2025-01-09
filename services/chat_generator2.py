import numpy as np
from langchain_google_genai import GoogleGenerativeAI
from services.vector_db_manager import VectorDBManager


class ChatGenerator:
    def __init__(self,vector_db_manager):
        self.vector_db_manager = vector_db_manager

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
