import requests

BASE_URL = "http://127.0.0.1:8000"

# 1. DOC/DOCX 파일 업로드 테스트
def test_upload_docs():
    file_path = "test.docx"  # 테스트용 DOCX 파일 경로
    with open(file_path, "wb") as f:
        f.write(b"This is a test document.")  # 간단한 테스트 문서 생성

    with open(file_path, "rb") as f:
        response = requests.post(
            f"{BASE_URL}/upload-docs/",
            files={"file": f}
        )
    print("Upload Response:", response.json())

# 2. 업로드된 파일 목록 테스트
def test_list_docs():
    response = requests.get(f"{BASE_URL}/list-docs/")
    print("List DOC/DOCX Response:", response.json())

# 3. 특정 파일 다운로드 테스트
def test_download_docs(file_name):
    response = requests.get(f"{BASE_URL}/download-docs/{file_name}")
    if response.status_code == 200:
        with open(f"downloaded_{file_name}", "wb") as f:
            f.write(response.content)
        print(f"File '{file_name}' downloaded successfully.")
    else:
        print("Download Response:", response.json())

# 테스트 실행
if __name__ == "__main__":
    print("Starting Tests...")
    
    # 1. DOC/DOCX 파일 업로드 테스트
    test_upload_docs()  # test.docx 파일 업로드 테스트
    
    # 2. 업로드된 파일 목록 조회 테스트
    test_list_docs()
    
    # 3. 특정 파일 다운로드 테스트
    test_download_docs("test.docx")
