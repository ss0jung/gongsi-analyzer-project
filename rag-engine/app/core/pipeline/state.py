from typing import Dict, Any, List, Optional
from langchain.schema import Document
from typing_extensions import TypedDict


class AnalysisState(TypedDict):
    """문서 분석 파이프라인의 상태를 정의"""

    # 입력 데이터
    file_path: str
    metadata: Dict[str, Any]
    step: str  # "index", "summarize", "query"

    # 문서 처리 관련 - Document 객체 추가
    raw_docs: Optional[List[Document]]
    doc_id: Optional[str]
    doc_content: Optional[str]
    chunks: Optional[List[Document]]  # 청크도 Document 객체로 변경
    total_chunks: Optional[int]

    # 부모-자식 청킹 관련 추가
    parent_chunks: Optional[List[Document]]
    child_chunks: Optional[List[Document]]
    parent_child_map: Optional[Dict[str, str]]

    # 요약 관련
    summary: Optional[Dict[str, Any]]

    # 질의응답 관련
    query: Optional[str]
    answer: Optional[str]
    sources: Optional[List[Document]]
    confidence: Optional[float]

    # 분기 제어
    processing_status: Optional[str]  # "processing", "completed", "failed"

    # 에러 처리
    error: Optional[str]
    retry_count: Optional[int]
