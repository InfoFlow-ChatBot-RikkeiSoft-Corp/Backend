# 1. 베이스 이미지 설정
FROM python:3.11.9-slim

# 2. 작업 디렉토리 생성 및 설정
WORKDIR /app

# 3. 종속성 파일 복사 및 설치
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 4. 애플리케이션 코드 복사
COPY . .

# 5. 환경 변수 설정
ENV PYTHONUNBUFFERED=1

# 6. Flask 애플리케이션 실행
CMD ["python", "main.py"]
