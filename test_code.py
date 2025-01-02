import requests

BASE_URL = "http://127.0.0.1:8000"

# 1. TXT 파일 업로드 테스트
def test_upload_txt():
    file_path = "test.txt"  # 테스트용 TXT 파일 경로
    with open(file_path, "w") as f:
        f.write("This is a test file.")  # 테스트용 텍스트 작성

    with open(file_path, "rb") as f:
        response = requests.post(
            f"{BASE_URL}/upload-txt/",
            files={"file": f}
        )
    print("Upload Response:", response.json())

# 2. 업로드된 파일 목록 테스트
def test_list_txt():
    response = requests.get(f"{BASE_URL}/list-txt/")
    print("List TXT Response:", response.json())

# 3. 특정 파일 다운로드 테스트
def test_download_txt(file_name):
    response = requests.get(f"{BASE_URL}/download-txt/{file_name}")
    if response.status_code == 200:
        with open(file_name, "wb") as f:
            f.write(response.content)
        print(f"File '{file_name}' downloaded successfully.")
    else:
        print("Download Response:", response.json())

# 실행
if __name__ == "__main__":
    # FastAPI 서버가 실행 중이어야 테스트가 동작합니다.
    print("Starting Tests...")
    
    # 1. TXT 파일 업로드 테스트
    test_upload_txt()
    
    # 2. 업로드된 파일 목록 조회 테스트
    test_list_txt()
    
    # 3. 특정 파일 다운로드 테스트
    test_download_txt("test.txt")
