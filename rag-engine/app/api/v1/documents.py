from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.core.pipeline.graph import create_analysis_pipeline

router = APIRouter()


# Pydantic 모델 정의
class DocumentIndexRequest(BaseModel):
    file_path: str
    company_name: Optional[str] = None


class DocumentIndexResponse(BaseModel):
    file_path: str
    document_id: str
    status: str
    message: str
    summary: Optional[Dict[str, Any]] = None


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[str]
    confidence: float


# 파이프라인 인스턴스 (싱글톤)
analysis_pipeline = create_analysis_pipeline()


@router.post("/index", response_model=DocumentIndexResponse)
async def index_document(request: DocumentIndexRequest):
    """
    LangGraph를 사용한 문서 인덱싱 및 요약 생성
    """
    try:
        # LangGraph 파이프라인 실행
        result = await analysis_pipeline.ainvoke(
            {
                "file_path": request.file_path,
                "metadata": request.model_dump(),
                "step": "index",
                "retry_count": 0,
            }
        )

        # 에러 체크
        if result.get("processing_status") == "failed":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return DocumentIndexResponse(
            file_path=request.file_path,
            document_id=result.get("document_id"),
            status="completed",
            message="문서 인덱싱 및 요약 생성 완료",
            summary=result.get("summary"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"처리 중 오류 발생: {str(e)}")


@router.post("/{document_id}/query", response_model=QueryResponse)
async def query_document(document_id: str, request: QueryRequest):
    """
    LangGraph를 사용한 맥락 기반 질의응답
    """
    try:
        # LangGraph 파이프라인 실행
        result = await analysis_pipeline.ainvoke(
            {
                "document_id": document_id,
                "query": request.query,
                "step": "query",
                "retry_count": 0,
            }
        )

        # 에러 체크
        if result.get("processing_status") == "failed":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return QueryResponse(
            query=request.query,
            answer=result.get("answer"),
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"질의 처리 중 오류: {str(e)}")


@router.get("/{document_id}/summary")
async def get_summary(document_id: str, summary_type: str = "auto"):
    """
    요약본 조회 (조건부 재생성)
    """
    try:
        result = await analysis_pipeline.ainvoke(
            {
                "document_id": document_id,
                "step": "summarize",
                "summary_type": summary_type,
                "retry_count": 0,
            }
        )

        if result.get("processing_status") == "failed":
            raise HTTPException(status_code=500, detail=result.get("error"))

        return result.get("summary")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"요약 조회 중 오류: {str(e)}")
