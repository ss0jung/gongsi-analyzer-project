from fastapi import APIRouter, HTTPException
from datetime import datetime
from models.schemas import QueryRequest, QueryResponse, AnalysisResult
from workflow import DocumentAnalysisWorkflow
from services.embedding_service import EmbeddingService
from agents.analysis_agent import AnalysisAgent

router = APIRouter(prefix="/api/v1/query", tags=["query"])

# 워크플로우 및 서비스 인스턴스
workflow = DocumentAnalysisWorkflow()
analysis_agent = AnalysisAgent()


@router.post("/")
async def query_document(request: QueryRequest) -> QueryResponse:
    """문서에 대한 질의응답"""

    try:
        # 문서가 인덱싱되어 있는지 확인
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(request.document_id)

        if not chunks:
            raise HTTPException(
                status_code=404,
                detail="문서를 찾을 수 없습니다. 먼저 문서를 인덱싱해주세요.",
            )

        # 기업명 추출 (첫 번째 청크의 메타데이터에서)
        corp_name = ""
        if chunks and chunks[0].metadata:
            corp_name = chunks[0].metadata.get("corp_name", "")

        # 질의응답 워크플로우 실행 (독립적)
        result = await workflow.run_query_workflow(
            document_id=request.document_id,
            corp_name=corp_name,
            question=request.question,
            include_news=request.include_news,
        )

        if result.get("error_message"):
            raise HTTPException(status_code=500, detail=result["error_message"])

        # 뉴스 포함 여부 확인
        news_included = len(result.get("search_results", [])) > 0

        # 응답 구성
        analysis_result = AnalysisResult(
            answer=result.get("analysis_result", "답변을 생성할 수 없습니다."),
            confidence_score=result.get("confidence_score", 0.0),
            relevant_chunks=[
                chunk.content for chunk in result.get("relevant_chunks", [])
            ],
            related_news=result.get("search_results", []),
            analysis_time=result.get("processing_times", {}).get("analysis", 0.0),
            news_included=news_included,
        )

        return QueryResponse(
            document_id=request.document_id,
            question=request.question,
            result=analysis_result,
            timestamp=datetime.now(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/{document_id}/follow-up")
async def get_follow_up_questions(document_id: str, previous_question: str):
    """후속 질문 제안"""

    try:
        # 문서 확인
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(document_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

        # 기업명 추출
        corp_name = ""
        if chunks and chunks[0].metadata:
            corp_name = chunks[0].metadata.get("corp_name", "")

        # 간단한 상태 구성 (이전 질문 기반)
        state = {
            "analysis_result": f"이전 질문: {previous_question}",
            "corp_name": corp_name,
        }

        # 후속 질문 생성
        follow_up_questions = await analysis_agent.generate_follow_up_questions(state)

        return {
            "document_id": document_id,
            "previous_question": previous_question,
            "follow_up_questions": follow_up_questions,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"후속 질문 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{document_id}/search")
async def search_document_content(document_id: str, query: str, top_k: int = 5):
    """문서 내 내용 검색"""

    try:
        embedding_service = EmbeddingService()

        # 유사한 청크 검색
        similar_chunks = await embedding_service.search_similar_chunks(
            query=query, document_id=document_id, top_k=top_k, min_similarity=0.3
        )

        if not similar_chunks:
            return {
                "document_id": document_id,
                "query": query,
                "results": [],
                "message": "관련된 내용을 찾을 수 없습니다.",
            }

        # 결과 포맷팅
        results = []
        for chunk, similarity in similar_chunks:
            results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section,
                    "chunk_type": chunk.chunk_type,
                    "content": chunk.content,
                    "similarity_score": similarity,
                    "metadata": chunk.metadata,
                }
            )

        return {
            "document_id": document_id,
            "query": query,
            "results": results,
            "total_found": len(results),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"문서 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/batch")
async def batch_query(
    document_id: str, questions: list[str], include_news: bool = None
):
    """여러 질문을 배치로 처리"""

    if len(questions) > 10:
        raise HTTPException(
            status_code=400, detail="한 번에 최대 10개의 질문까지 처리할 수 있습니다."
        )

    try:
        # 문서 확인
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(document_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

        results = []

        # 각 질문을 순차적으로 처리
        for question in questions:
            try:
                request = QueryRequest(
                    document_id=document_id,
                    question=question,
                    include_news=include_news,
                )

                response = await query_document(request)
                results.append(
                    {"question": question, "success": True, "result": response.result}
                )

            except Exception as e:
                results.append(
                    {"question": question, "success": False, "error": str(e)}
                )

        return {
            "document_id": document_id,
            "total_questions": len(questions),
            "successful_answers": sum(1 for r in results if r["success"]),
            "results": results,
            "timestamp": datetime.now(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"배치 질의 처리 중 오류가 발생했습니다: {str(e)}"
        )


from fastapi import APIRouter, HTTPException
from datetime import datetime
from models.schemas import QueryRequest, QueryResponse, AnalysisResult
from workflow import DocumentAnalysisWorkflow
from services.embedding_service import EmbeddingService
from agents.analysis_agent import AnalysisAgent

router = APIRouter(prefix="/api/v1/query", tags=["query"])

# 워크플로우 및 서비스 인스턴스
workflow = DocumentAnalysisWorkflow()
analysis_agent = AnalysisAgent()


@router.post("/")
async def query_document(request: QueryRequest) -> QueryResponse:
    """문서에 대한 질의응답"""

    try:
        # 문서가 인덱싱되어 있는지 확인
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(request.document_id)

        if not chunks:
            raise HTTPException(
                status_code=404,
                detail="문서를 찾을 수 없습니다. 먼저 문서를 인덱싱해주세요.",
            )

        # 기업명 추출 (첫 번째 청크의 메타데이터에서)
        corp_name = ""
        if chunks and chunks[0].metadata:
            corp_name = chunks[0].metadata.get("corp_name", "")

        # 질의응답 워크플로우 실행
        result = await workflow.run_query_workflow(
            rcept_no=request.document_id,
            corp_name=corp_name,
            question=request.question,
            include_news=request.include_news,
        )

        if result.get("error_message"):
            raise HTTPException(status_code=500, detail=result["error_message"])

        # 응답 구성
        analysis_result = AnalysisResult(
            answer=result.get("analysis_result", "답변을 생성할 수 없습니다."),
            confidence_score=result.get("confidence_score", 0.0),
            relevant_chunks=[
                chunk.content for chunk in result.get("relevant_chunks", [])
            ],
            related_news=result.get("search_results", []),
            analysis_time=result.get("processing_times", {}).get("analysis", 0.0),
        )

        return QueryResponse(
            document_id=request.document_id,
            question=request.question,
            result=analysis_result,
            timestamp=datetime.now(),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"질의응답 처리 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/{document_id}/follow-up")
async def get_follow_up_questions(document_id: str, previous_question: str):
    """후속 질문 제안"""

    try:
        # 문서 확인
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(document_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

        # 기업명 추출
        corp_name = ""
        if chunks and chunks[0].metadata:
            corp_name = chunks[0].metadata.get("corp_name", "")

        # 간단한 상태 구성 (이전 질문 기반)
        state = {
            "analysis_result": f"이전 질문: {previous_question}",
            "corp_name": corp_name,
        }

        # 후속 질문 생성
        follow_up_questions = await analysis_agent.generate_follow_up_questions(state)

        return {
            "document_id": document_id,
            "previous_question": previous_question,
            "follow_up_questions": follow_up_questions,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"후속 질문 생성 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{document_id}/search")
async def search_document_content(document_id: str, query: str, top_k: int = 5):
    """문서 내 내용 검색"""

    try:
        embedding_service = EmbeddingService()

        # 유사한 청크 검색
        similar_chunks = await embedding_service.search_similar_chunks(
            query=query, document_id=document_id, top_k=top_k, min_similarity=0.3
        )

        if not similar_chunks:
            return {
                "document_id": document_id,
                "query": query,
                "results": [],
                "message": "관련된 내용을 찾을 수 없습니다.",
            }

        # 결과 포맷팅
        results = []
        for chunk, similarity in similar_chunks:
            results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section,
                    "chunk_type": chunk.chunk_type,
                    "content": chunk.content,
                    "similarity_score": similarity,
                    "metadata": chunk.metadata,
                }
            )

        return {
            "document_id": document_id,
            "query": query,
            "results": results,
            "total_found": len(results),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"문서 검색 중 오류가 발생했습니다: {str(e)}"
        )


@router.post("/batch")
async def batch_query(
    document_id: str, questions: list[str], include_news: bool = True
):
    """여러 질문을 배치로 처리"""

    if len(questions) > 10:
        raise HTTPException(
            status_code=400, detail="한 번에 최대 10개의 질문까지 처리할 수 있습니다."
        )

    try:
        # 문서 확인
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(document_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

        results = []

        # 각 질문을 순차적으로 처리
        for question in questions:
            try:
                request = QueryRequest(
                    document_id=document_id,
                    question=question,
                    include_news=include_news,
                )

                response = await query_document(request)
                results.append(
                    {"question": question, "success": True, "result": response.result}
                )

            except Exception as e:
                results.append(
                    {"question": question, "success": False, "error": str(e)}
                )

        return {
            "document_id": document_id,
            "total_questions": len(questions),
            "successful_answers": sum(1 for r in results if r["success"]),
            "results": results,
            "timestamp": datetime.now(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"배치 질의 처리 중 오류가 발생했습니다: {str(e)}"
        )
