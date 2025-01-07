from api import create_app
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# Flask 앱 생성 및 실행
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)