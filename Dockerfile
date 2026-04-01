FROM python:3.12-slim

WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY mcp_server/ mcp_server/
COPY database/ database/
COPY parsers/ parsers/
COPY app/ app/
COPY data/ data/
COPY verify_db.py .

# DB 검증 (빌드 시 확인)
RUN python verify_db.py

# 기본: 웹 서버 (docker-compose에서 서비스별 override)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
