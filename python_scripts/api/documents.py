from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from models.schemas import (
    DocumentIndexRequest,
    IndexingResult,
    DocumentSummary,
    ProcessingStatus,
)
from workflow import DocumentAnalysisWorkflow
from services.embedding_service import EmbeddingService
import asyncio
from typing import Dict
import uuid
import os

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# 인덱싱 작업 상태 추적
indexing_tasks: Dict[str, IndexingResult] = {}

# 워크플로우 인스턴스
workflow = DocumentAnalysisWorkflow()


@router.post("/index")
async def index_document(
    request: DocumentIndexRequest, background_tasks: BackgroundTasks
) -> JSONResponse:
    """파일 기반 문서 인덱싱 및 요약 생성"""

    # 파일 경로 검증
    if not os.path.exists(request.file_path):
        raise HTTPException(
            status_code=400, detail=f"파일을 찾을 수 없습니다: {request.file_path}"
        )

    task_id = str(uuid.uuid4())

    # 초기 상태 설정
    initial_result = IndexingResult(
        document_id=request.document_id,
        status=ProcessingStatus.PENDING,
        summary=None,
        total_chunks=None,
        processing_time=None,
        error_message=None,
    )

    indexing_tasks[task_id] = initial_result

    # 백그라운드에서 인덱싱 실행
    background_tasks.add_task(
        run_indexing_task,
        task_id,
        request.document_id,
        request.corp_name,
        request.file_path,
    )

    return JSONResponse(
        status_code=202,
        content={
            "task_id": task_id,
            "document_id": request.document_id,
            "message": "인덱싱 작업이 시작되었습니다.",
            "status": "pending",
        },
    )


async def run_indexing_task(
    task_id: str, document_id: str, corp_name: str, file_path: str
):
    """백그라운드 인덱싱 작업"""

    try:
        # 상태 업데이트: 처리 중
        indexing_tasks[task_id].status = ProcessingStatus.PROCESSING

        # 워크플로우 실행
        result = await workflow.run_indexing_workflow(document_id, corp_name, file_path)

        if result.get("error_message"):
            # 실패
            indexing_tasks[task_id].status = ProcessingStatus.FAILED
            indexing_tasks[task_id].error_message = result["error_message"]
        else:
            # 성공
            indexing_tasks[task_id].status = ProcessingStatus.COMPLETED
            indexing_tasks[task_id].summary = result.get("summary")
            indexing_tasks[task_id].total_chunks = len(result.get("chunks", []))
            indexing_tasks[task_id].processing_time = sum(
                result.get("processing_times", {}).values()
            )

    except Exception as e:
        indexing_tasks[task_id].status = ProcessingStatus.FAILED
        indexing_tasks[task_id].error_message = f"인덱싱 처리 중 오류: {str(e)}"


@router.get("/index/{task_id}/status")
async def get_indexing_status(task_id: str) -> IndexingResult:
    """인덱싱 작업 상태 조회"""

    if task_id not in indexing_tasks:
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다.")

    return indexing_tasks[task_id]


@router.get("/{document_id}/summary")
async def get_document_summary(document_id: str) -> DocumentSummary:
    """문서 요약 조회"""

    try:
        # 완료된 인덱싱 작업에서 요약 찾기
        for task_result in indexing_tasks.values():
            if (
                task_result.document_id == document_id
                and task_result.status == ProcessingStatus.COMPLETED
                and task_result.summary
            ):
                return task_result.summary

        raise HTTPException(
            status_code=404,
            detail="문서 요약을 찾을 수 없습니다. 먼저 문서를 인덱싱해주세요.",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"요약 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """문서 삭제 (벡터 DB에서 제거)"""

    try:
        embedding_service = EmbeddingService()
        embedding_service.delete_document(document_id)

        # 인덱싱 작업 기록에서도 제거
        tasks_to_remove = []
        for task_id, result in indexing_tasks.items():
            if result.document_id == document_id:
                tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del indexing_tasks[task_id]

        return {"message": f"문서 {document_id}가 삭제되었습니다."}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"문서 삭제 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{document_id}/chunks")
async def get_document_chunks(document_id: str):
    """문서의 모든 청크 조회 (디버깅용)"""

    try:
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(document_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section,
                    "chunk_type": chunk.chunk_type,
                    "content_preview": (
                        chunk.content[:200] + "..."
                        if len(chunk.content) > 200
                        else chunk.content
                    ),
                    "metadata": chunk.metadata,
                }
                for chunk in chunks
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"청크 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/stats")
async def get_collection_stats():
    """벡터 DB 통계 정보"""

    try:
        embedding_service = EmbeddingService()
        stats = embedding_service.get_collection_stats()

        # 진행 중인 인덱싱 작업 수 추가
        processing_count = sum(
            1
            for task in indexing_tasks.values()
            if task.status == ProcessingStatus.PROCESSING
        )

        completed_count = sum(
            1
            for task in indexing_tasks.values()
            if task.status == ProcessingStatus.COMPLETED
        )

        stats["processing_tasks"] = processing_count
        stats["completed_tasks"] = completed_count
        stats["total_tasks"] = len(indexing_tasks)

        return stats

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/index/{task_id}/status")
async def get_indexing_status(task_id: str) -> IndexingResult:
    """인덱싱 작업 상태 조회"""

    if task_id not in indexing_tasks:
        raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다.")

    return indexing_tasks[task_id]


@router.get("/{document_id}/summary")
async def get_document_summary(document_id: str) -> DocumentSummary:
    """문서 요약 조회"""

    try:
        # 완료된 인덱싱 작업에서 요약 찾기
        for task_result in indexing_tasks.values():
            if (
                task_result.document_id == document_id
                and task_result.status == ProcessingStatus.COMPLETED
                and task_result.summary
            ):
                return task_result.summary

        # 인덱싱 작업에서 찾을 수 없다면 워크플로우에서 직접 조회
        # (이미 인덱싱된 문서의 경우)
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(document_id)

        if not chunks:
            raise HTTPException(
                status_code=404,
                detail="문서를 찾을 수 없거나 아직 인덱싱되지 않았습니다.",
            )

        # 요약이 없다면 새로 생성 (이 경우는 드물지만)
        raise HTTPException(
            status_code=404, detail="문서 요약을 찾을 수 없습니다. 다시 인덱싱해주세요."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"요약 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """문서 삭제 (벡터 DB에서 제거)"""

    try:
        embedding_service = EmbeddingService()
        embedding_service.delete_document(document_id)

        # 인덱싱 작업 기록에서도 제거
        tasks_to_remove = []
        for task_id, result in indexing_tasks.items():
            if result.document_id == document_id:
                tasks_to_remove.append(task_id)

        for task_id in tasks_to_remove:
            del indexing_tasks[task_id]

        return {"message": f"문서 {document_id}가 삭제되었습니다."}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"문서 삭제 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/{document_id}/chunks")
async def get_document_chunks(document_id: str):
    """문서의 모든 청크 조회 (디버깅용)"""

    try:
        embedding_service = EmbeddingService()
        chunks = await embedding_service.get_document_chunks(document_id)

        if not chunks:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section,
                    "chunk_type": chunk.chunk_type,
                    "content_preview": (
                        chunk.content[:200] + "..."
                        if len(chunk.content) > 200
                        else chunk.content
                    ),
                    "metadata": chunk.metadata,
                }
                for chunk in chunks
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"청크 조회 중 오류가 발생했습니다: {str(e)}"
        )


@router.get("/stats")
async def get_collection_stats():
    """벡터 DB 통계 정보"""

    try:
        embedding_service = EmbeddingService()
        stats = embedding_service.get_collection_stats()

        # 진행 중인 인덱싱 작업 수 추가
        processing_count = sum(
            1
            for task in indexing_tasks.values()
            if task.status == ProcessingStatus.PROCESSING
        )

        stats["processing_tasks"] = processing_count
        stats["total_tasks"] = len(indexing_tasks)

        return stats

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"통계 조회 중 오류가 발생했습니다: {str(e)}"
        )
