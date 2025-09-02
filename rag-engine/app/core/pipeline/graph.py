from langgraph.graph import StateGraph, START, END
from .state import AnalysisState
from .nodes import PipelineNodes


def create_analysis_pipeline() -> StateGraph:
    """공시 분석 파이프라인 그래프 생성"""

    # 노드 인스턴스 생성
    nodes = PipelineNodes()

    # 그래프 생성
    workflow = StateGraph(AnalysisState)

    # 노드 추가
    workflow.add_node("document_preprocessor", nodes.document_preprocessor)
    workflow.add_node("chunk_and_embed_document", nodes.chunk_and_embed_document)
    # workflow.add_node("summary_agent", nodes.summary_agent)
    # workflow.add_node("query_agent", nodes.query_agent)
    workflow.add_node("error_handler", nodes.error_handler)
    workflow.add_node("complete_processing", nodes.complete_processing)

    # 시작점 설정
    workflow.add_edge(START, "document_preprocessor")

    workflow.add_edge("document_preprocessor", "chunk_and_embed_document")
    workflow.add_edge("chunk_and_embed_document", "complete_processing")

    # 에러 핸들러에서 재시도 또는 종료
    # workflow.add_conditional_edges(
    #     "error_handler",
    #     lambda state: (
    #         "document_preprocessor"
    #         if state.get("processing_status") == "retrying"
    #         else "complete_processing"
    #     ),
    #     {
    #         "document_preprocessor": "document_preprocessor",
    #         "complete_processing": "complete_processing",
    #     },
    # )

    # 종료점 설정
    workflow.add_edge("complete_processing", END)

    # 그래프 컴파일
    return workflow.compile()
