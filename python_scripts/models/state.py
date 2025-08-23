from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from models.schemas import DocumentChunk, DocumentSummary, NewsItem


class IndexingState(TypedDict):
    """인덱싱 + 요약 생성용 상태"""

    # 문서 관련
    document_id: str
    corp_name: str
    file_path: str
    document_content: str
    chunks: List[DocumentChunk]

    # 요약 관련
    summary: Optional[DocumentSummary]
    summary_generated: bool

    # Metadata
    processing_stage: str  # 'reading', 'chunking', 'summarizing', 'completed'
    error_message: Optional[str]
    start_time: Optional[float]
    processing_times: Dict[str, float]


class QueryState(TypedDict):
    """질의응답용 상태"""

    # 기본 정보
    document_id: str
    corp_name: str
    question: str

    # 검색 및 분석
    relevant_chunks: List[DocumentChunk]
    search_results: List[NewsItem]
    include_news: bool

    # 분석 결과
    analysis_result: Optional[str]
    confidence_score: Optional[float]

    # 메타데이터
    processing_stage: str  # 'searching', 'analyzing', 'completed'
    error_message: Optional[str]
    start_time: Optional[float]
    processing_times: Dict[str, float]
