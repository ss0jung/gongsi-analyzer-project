import asyncio
from openai import AsyncOpenAI
from langchain.prompts import ChatPromptTemplate
from typing import Dict, Any
import time
from models.state import AnalysisState
from models.schemas import DocumentSummary
from config import settings


class SummaryAgent:
    """문서 요약 전문 에이전트"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        self.max_length = settings.SUMMARY_MAX_LENGTH
        self.timeout = settings.SUMMARY_TIMEOUT

    async def generate_summary(self, state: AnalysisState) -> AnalysisState:
        """문서 요약 생성"""
        start_time = time.time()

        try:
            document_content = state.get("document_content", "")
            corp_name = state.get("corp_name", "")

            if not document_content:
                state["error_message"] = "문서 내용이 없습니다."
                return state

            # 문서 길이에 따른 요약 전략 결정
            summary_strategy = self._determine_strategy(document_content)

            if summary_strategy == "direct":
                summary = await self._direct_summary(document_content, corp_name)
            else:
                summary = await self._chunked_summary(document_content, corp_name)

            # 요약 결과 구조화
            structured_summary = await self._structure_summary(summary, corp_name)

            state["summary"] = structured_summary
            state["summary_generated"] = True
            state["processing_times"]["summary"] = time.time() - start_time

        except asyncio.TimeoutError:
            state["error_message"] = f"요약 생성 시간 초과 ({self.timeout}초)"
        except Exception as e:
            state["error_message"] = f"요약 생성 중 오류: {str(e)}"

        return state

    def _determine_strategy(self, content: str) -> str:
        """요약 전략 결정"""
        # 대략적인 토큰 수 추정 (한글 1글자 ≈ 1.5토큰)
        estimated_tokens = len(content) * 1.5

        # GPT-4의 컨텍스트 윈도우 고려
        if estimated_tokens < 8000:
            return "direct"
        else:
            return "chunked"

    async def _direct_summary(self, content: str, corp_name: str) -> str:
        """직접 요약 (짧은 문서용)"""

        prompt = f"""
당신은 금융 문서 분석 전문가입니다. 
다음 {corp_name}의 공시 문서를 읽고, 일반 투자자도 이해하기 쉽게 요약해주세요.

문서 내용:
{content[:6000]}  # 토큰 제한 고려

다음 4개 섹션으로 요약해주세요:

## 🏢 기업 개요
- 주요 사업 분야와 현재 상황을 간단히 설명

## 💰 재무 하이라이트  
- 매출, 영업이익, 순이익 등 핵심 재무 지표
- 전년 대비 주요 변화사항

## 📈 주요 변화사항
- 신규 사업, 투자, M&A 등 중요한 변화
- 시장 환경 변화가 회사에 미치는 영향

## ⚠️ 주목할 점
- 투자자가 알아야 할 위험 요인이나 기회 요인
- 향후 전망에 영향을 줄 수 있는 요소들

각 섹션은 2-3문장으로 간결하게 작성하고, 전체 길이는 {self.max_length}자 이내로 해주세요.
금융 전문 용어는 괄호 안에 쉬운 설명을 추가해주세요.
"""

        try:
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1000,
                ),
                timeout=self.timeout,
            )

            return response.choices[0].message.content

        except Exception as e:
            raise Exception(f"OpenAI API 호출 실패: {str(e)}")

    async def _chunked_summary(self, content: str, corp_name: str) -> str:
        """청크별 요약 후 통합 (긴 문서용)"""

        # 문서를 섹션별로 분할
        sections = self._split_into_sections(content)

        section_summaries = {}

        # 각 섹션별 요약
        for section_name, section_content in sections.items():
            if section_content.strip():
                summary = await self._summarize_section(
                    section_content, section_name, corp_name
                )
                section_summaries[section_name] = summary

        # 최종 통합 요약
        final_summary = await self._integrate_summaries(section_summaries, corp_name)

        return final_summary

    def _split_into_sections(self, content: str) -> Dict[str, str]:
        """문서를 섹션별로 분할"""
        import re

        sections = {
            "business": "",
            "financial": "",
            "management": "",
            "risk": "",
            "others": "",
        }

        # 섹션 패턴 정의
        patterns = {
            "business": r"(사업의\s*내용|주요\s*사업|사업현황).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "financial": r"(재무에\s*관한\s*사항|재무상태|재무제표).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "management": r"(경영진\s*분석|재무성과\s*분석|경영성과).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "risk": r"(위험요인|리스크\s*요인|사업위험).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
        }

        remaining_content = content

        for section_name, pattern in patterns.items():
            matches = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                section_content = matches.group(0)
                sections[section_name] = section_content[:2000]  # 길이 제한
                remaining_content = remaining_content.replace(section_content, "")

        # 나머지 내용
        if remaining_content.strip():
            sections["others"] = remaining_content[:2000]

        return sections

    async def _summarize_section(
        self, content: str, section_name: str, corp_name: str
    ) -> str:
        """섹션별 요약"""

        section_prompts = {
            "business": "주요 사업 분야와 현재 상황을 2-3문장으로 요약해주세요.",
            "financial": "핵심 재무 지표와 전년 대비 변화를 2-3문장으로 요약해주세요.",
            "management": "경영 성과와 분석 내용을 2-3문장으로 요약해주세요.",
            "risk": "주요 위험 요인을 2-3문장으로 요약해주세요.",
            "others": "기타 중요한 내용을 2-3문장으로 요약해주세요.",
        }

        prompt = f"""
다음은 {corp_name}의 공시 문서 중 일부입니다.
{section_prompts.get(section_name, "내용을 2-3문장으로 요약해주세요.")}

내용:
{content}

일반 투자자도 이해하기 쉽게 설명해주세요.
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"{section_name} 섹션 요약 실패: {str(e)}"

    async def _integrate_summaries(
        self, section_summaries: Dict[str, str], corp_name: str
    ) -> str:
        """섹션별 요약을 최종 통합"""

        summaries_text = "\n".join(
            [f"{k}: {v}" for k, v in section_summaries.items() if v]
        )

        prompt = f"""
다음은 {corp_name}의 공시 문서를 섹션별로 요약한 내용입니다.
이를 바탕으로 투자자를 위한 최종 요약 보고서를 작성해주세요.

섹션별 요약:
{summaries_text}

다음 형식으로 작성해주세요:

## 🏢 기업 개요
## 💰 재무 하이라이트  
## 📈 주요 변화사항
## ⚠️ 주목할 점

각 섹션은 2-3문장으로 간결하게 작성하고, 전체 길이는 {self.max_length}자 이내로 해주세요.
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )

            return response.choices[0].message.content

        except Exception as e:
            # 통합 실패 시 섹션별 요약을 단순 결합
            return self._fallback_integration(section_summaries)

    def _fallback_integration(self, section_summaries: Dict[str, str]) -> str:
        """통합 실패 시 대체 방법"""
        result = ""

        if section_summaries.get("business"):
            result += f"## 🏢 기업 개요\n{section_summaries['business']}\n\n"

        if section_summaries.get("financial"):
            result += f"## 💰 재무 하이라이트\n{section_summaries['financial']}\n\n"

        if section_summaries.get("management"):
            result += f"## 📈 주요 변화사항\n{section_summaries['management']}\n\n"

        if section_summaries.get("risk"):
            result += f"## ⚠️ 주목할 점\n{section_summaries['risk']}\n\n"

        return result.strip()

    async def _structure_summary(
        self, summary_text: str, corp_name: str
    ) -> DocumentSummary:
        """요약 결과를 구조화"""

        # 간단한 파싱 (섹션별로 분할)
        sections = {
            "company_overview": "",
            "financial_highlights": "",
            "key_changes": "",
            "notable_points": "",
        }

        current_section = None
        lines = summary_text.split("\n")

        for line in lines:
            line = line.strip()
            if "🏢" in line or "기업 개요" in line:
                current_section = "company_overview"
            elif "💰" in line or "재무 하이라이트" in line:
                current_section = "financial_highlights"
            elif "📈" in line or "주요 변화사항" in line:
                current_section = "key_changes"
            elif "⚠️" in line or "주목할 점" in line:
                current_section = "notable_points"
            elif line.startswith("##"):
                current_section = None
            elif line and current_section:
                sections[current_section] += line + " "

        # 빈 섹션 처리
        for key, value in sections.items():
            if not value.strip():
                sections[key] = "정보가 없습니다."

        return DocumentSummary(
            company_overview=sections["company_overview"].strip(),
            financial_highlights=sections["financial_highlights"].strip(),
            key_changes=sections["key_changes"].strip(),
            notable_points=sections["notable_points"].strip(),
        )
