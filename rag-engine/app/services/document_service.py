from typing import Dict, Any, Optional
from app.core.pipeline.graph import create_analysis_pipeline
from app.services.vector_service import VectorService


class DocumentService:
    def __init__(self):
        self.vector_service = VectorService()
        self.analysis_pipeline = create_analysis_pipeline()

    async def index_document(
        self, file_path: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        문서를 인덱싱합니다.
        """
        try:
            # 문서 처리 파이프라인 실행
            result = await self.analysis_pipeline.invoke(
                {"file_path": file_path, "metadata": metadata, "step": "index"}
            )

            return {
                "success": True,
                "document_id": result.get("document_id"),
                "chunks_processed": result.get("chunks_count", 0),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def query_document(self, document_id: str, query: str) -> Dict[str, Any]:
        """
        문서에 대해 질의응답을 수행합니다.
        """
        try:
            result = await self.analysis_pipeline.invoke(
                {"document_id": document_id, "query": query, "step": "query"}
            )

            return result

        except Exception as e:
            raise Exception(f"질의 처리 실패: {str(e)}")

    async def get_document_status(self, document_id: str) -> Dict[str, Any]:
        """
        문서 처리 상태를 조회합니다.
        """
        # 벡터DB에서 문서 상태 확인
        exists = await self.vector_service.document_exists(document_id)

        return {
            "document_id": document_id,
            "status": "completed" if exists else "not_found",
            "indexed": exists,
        }
