from typing import Dict, Any, Optional
from app.core.pipeline.graph import create_analysis_pipeline


class SummaryService:
    def __init__(self):
        self.analysis_pipeline = create_analysis_pipeline()

    async def generate_summary(self, document_id: str) -> Dict[str, Any]:
        """
        문서의 요약본을 생성합니다.
        개선사항: Summary Agent를 활용한 구조화된 요약 제공
        """
        try:
            result = await self.analysis_pipeline.invoke(
                {"document_id": document_id, "step": "summarize"}
            )

            return {
                "document_id": document_id,
                "summary": {
                    "financial_highlights": result.get("financial_highlights"),
                    "business_status": result.get("business_status"),
                    "risk_factors": result.get("risk_factors"),
                    "future_outlook": result.get("future_outlook"),
                    "investment_points": result.get("investment_points"),
                },
                "generated_at": result.get("timestamp"),
            }

        except Exception as e:
            raise Exception(f"요약 생성 실패: {str(e)}")

    async def get_summary(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        저장된 요약본을 조회합니다.
        """
        try:
            # 캐시된 요약본이 있는지 확인
            cached_summary = await self._get_cached_summary(document_id)

            if cached_summary:
                return cached_summary

            # 없다면 새로 생성
            return await self.generate_summary(document_id)

        except Exception as e:
            raise Exception(f"요약 조회 실패: {str(e)}")

    async def _get_cached_summary(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        캐시된 요약본을 조회합니다. (실제 구현에서는 Redis 등 사용)
        """
        # TODO: 실제 캐시 구현
        return None
