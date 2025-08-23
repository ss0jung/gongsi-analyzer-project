from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, Any
import time
import asyncio

from models.state import IndexingState, QueryState
from agents.summary_agent import SummaryAgent
from agents.analysis_agent import AnalysisAgent
from services.embedding_service import EmbeddingService
from utils.chunking import HybridDocumentChunker


class DocumentIndexingWorkflow:
    """문서 인덱싱 + 요약 생성 워크플로우"""

    def __init__(self):
        self.summary_agent = SummaryAgent()
        self.embedding_service = EmbeddingService()
        self.chunker = HybridDocumentChunker()

        # 워크플로우 그래프 초기화
        self.workflow = self._create_workflow()
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)

    def _create_workflow(self) -> StateGraph:
        """인덱싱 워크플로우 그래프 생성"""

        workflow = StateGraph(IndexingState)

        # 노드 추가
        workflow.add_node("read_document", self.read_document_node)
        workflow.add_node("process_chunks", self.process_chunks_node)
        workflow.add_node("generate_summary", self.generate_summary_node)

        # 순차적 플로우
        workflow.set_entry_point("read_document")
        workflow.add_edge("read_document", "process_chunks")
        workflow.add_edge("process_chunks", "generate_summary")
        workflow.add_edge("generate_summary", END)

        return workflow

    async def read_document_node(self, state: IndexingState) -> IndexingState:
        """Java에서 생성한 파일을 읽는 노드"""
        state["processing_stage"] = "reading"
        state["start_time"] = time.time()

        try:
            file_path = state.get("file_path")

            if not file_path:
                state["error_message"] = "파일 경로가 제공되지 않았습니다."
                return state

            # 파일 읽기
            document_content = await self._read_file_async(file_path)

            if not document_content:
                state["error_message"] = f"파일을 읽을 수 없습니다: {file_path}"
                return state

            state["document_content"] = document_content
            state["processing_times"] = {"read_file": time.time() - state["start_time"]}

        except Exception as e:
            state["error_message"] = f"파일 읽기 중 오류: {str(e)}"

        return state

    async def _read_file_async(self, file_path: str) -> str:
        """비동기로 파일 읽기"""

        def read_file():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
            except Exception as e:
                raise Exception(f"파일 읽기 실패: {str(e)}")

        # 파일 I/O를 비동기로 실행
        return await asyncio.get_event_loop().run_in_executor(None, read_file)

    async def process_chunks_node(self, state: IndexingState) -> IndexingState:
        """문서 청킹 및 임베딩 노드"""
        state["processing_stage"] = "chunking"
        start_time = time.time()

        try:
            document_content = state.get("document_content", "")
            document_id = state.get("document_id", "")
            corp_name = state.get("corp_name", "")

            if not document_content:
                state["error_message"] = "문서 내용이 없습니다."
                return state

            # 1. 문서 청킹
            chunks = self.chunker.chunk_document(document_content, document_id)

            if not chunks:
                state["error_message"] = "문서 청킹에 실패했습니다."
                return state

            # 청크에 기업명 메타데이터 추가
            for chunk in chunks:
                chunk.metadata["corp_name"] = corp_name

            # 2. 임베딩 생성 및 저장
            embedded_chunks = await self.embedding_service.embed_chunks(chunks)

            state["chunks"] = chunks
            state["processing_times"]["chunking"] = time.time() - start_time

        except Exception as e:
            state["error_message"] = f"청킹 처리 중 오류: {str(e)}"

        return state

    async def generate_summary_node(self, state: IndexingState) -> IndexingState:
        """요약 생성 노드"""
        state["processing_stage"] = "summarizing"

        try:
            # SummaryAgent 호출 (기존 인터페이스 호환)
            legacy_state = {
                "document_content": state.get("document_content", ""),
                "corp_name": state.get("corp_name", ""),
                "processing_times": state.get("processing_times", {}),
            }

            result_state = await self.summary_agent.generate_summary(legacy_state)

            # 결과 복사
            state["summary"] = result_state.get("summary")
            state["summary_generated"] = result_state.get("summary_generated", False)
            state["processing_times"].update(result_state.get("processing_times", {}))

            if result_state.get("error_message"):
                state["error_message"] = result_state["error_message"]
            else:
                state["processing_stage"] = "completed"

        except Exception as e:
            state["error_message"] = f"요약 생성 중 오류: {str(e)}"

        return state

    async def run_indexing(
        self, document_id: str, corp_name: str, file_path: str
    ) -> IndexingState:
        """인덱싱 워크플로우 실행"""

        initial_state: IndexingState = {
            "document_id": document_id,
            "corp_name": corp_name,
            "file_path": file_path,
            "document_content": "",
            "chunks": [],
            "summary": None,
            "summary_generated": False,
            "processing_stage": "pending",
            "error_message": None,
            "start_time": None,
            "processing_times": {},
        }

        try:
            config = {"configurable": {"thread_id": f"indexing_{document_id}"}}
            result = await self.app.ainvoke(initial_state, config=config)
            return result

        except Exception as e:
            initial_state["error_message"] = f"워크플로우 실행 중 오류: {str(e)}"
            initial_state["processing_stage"] = "failed"
            return initial_state


class DocumentQueryWorkflow:
    """질의응답 워크플로우 (독립적)"""

    def __init__(self):
        self.analysis_agent = AnalysisAgent()
        self.embedding_service = EmbeddingService()

        # 워크플로우 그래프 초기화
        self.workflow = self._create_workflow()
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)

    def _create_workflow(self) -> StateGraph:
        """질의응답 워크플로우 그래프 생성"""

        workflow = StateGraph(QueryState)

        # 노드 추가
        workflow.add_node("analyze_query", self.analyze_query_node)

        # 단일 노드 플로우
        workflow.set_entry_point("analyze_query")
        workflow.add_edge("analyze_query", END)

        return workflow

    async def analyze_query_node(self, state: QueryState) -> QueryState:
        """질의 분석 노드"""
        state["processing_stage"] = "analyzing"
        start_time = time.time()

        try:
            # 뉴스 포함 여부 자동 판단
            if state.get("include_news") is None:
                state["include_news"] = self._should_include_news(
                    state.get("question", "")
                )

            # AnalysisAgent 호출 (기존 인터페이스 호환)
            legacy_state = {
                "question": state.get("question", ""),
                "document_id": state.get("document_id", ""),
                "corp_name": state.get("corp_name", ""),
                "include_news": state.get("include_news", False),
                "processing_times": {},
            }

            result_state = await self.analysis_agent.analyze_query(legacy_state)

            # 결과 복사
            state["relevant_chunks"] = result_state.get("relevant_chunks", [])
            state["search_results"] = result_state.get("search_results", [])
            state["analysis_result"] = result_state.get("analysis_result")
            state["confidence_score"] = result_state.get("confidence_score")
            state["processing_times"] = result_state.get("processing_times", {})

            if result_state.get("error_message"):
                state["error_message"] = result_state["error_message"]
            else:
                state["processing_stage"] = "completed"

        except Exception as e:
            state["error_message"] = f"질의 분석 중 오류: {str(e)}"

        return state

    def _should_include_news(self, question: str) -> bool:
        """질문 내용을 분석해서 뉴스 검색 필요 여부 자동 판단"""

        # 시간 관련 키워드
        time_keywords = [
            "최근",
            "현재",
            "요즘",
            "지금",
            "올해",
            "작년",
            "전망",
            "계획",
            "향후",
        ]

        # 시장/경쟁 관련 키워드
        market_keywords = ["경쟁", "시장", "업계", "동향", "트렌드", "비교", "경쟁사"]

        # 실시간 정보가 필요한 키워드
        realtime_keywords = ["주가", "시세", "평가", "전문가", "분석가", "의견", "전망"]

        # 변화/성장 관련 키워드
        change_keywords = ["증가", "감소", "성장", "하락", "변화", "개선", "악화"]

        question_lower = question.lower()

        all_keywords = (
            time_keywords + market_keywords + realtime_keywords + change_keywords
        )

        # 키워드 매칭 점수 계산
        matched_count = sum(1 for keyword in all_keywords if keyword in question_lower)

        # 2개 이상의 키워드가 매칭되면 뉴스 검색 포함
        return matched_count >= 1

    async def run_query(
        self, document_id: str, corp_name: str, question: str, include_news: bool = None
    ) -> QueryState:
        """질의응답 워크플로우 실행"""

        initial_state: QueryState = {
            "document_id": document_id,
            "corp_name": corp_name,
            "question": question,
            "relevant_chunks": [],
            "search_results": [],
            "include_news": include_news,
            "analysis_result": None,
            "confidence_score": None,
            "processing_stage": "pending",
            "error_message": None,
            "start_time": time.time(),
            "processing_times": {},
        }

        try:
            config = {
                "configurable": {"thread_id": f"query_{document_id}_{hash(question)}"}
            }
            result = await self.app.ainvoke(initial_state, config=config)
            return result

        except Exception as e:
            initial_state["error_message"] = f"워크플로우 실행 중 오류: {str(e)}"
            initial_state["processing_stage"] = "failed"
            return initial_state


# 워크플로우 매니저 (기존 코드와의 호환성을 위해)
class DocumentAnalysisWorkflow:
    """통합 워크플로우 매니저"""

    def __init__(self):
        self.indexing_workflow = DocumentIndexingWorkflow()
        self.query_workflow = DocumentQueryWorkflow()

    async def run_indexing_workflow(
        self, document_id: str, corp_name: str, file_path: str
    ):
        """인덱싱 워크플로우 실행"""
        return await self.indexing_workflow.run_indexing(
            document_id, corp_name, file_path
        )

    async def run_query_workflow(
        self, document_id: str, corp_name: str, question: str, include_news: bool = None
    ):
        """질의응답 워크플로우 실행"""
        return await self.query_workflow.run_query(
            document_id, corp_name, question, include_news
        )
