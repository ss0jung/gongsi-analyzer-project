import aiohttp
import asyncio
from typing import List, Dict
from datetime import datetime, timedelta
from urllib.parse import quote
import json
from config import settings
from models.schemas import NewsItem


class NaverNewsService:
    """네이버 뉴스 검색 서비스"""

    def __init__(self):
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET
        self.base_url = settings.NAVER_NEWS_URL
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def search_company_news(
        self, company_name: str, months: int = None, display: int = None
    ) -> List[NewsItem]:
        """기업 관련 뉴스 검색"""
        months = months or settings.NEWS_SEARCH_MONTHS
        display = display or settings.NEWS_DISPLAY_COUNT

        # 검색 쿼리 생성
        search_queries = self._generate_search_queries(company_name)

        all_news = []
        for query in search_queries:
            news_items = await self._search_news(query, display // len(search_queries))
            all_news.extend(news_items)

        # 중복 제거 및 관련도 순 정렬
        unique_news = self._remove_duplicates(all_news)
        relevant_news = self._filter_by_relevance(unique_news, company_name)

        return relevant_news[:display]

    def _generate_search_queries(self, company_name: str) -> List[str]:
        """검색 쿼리 생성"""
        # 기본 쿼리들
        queries = [
            company_name,
            f"{company_name} 실적",
            f"{company_name} 재무",
            f"{company_name} 사업",
        ]

        # 회사명에서 "(주)", "㈜" 등 제거한 버전도 추가
        clean_name = company_name.replace("(주)", "").replace("㈜", "").strip()
        if clean_name != company_name:
            queries.append(clean_name)

        return queries

    async def _search_news(self, query: str, display: int) -> List[NewsItem]:
        """네이버 뉴스 API 호출"""
        if not self.session:
            self.session = aiohttp.ClientSession()

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

        params = {
            "query": quote(query),
            "display": min(display, 100),  # 최대 100개
            "start": 1,
            "sort": "sim",  # 정확도순
        }

        try:
            async with self.session.get(
                self.base_url, headers=headers, params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_news_response(data, query)
                else:
                    print(f"Naver API Error: {response.status}")
                    return []
        except Exception as e:
            print(f"Error searching news: {e}")
            return []

    def _parse_news_response(self, data: dict, query: str) -> List[NewsItem]:
        """뉴스 응답 파싱"""
        news_items = []

        for item in data.get("items", []):
            # HTML 태그 제거
            title = self._clean_html(item.get("title", ""))
            description = self._clean_html(item.get("description", ""))

            # 관련도 점수 계산 (간단한 키워드 매칭 기반)
            relevance_score = self._calculate_relevance(title, description, query)

            news_item = NewsItem(
                title=title,
                description=description,
                pub_date=item.get("pubDate", ""),
                link=item.get("link", ""),
                relevance_score=relevance_score,
            )
            news_items.append(news_item)

        return news_items

    def _clean_html(self, text: str) -> str:
        """HTML 태그 제거"""
        import re

        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&quot;", '"').replace("&amp;", "&")
        text = text.replace("&lt;", "<").replace("&gt;", ">")
        return text.strip()

    def _calculate_relevance(self, title: str, description: str, query: str) -> float:
        """관련도 점수 계산"""
        text = f"{title} {description}".lower()
        query_lower = query.lower()

        # 기본 점수
        score = 0.0

        # 제목에 쿼리가 포함되면 높은 점수
        if query_lower in title.lower():
            score += 0.5

        # 설명에 쿼리가 포함되면 점수 추가
        if query_lower in description.lower():
            score += 0.3

        # 금융 관련 키워드 보너스
        financial_keywords = [
            "실적",
            "매출",
            "영업이익",
            "순이익",
            "재무",
            "투자",
            "사업",
            "전망",
        ]
        for keyword in financial_keywords:
            if keyword in text:
                score += 0.1

        return min(score, 1.0)  # 최대 1.0으로 제한

    def _remove_duplicates(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """중복 뉴스 제거"""
        seen_titles = set()
        unique_items = []

        for item in news_items:
            # 제목의 첫 20자로 중복 체크
            title_key = item.title[:20]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_items.append(item)

        return unique_items

    def _filter_by_relevance(
        self, news_items: List[NewsItem], company_name: str
    ) -> List[NewsItem]:
        """관련도 기준 필터링 및 정렬"""
        # 최소 관련도 임계값
        min_relevance = 0.1

        # 관련도 필터링
        relevant_items = [
            item for item in news_items if item.relevance_score >= min_relevance
        ]

        # 관련도 순으로 정렬
        relevant_items.sort(key=lambda x: x.relevance_score, reverse=True)

        return relevant_items

    async def get_recent_news(
        self, company_name: str, days: int = 30
    ) -> List[NewsItem]:
        """최근 뉴스만 가져오기"""
        all_news = await self.search_company_news(company_name)

        # 날짜 필터링
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_news = []

        for news in all_news:
            try:
                # pub_date 파싱 (예: "Mon, 11 Dec 2023 14:30:00 +0900")
                news_date = datetime.strptime(news.pub_date, "%a, %d %b %Y %H:%M:%S %z")
                if news_date.replace(tzinfo=None) >= cutoff_date:
                    recent_news.append(news)
            except:
                # 날짜 파싱 실패 시 최근 뉴스로 간주
                recent_news.append(news)

        return recent_news
