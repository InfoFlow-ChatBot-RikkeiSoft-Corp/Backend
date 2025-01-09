1. answer_generator.py 
역할: 검색된 문맥과 사용자의 질문을 기반으로 답변 생성.
주요 기능:
Google Generative AI를 사용하여 답변 생성.
프롬프트 템플릿(PromptTemplate)을 활용해 질문 및 문맥을 입력받아 적절한 응답 반환.
2. chat_generator.py 
역할: 대화 기반 질문 처리 및 벡터 검색 쿼리 생성.
주요 기능:
질문을 임베딩 벡터로 변환.
벡터 검색 쿼리를 구성하여 검색 시스템과 통합.
3. docs.py 
역할: 문서 객체 모델 관리.
주요 기능:
문서를 LangChain 호환 Document 객체로 변환.
문서의 주요 내용 발췌 (get_excerpt).
정적 메서드를 통해 웹 및 파일 데이터로부터 Docs 객체 생성.
4. document_fetcher.py 
역할: 문서 로드 및 관리.
주요 기능:
웹 URL에서 문서를 가져와 Docs 객체로 반환.
.docx 파일을 로드하여 Docs 객체로 반환.
5. RAG_manager.py 
역할: 전체 RAG 파이프라인 관리.
주요 기능:
문서 추가(add_documents, fetch_and_add_document).
벡터스토어 검색(retrieve_documents).
답변 생성(검색된 문서를 기반으로 AnswerGenerator 호출).
6. rag_service.py 
역할: RAG 파이프라인 서비스화.
주요 기능:
RetrieverManager와 AnswerGenerator를 통합해 최종 응답 생성.
질문 입력에 따라 문맥 검색 및 답변 생성 수행.
7. retriever_manager.py 
역할: 문맥 검색 및 반환.
주요 기능:
**VectorDBManager**를 활용하여 벡터스토어 검색.
검색된 문서를 텍스트 컨텍스트로 변환하여 반환.
8. vector_db_manager.py 
역할: 벡터스토어의 관리 및 검색 인터페이스 제공.
주요 기능:
벡터스토어 초기화 및 로드.
문서 추가(add_doc_to_db, add_documents).
검색 수행(search, get_retriever).
임베딩 생성(generate_embedding).

질문에 대한 컨텍스트를 검색.
    :param question: 사용자의 질문
    :param k: 반환할 문서 수
    :param search_type: 검색 유형
    :param similarity_threshold: 유사도 임계값
    :return: 검색된 문서들의 내용