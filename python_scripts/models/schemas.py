from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Request Models
class DocumentIndexRequest(BaseModel):
    document_id: str = Field(..., description="문서 ID - 접수 번호")
    corp_name: str = Field(..., description="기업명")
    file_path: str = Field(..., description="Java에서 생성한 파일 경로")


class QueryRequest(BaseModel):
    document_id: str = Field(..., description="문서 ID  - 접수 번호")
    question: str = Field(..., description="질문", min_length=5)
    include_news: Optional[bool] = Field(
        None, description="뉴스 검색 포함 여부 (AI 자동 판단시 None)"
    )


# Response Models
class DocumentSummary(BaseModel):
    company_overview: str = Field(..., description="기업 개요")
    financial_highlights: str = Field(..., description="재무 하이라이트")
    key_changes: str = Field(..., description="주요 변화사항")
    notable_points: str = Field(..., description="주목할 점")


class IndexingResult(BaseModel):
    document_id: str
    status: ProcessingStatus
    summary: Optional[DocumentSummary] = None
    total_chunks: Optional[int] = None
    processing_time: Optional[float] = None
    error_message: Optional[str] = None


class NewsItem(BaseModel):
    title: str
    description: str
    pub_date: str
    link: str
    relevance_score: float


class AnalysisResult(BaseModel):
    answer: str
    confidence_score: float
    relevant_chunks: List[str]
    related_news: List[NewsItem]
    analysis_time: float
    news_included: bool = Field(..., description="뉴스가 포함되었는지 여부")


class QueryResponse(BaseModel):
    document_id: str
    question: str
    result: AnalysisResult
    timestamp: datetime


# Internal Models
class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    chunk_type: str  # 'text', 'table', 'structured'
    section: str
    page: Optional[int] = None
    metadata: Dict[str, Any] = {}


class EmbeddedChunk(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
