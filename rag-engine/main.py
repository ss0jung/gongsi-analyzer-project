from dotenv import load_dotenv
from fastapi import FastAPI
from app.api.v1 import documents

load_dotenv()  # .env 파일 로드

# FastAPI 인스턴스 생성
app = FastAPI(
    title="공시 분석 플랫폼 API",
    description="AI 기반 공시 문서 분석 및 요약 서비스",
    version="1.0.0",
)

app.router.prefix = "/api/v1"
app.include_router(documents.router, prefix="/documents", tags=["Documents"])


@app.get("/")
async def root():
    return {"message": "공시 분석 플랫폼 API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
