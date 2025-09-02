from typing import Dict, Any, List
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import PDFPlumberLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain.storage import InMemoryStore
from langchain.retrievers import ParentDocumentRetriever
from pathlib import Path
from .state import AnalysisState
from app.core.config import get_settings
import asyncio
import uuid


class PipelineNodes:
    def __init__(self):
        self.settings = get_settings()

        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
        )

        self.embeddings = OpenAIEmbeddings(
            model=self.settings.openai_embedding_model,
            api_key=self.settings.openai_api_key,
        )

        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.parent_chunk_size,
            chunk_overlap=self.settings.parent_chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", " "],
        )

        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.child_chunk_size,
            chunk_overlap=self.settings.child_chunk_overlap,
            separators=["\n\n", "\n", ".", "!", "?", " "],
        )

        # The vectorstore to use to index the child chunks
        self.vectorstore = Chroma(
            collection_name="split_parents",
            embedding_function=self.embeddings,
            persist_directory=self.setting.chorma_db_path,
        )

        # The storage layer for the parent documents
        self.store = InMemoryStore()

        # Initialize the retriever
        self.retriever = ParentDocumentRetriever(
            vectorstore=self.vectorstore,
            docstore=self.store,
            child_splitter=self.child_splitter,
            parent_splitter=self.parent_splitter,
        )

    async def document_preprocessor(self, state: AnalysisState) -> AnalysisState:
        """PDF 로드 및 전처리"""
        try:
            file_path = state["file_path"]

            # 파일 존재 여부 확인
            if not self._validate_file(file_path):
                state["error"] = f"파일을 찾을 수 없습니다: {file_path}"
                state["processing_status"] = "failed"
                return state

            # 문서 ID 생성
            state["doc_id"] = str(uuid.uuid4())

            # PDF 파일 로드
            loader = PDFPlumberLoader(file_path)
            state["raw_docs"] = loader.load()

            state["processing_status"] = "preprocessing_completed"

            return state

        except Exception as e:
            state["error"] = str(e)
            state["processing_status"] = "failed"
            return state

    async def chunk_and_embed_document(self, state: AnalysisState) -> AnalysisState:
        """문서 청킹"""
        try:
            documents = state["raw_docs"]
            if not documents:
                state["error"] = f"원본 문서가 없습니다."
                state["processing_status"] = "failed"
                return state

            if len(documents) > 50:  # 큰 문서인 경우
                await self.retriever.aadd_documents(documents)
            else:
                self.retriever.add_documents(documents)

            state["processing_status"] = "chunking_completed"
            state["total_chunks"] = len(documents)

            # 벡터스토어 통계 조회
            vectorstore_stats = await self._get_vectorstore_stats()
            state["embedding_stats"] = {
                "total_vectors": vectorstore_stats.get("total_vectors", 0),
                "embedding_model": self.settings.openai_embedding_model,
                "collection_name": self.settings.chroma_collection_name,
            }

            return state

        except Exception as e:
            state["error"] = f"문서 처리 중 오류 :{str(e)}"
            state["processing_status"] = "failed"
            return state

    async def summary_agent(self, state: AnalysisState) -> AnalysisState:
        """문서 요약 생성 에이전트"""
        try:
            document_content = state["document_content"]
            summary_type = state.get("summary_type", "auto")

            # 요약 타입에 따른 프롬프트 선택
            if summary_type == "detailed":
                prompt = self._get_detailed_summary_prompt()
            elif summary_type == "brief":
                prompt = self._get_brief_summary_prompt()
            else:
                prompt = self._get_auto_summary_prompt()

            # LLM 호출
            formatted_prompt = prompt.format(content=document_content)
            response = await self.llm.ainvoke(
                [{"role": "user", "content": formatted_prompt}]
            )

            # 구조화된 요약 생성
            summary = self._parse_summary_response(response.content)
            state["summary"] = summary

            return state

        except Exception as e:
            state["error"] = str(e)
            state["processing_status"] = "failed"
            return state

    async def query_agent(self, state: AnalysisState) -> AnalysisState:
        """질의응답 에이전트"""
        try:
            query = state["query"]
            document_id = state["document_id"]

            # RAG 검색
            relevant_chunks = await self._search_relevant_chunks(document_id, query)

            # 컨텍스트 기반 답변 생성
            prompt = ChatPromptTemplate.from_template(
                """
            당신은 공시 문서 분석 전문가입니다.
            
            질문: {query}
            
            관련 문서 내용:
            {context}
            
            위 내용을 바탕으로 정확하고 구체적인 답변을 제공해주세요.
            답변은 다음 형식으로 작성해주세요:
            
            ## 핵심 답변
            [주요 답변 내용]
            
            ## 세부 분석
            [상세한 분석 내용]
            
            ## 근거 자료
            [참조한 문서 부분]
            """
            )

            context = "\n".join(relevant_chunks)
            formatted_prompt = prompt.format(query=query, context=context)

            response = await self.llm.ainvoke(
                [{"role": "user", "content": formatted_prompt}]
            )

            state["answer"] = response.content
            state["sources"] = relevant_chunks
            state["confidence"] = self._calculate_confidence(query, relevant_chunks)

            return state

        except Exception as e:
            state["error"] = str(e)
            state["processing_status"] = "failed"
            return state

    def route_by_step(self, state: AnalysisState) -> str:
        """단계별 라우팅"""
        step = state.get("step")

        if state.get("error"):
            return "error_handler"

        if step == "index":
            return "vector_indexer"
        elif step == "query":
            return "query_agent"
        elif step == "summarize":
            return "summary_agent"
        else:
            return "complete_processing"

    async def error_handler(self, state: AnalysisState) -> AnalysisState:
        """에러 처리"""
        error = state.get("error", "알 수 없는 오류")
        retry_count = state.get("retry_count", 0)

        print(f"에러 발생: {error}, 재시도 횟수: {retry_count}")

        if retry_count < 3:
            # 재시도 로직
            state["retry_count"] = retry_count + 1
            state["error"] = None
            state["processing_status"] = "retrying"
        else:
            state["processing_status"] = "failed"

        return state

    async def complete_processing(self, state: AnalysisState) -> AnalysisState:
        """처리 완료"""
        state["processing_status"] = "completed"
        return state

    # 헬퍼 메서드들
    def _validate_file(self, file_path: str) -> bool:
        """파일 검증 헬퍼 메소드"""
        return Path(file_path).exists() and Path(file_path).suffix.lower() == ".pdf"

    async def _get_vectorstore_stats(self) -> dict:
        """벡터스토어 통계 조회"""
        try:
            # Chroma vectorstore에서 문서 개수 조회
            collection = self.vectorstore._collection
            return {
                "total_vectors": collection.count(),
                "collection_name": self.vectorstore._collection.name,
            }
        except Exception as e:
            return {"error": str(e)}

    async def _search_relevant_chunks(self, document_id: str, query: str) -> List[str]:
        # 실제 RAG 검색 로직
        return ["관련 청크1", "관련 청크2"]

    def _calculate_confidence(self, query: str, chunks: List[str]) -> float:
        # 신뢰도 계산 로직
        return 0.85

    def _get_auto_summary_prompt(self) -> str:
        return """
        당신은 금융 문서 요약 전문가입니다. 
        공시 문서를 읽고 투자자가 알아야 할 핵심 사항들을 요약해주세요.
        
        문서 내용: {content}
        
        다음 구조로 요약해주세요:
        ## 📊 재무 하이라이트
        ## 🏢 주요 사업 현황  
        ## ⚠️ 위험 요인
        ## 📈 향후 전망
        ## 💡 투자 포인트
        """

    def _parse_summary_response(self, response: str) -> Dict[str, Any]:
        # 응답 파싱 로직
        return {
            "financial_highlights": "재무 하이라이트...",
            "business_status": "사업 현황...",
            "risk_factors": "위험 요인...",
            "future_outlook": "향후 전망...",
            "investment_points": "투자 포인트...",
        }
