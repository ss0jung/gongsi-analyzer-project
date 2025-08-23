from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from config import settings
from api import documents, query

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 시 실행"""

    # 시작 시
    logger.info("🚀 공시 분석 AI API 서버 시작")
    logger.info(f"📊 OpenAI Model: {settings.OPENAI_MODEL}")
    logger.info(f"🔗 Embedding Model: {settings.EMBEDDING_MODEL}")
    logger.info(f"💾 ChromaDB: {settings.CHROMA_PERSIST_DIR}")

    # ChromaDB 초기화 테스트
    try:
        from services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService()
        stats = embedding_service.get_collection_stats()
        logger.info(f"📈 벡터 DB 연결 성공: {stats}")
    except Exception as e:
        logger.error(f"❌ 벡터 DB 연결 실패: {e}")

    # API 키 확인
    required_keys = {
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "NAVER_CLIENT_ID": settings.NAVER_CLIENT_ID,
        "NAVER_CLIENT_SECRET": settings.NAVER_CLIENT_SECRET,
    }

    for key_name, key_value in required_keys.items():
        if not key_value:
            logger.warning(f"⚠️  {key_name}이 설정되지 않았습니다.")
        else:
            logger.info(f"✅ {key_name} 설정 완료")

    yield

    # 종료 시
    logger.info("🛑 공시 분석 AI API 서버 종료")


# FastAPI 앱 생성
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description="""
    ## 📊 공시 분석 AI API
    
    Java 서비스에서 전처리된 공시문서를 AI로 분석하여 요약과 질의응답을 제공하는 API입니다.
    
    ### 주요 기능
    - 🔍 **파일 기반 인덱싱**: Java에서 생성한 파일을 읽어 청킹, 임베딩, 자동 요약 생성
    - 📋 **Progressive Disclosure**: 요약본 먼저 제공 → 사용자 선택에 따라 질의응답
    - 💬 **독립적 질의응답**: 문서별 반복 가능한 질의응답 시스템
    - 📰 **뉴스 자동 연동**: AI가 질문을 분석해서 필요시 최신 뉴스 검색
    
    ### 사용 흐름
    1. **Java → 파일 생성** → **인덱싱 요청** → **요약 확인**
    2. **사용자 선택**: 질문하기 또는 종료
    3. **질의응답**: 필요시 반복 가능
    
    ### 워크플로우
    - **인덱싱 워크플로우**: 파일 읽기 → 청킹 → 임베딩 → 요약 (독립적)
    - **질의 워크플로우**: 질문 분석 → RAG 검색 → 뉴스 검색 → AI 답변 (독립적, 반복 가능)
    """,
    lifespan=lifespan,
    debug=settings.DEBUG,
)

# CORS 미들웨어 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록 (companies 라우터 제거)
app.include_router(documents.router)
app.include_router(query.router)


@app.get("/")
async def root():
    """API 루트 엔드포인트"""
    return {
        "service": "공시 분석 AI API",
        "version": settings.APP_VERSION,
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "note": "Java 서비스와 연동하여 파일 기반 문서 분석을 제공합니다.",
        "endpoints": {
            "documents": "/api/v1/documents - 파일 기반 인덱싱 및 요약",
            "query": "/api/v1/query - 독립적 질의응답 시스템",
            "docs": "/docs - Swagger API 문서",
            "redoc": "/redoc - ReDoc API 문서",
        },
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    try:
        health_status = {"api": "healthy", "timestamp": datetime.now().isoformat()}

        # ChromaDB 상태 확인
        try:
            from services.embedding_service import EmbeddingService

            embedding_service = EmbeddingService()
            stats = embedding_service.get_collection_stats()
            health_status["vector_db"] = {
                "status": "healthy",
                "total_chunks": stats.get("total_chunks", 0),
            }
        except Exception as e:
            health_status["vector_db"] = {"status": "unhealthy", "error": str(e)}

        # Naver News API 상태 확인
        try:
            from services.news_service import NaverNewsService

            # 간단한 테스트 (실제 요청 없이 설정만 확인)
            if settings.NAVER_CLIENT_ID and settings.NAVER_CLIENT_SECRET:
                health_status["news_api"] = {"status": "configured"}
            else:
                health_status["news_api"] = {"status": "not_configured"}
        except Exception as e:
            health_status["news_api"] = {"status": "error", "error": str(e)}

        # 전체 상태 결정
        all_healthy = all(
            (
                service.get("status") in ["healthy", "configured"]
                if isinstance(service, dict)
                else service == "healthy"
            )
            for service in health_status.values()
            if isinstance(service, (dict, str))
        )

        health_status["overall"] = "healthy" if all_healthy else "degraded"

        return health_status

    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "overall": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
        )


@app.exception_handler(404)
async def not_found_handler(request, exc):
    """404 에러 핸들러"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": "요청하신 리소스를 찾을 수 없습니다.",
            "path": str(request.url),
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """500 에러 핸들러"""
    logger.error(f"Internal server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "서버 내부 오류가 발생했습니다.",
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.get("/api/v1/info")
async def api_info():
    """API 정보 조회"""
    try:
        from services.embedding_service import EmbeddingService

        embedding_service = EmbeddingService()
        stats = embedding_service.get_collection_stats()

        return {
            "service": {
                "name": settings.APP_TITLE,
                "version": settings.APP_VERSION,
                "model": settings.OPENAI_MODEL,
                "embedding_model": settings.EMBEDDING_MODEL,
            },
            "features": {
                "file_based_indexing": True,
                "separated_workflows": True,
                "auto_news_detection": True,
                "progressive_disclosure": True,
            },
            "settings": {
                "max_summary_length": settings.SUMMARY_MAX_LENGTH,
                "chunk_size": settings.CHUNK_SIZE,
                "chunk_overlap": settings.CHUNK_OVERLAP,
                "summary_timeout": f"{settings.SUMMARY_TIMEOUT}초",
            },
            "database": {
                "collection_name": settings.COLLECTION_NAME,
                "total_documents": stats.get("total_chunks", 0),
                "persist_directory": settings.CHROMA_PERSIST_DIR,
            },
            "integration": {
                "java_service": "파일 기반 연동",
                "workflow_type": "분리형 (인덱싱 + 질의)",
                "news_detection": "자동 판단",
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"API 정보 조회 중 오류: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG, log_level="info"
    )
