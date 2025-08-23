def _should_include_news_analysis(self, question: str) -> bool:
    """질문 내용을 분석해서 뉴스 검색 필요 여부 자동 판단 (상세 버전)"""

    question_lower = question.lower()

    # 1. 시간 관련 키워드 (현재/최근 정보 필요)
    time_keywords = [
        "최근",
        "현재",
        "요즘",
        "지금",
        "올해",
        "작년",
        "내년",
        "앞으로",
        "향후",
        "미래",
        "전망",
        "계획",
        "예정",
    ]
    time_score = sum(0.3 for kw in time_keywords if kw in question_lower)

    # 2. 시장/경쟁 관련 키워드 (외부 정보 필요)
    market_keywords = [
        "경쟁",
        "시장",
        "업계",
        "동향",
        "트렌드",
        "비교",
        "경쟁사",
        "점유율",
        "순위",
        "위치",
        "경쟁력",
        "차별화",
    ]
    market_score = sum(0.25 for kw in market_keywords if kw in question_lower)

    # 3. 실시간/외부 평가 키워드
    external_keywords = [
        "주가",
        "시세",
        "평가",
        "전문가",
        "분석가",
        "의견",
        "추천",
        "목표가",
        "투자",
        "전망",
        "리포트",
    ]
    external_score = sum(0.4 for kw in external_keywords if kw in question_lower)

    # 4. 변화/성과 관련 키워드
    performance_keywords = [
        "증가",
        "감소",
        "성장",
        "하락",
        "변화",
        "개선",
        "악화",
        "상승",
        "하락",
        "회복",
        "둔화",
        "가속",
        "확대",
        "축소",
    ]
    performance_score = sum(0.2 for kw in performance_keywords if kw in question_lower)

    # 5. 사업/전략 키워드 (뉴스에서 추가 정보 가능)
    business_keywords = [
        "신사업",
        "신제품",
        "출시",
        "론칭",
        "확장",
        "진출",
        "인수",
        "합병",
        "제휴",
        "파트너십",
        "투자유치",
    ]
    business_score = sum(0.25 for kw in business_keywords if kw in question_lower)

    # 6. 부정적 키워드 (뉴스에서 맥락 파악 필요)
    negative_keywords = [
        "문제",
        "이슈",
        "위험",
        "우려",
        "논란",
        "갈등",
        "소송",
        "제재",
        "벌금",
        "조사",
        "비판",
    ]
    negative_score = sum(0.35 for kw in negative_keywords if kw in question_lower)

    # 총 점수 계산import asyncio


from openai import AsyncOpenAI
from typing import List, Tuple
import time
from models.state import AnalysisState
from models.schemas import DocumentChunk, NewsItem, AnalysisResult
from services.embedding_service import EmbeddingService
from services.news_service import NaverNewsService
from config import settings


class AnalysisAgent:
    """질의응답 및 분석 전문 에이전트"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.embedding_service = EmbeddingService()

    async def analyze_query(self, state: AnalysisState) -> AnalysisState:
        """질의 분석 및 답변 생성"""
        start_time = time.time()

        try:
            question = state.get("question", "")
            document_id = state.get("document_id", "")
            corp_name = state.get("corp_name", "")
            include_news = state.get("include_news", True)

            if not question or not document_id:
                state["error_message"] = "질문 또는 문서 ID가 없습니다."
                return state

            # 1. 관련 문서 청크 검색
            relevant_chunks = await self._search_relevant_chunks(question, document_id)

            # 2. 뉴스 검색 (옵션)
            news_items = []
            if include_news and corp_name:
                news_items = await self._search_relevant_news(corp_name, question)

            # 3. 컨텍스트 기반 답변 생성
            analysis_result = await self._generate_analysis(
                question, relevant_chunks, news_items, corp_name
            )

            # 4. 신뢰도 점수 계산
            confidence_score = self._calculate_confidence(
                relevant_chunks, analysis_result
            )

            # 상태 업데이트
            state["relevant_chunks"] = relevant_chunks
            state["search_results"] = news_items
            state["analysis_result"] = analysis_result
            state["confidence_score"] = confidence_score
            state["processing_times"]["analysis"] = time.time() - start_time

        except Exception as e:
            state["error_message"] = f"분석 중 오류: {str(e)}"

        return state

    async def _search_relevant_chunks(
        self, question: str, document_id: str
    ) -> List[DocumentChunk]:
        """관련 문서 청크 검색"""
        try:
            # 의미적 유사도 + 키워드 리랭킹
            chunk_results = await self.embedding_service.semantic_search_with_rerank(
                query=question, document_id=document_id, top_k=10, rerank_top_k=5
            )

            # DocumentChunk만 추출
            chunks = [chunk for chunk, score in chunk_results if score > 0.3]

            return chunks[:5]  # 최대 5개

        except Exception as e:
            print(f"Error searching relevant chunks: {e}")
            return []

    async def _search_relevant_news(
        self, corp_name: str, question: str
    ) -> List[NewsItem]:
        """관련 뉴스 검색"""
        try:
            async with NaverNewsService() as news_service:
                # 기본 뉴스 검색
                news_items = await news_service.search_company_news(
                    company_name=corp_name, display=10
                )

                # 질문과 관련성 높은 뉴스 필터링
                relevant_news = self._filter_news_by_question(news_items, question)

                return relevant_news[:3]  # 최대 3개

        except Exception as e:
            print(f"Error searching relevant news: {e}")
            return []

    def _filter_news_by_question(
        self, news_items: List[NewsItem], question: str
    ) -> List[NewsItem]:
        """질문과 관련성 높은 뉴스 필터링"""
        question_keywords = set(question.lower().split())

        # 재무 관련 질문 키워드
        financial_keywords = {
            "실적",
            "매출",
            "영업이익",
            "순이익",
            "재무",
            "수익",
            "손실",
            "성장",
            "감소",
            "증가",
            "전망",
            "계획",
            "투자",
        }

        scored_news = []
        for news in news_items:
            score = news.relevance_score

            # 질문 키워드가 뉴스에 포함된 경우 점수 증가
            news_text = f"{news.title} {news.description}".lower()
            for keyword in question_keywords:
                if keyword in news_text:
                    score += 0.2

            # 재무 관련 질문인 경우 재무 뉴스 우선
            if any(kw in question.lower() for kw in financial_keywords):
                if any(kw in news_text for kw in financial_keywords):
                    score += 0.3

            scored_news.append((news, score))

        # 점수 순으로 정렬
        scored_news.sort(key=lambda x: x[1], reverse=True)

        return [news for news, score in scored_news if score > 0.4]

    async def _generate_analysis(
        self,
        question: str,
        chunks: List[DocumentChunk],
        news_items: List[NewsItem],
        corp_name: str,
    ) -> str:
        """컨텍스트 기반 분석 답변 생성"""

        # 컨텍스트 구성
        context_parts = []

        # 문서 컨텍스트
        if chunks:
            doc_context = "## 공시 문서 관련 내용:\n"
            for i, chunk in enumerate(chunks, 1):
                doc_context += f"{i}. [{chunk.section}] {chunk.content[:300]}...\n\n"
            context_parts.append(doc_context)

        # 뉴스 컨텍스트
        if news_items:
            news_context = "## 최근 뉴스 정보:\n"
            for i, news in enumerate(news_items, 1):
                news_context += f"{i}. {news.title}\n   {news.description}\n\n"
            context_parts.append(news_context)

        context = "\n".join(context_parts)

        # 프롬프트 생성
        prompt = f"""
당신은 {corp_name}의 공시 문서와 최신 뉴스를 분석하는 금융 전문가입니다.
다음 질문에 대해 제공된 정보를 바탕으로 정확하고 통찰력 있는 답변을 해주세요.

질문: {question}

참고 정보:
{context}

답변 가이드라인:
1. 공시 문서의 정보를 우선적으로 활용하세요
2. 최신 뉴스는 보조적인 정보로 활용하세요
3. 구체적인 숫자나 데이터가 있다면 인용하세요
4. 불확실한 정보는 명시적으로 표시하세요
5. 투자자 관점에서 실용적인 인사이트를 제공하세요
6. 답변은 3-4개 문단으로 구성하세요

답변 구조:
- 첫 번째 문단: 질문에 대한 직접적인 답변
- 두 번째 문단: 공시 문서 기반 상세 분석
- 세 번째 문단: 시장 상황 및 뉴스 반영 (해당시)
- 네 번째 문단: 투자자를 위한 시사점
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=1500,
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"분석 생성 중 오류가 발생했습니다: {str(e)}"

    def _calculate_confidence(
        self, chunks: List[DocumentChunk], analysis: str
    ) -> float:
        """답변 신뢰도 점수 계산"""
        confidence = 0.5  # 기본 점수

        # 관련 청크 수에 따른 점수
        if len(chunks) >= 3:
            confidence += 0.2
        elif len(chunks) >= 1:
            confidence += 0.1

        # 분석 답변 길이에 따른 점수
        if len(analysis) > 500:
            confidence += 0.1

        # 구체적 숫자나 데이터 포함 여부
        import re

        if re.search(r"\d+%|\d+억|\d+만|\d+년|\d+월", analysis):
            confidence += 0.1

        # 불확실성 표현이 있는 경우 점수 감점
        uncertainty_phrases = [
            "확실하지 않",
            "명확하지 않",
            "정보가 부족",
            "판단하기 어려",
        ]
        if any(phrase in analysis for phrase in uncertainty_phrases):
            confidence -= 0.1

        return min(max(confidence, 0.0), 1.0)  # 0.0 ~ 1.0 범위로 제한

    async def generate_follow_up_questions(self, state: AnalysisState) -> List[str]:
        """후속 질문 제안"""
        try:
            analysis_result = state.get("analysis_result", "")
            corp_name = state.get("corp_name", "")

            if not analysis_result:
                return []

            prompt = f"""
다음은 {corp_name}에 대한 분석 결과입니다:

{analysis_result}

이 분석을 바탕으로 투자자가 추가로 궁금해할 만한 후속 질문 3개를 제안해주세요.
각 질문은 구체적이고 실용적이어야 합니다.

형식: 
1. 질문1
2. 질문2  
3. 질문3
"""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=300,
            )

            # 응답 파싱
            content = response.choices[0].message.content
            questions = []
            for line in content.split("\n"):
                if line.strip() and (line.strip().startswith(("1.", "2.", "3."))):
                    question = line.strip()[2:].strip()
                    if question:
                        questions.append(question)

            return questions[:3]

        except Exception as e:
            print(f"Error generating follow-up questions: {e}")
            return []
