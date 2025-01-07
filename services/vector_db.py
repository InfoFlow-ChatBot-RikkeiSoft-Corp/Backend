from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Embedding 설정 (Google Generative AI)
embedding = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")

# 전역 FAISS 인스턴스 생성 및 로드
vectorstore_path = "faiss_index"
try:
    vectorstore = FAISS.load_local(vectorstore_path, embedding)
    print("✅ FAISS 벡터스토어가 성공적으로 로드되었습니다.")
except Exception as e:
    print(f"❌ FAISS 벡터스토어 로드 실패: {str(e)}")
    vectorstore = None  # 초기화 실패 시 None 설정
