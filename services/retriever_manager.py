from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class RetrieverManager:

    def __init__(self, vector_db_manager):
        """
        VectorDBManager 객체를 통해 벡터스토어를 관리.
        """
        self.vector_db_manager = vector_db_manager

    def retrieve_context(self, question, k=3, search_type="similarity", similarity_threshold=0.7):
        """
        질문에 대한 컨텍스트를 검색하고 관련성을 검증합니다.
        """
        try:
            print("\n=== 🔍 Context Retrieval Debug Info ===")
            print(f"Question: {question}")
            print(f"Search params - k: {k}, type: {search_type}, threshold: {similarity_threshold}")

            # 벡터 DB에서 문서 검색
            docs = self.vector_db_manager.search(
                query=question, 
                k=k, 
                search_type=search_type, 
                similarity_threshold=similarity_threshold
            )

            print(f"Found {len(docs)} initial documents")

            if not docs:
                print("❌ No documents found in initial search")
                return {
                    "context": "주어진 정보에서 질문에 대한 정보를 찾을 수 없습니다.",
                    "references": []
                }

            # 검색된 문서의 본문과 메타데이터를 기반으로 컨텍스트 생성
            references = []
            context_list = []
            relevant_docs = []

            for doc in docs:
                # 문서 관련성 점수 계산
                similarity_score = self._calculate_similarity(question, doc.page_content)
                print(f"\nDocument Analysis:")
                print(f"Title: {doc.metadata.get('title', 'No Title')}")
                print(f"Similarity Score: {similarity_score:.3f}")
                print(f"Content Preview: {doc.page_content[:100]}...")
                
                # similarity_threshold보다 높은 점수를 가진 문서만 포함
                if similarity_score >= similarity_threshold:
                    relevant_docs.append(doc)
                    content = doc.page_content
                    metadata = doc.metadata
                    
                    title = metadata.get("title", "제목 없음")
                    url = metadata.get("url", "URL 없음")

                    if content.strip():
                        context_list.append(f"{content}\n출처: {title}" + (f" ({url})" if url != "URL 없음" else ""))
                    
                    references.append({
                        "title": title,
                        "url": url,
                        "content": content,
                        "similarity_score": similarity_score
                    })
                    print(f"✅ Document passed threshold check")
                else:
                    print(f"❌ Document filtered out (below threshold)")

            # 관련 문서가 없는 경우
            if not relevant_docs:
                print("❌ No relevant documents found after filtering")
                return {
                    "context": "주어진 정보에서 질문과 관련된 정보를 찾을 수 없습니다.",
                    "references": []
                }

            # 컨텍스트 본문 조합
            context = "\n\n".join(context_list)
            print(f"\nFinal context length: {len(context)} characters")
            print(f"Number of relevant documents: {len(relevant_docs)}")
            print("=== End Debug Info ===\n")

            return {
                "context": context,
                "references": references
            }

        except Exception as e:
            print(f"❌ Error during context retrieval: {e}")
            raise RuntimeError(f"Error during context retrieval: {e}")

    def _calculate_similarity(self, question, content):
        """
        질문과 문서 내용 간의 유사도를 계산합니다.
        """
        try:
            # 벡터 임베딩 생성
            question_embedding = self.vector_db_manager.generate_embedding(question)
            content_embedding = self.vector_db_manager.generate_embedding(content)
            
            # 코사인 유사도 계산
            similarity = self._cosine_similarity(question_embedding, content_embedding)
            return similarity

        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.0

    def _cosine_similarity(self, vec1, vec2):
        """
        두 벡터 간의 코사인 유사도를 계산합니다.
        """
        import numpy as np
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        return dot_product / (norm1 * norm2)