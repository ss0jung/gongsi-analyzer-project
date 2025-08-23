import re
import tiktoken
from typing import List, Dict, Tuple
from models.schemas import DocumentChunk
from config import settings
import uuid


class HybridDocumentChunker:
    """하이브리드 문서 청킹 클래스"""

    def __init__(self):
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        self.chunk_size = settings.CHUNK_SIZE
        self.overlap = settings.CHUNK_OVERLAP
        self.max_tokens = settings.MAX_TOKENS_PER_CHUNK

    def chunk_document(
        self, document_content: str, document_id: str
    ) -> List[DocumentChunk]:
        """메인 청킹 함수"""
        chunks = []

        # 1. 구조화된 섹션으로 분할
        sections = self._extract_sections(document_content)

        for section_name, content in sections.items():
            section_chunks = self._process_section(content, section_name, document_id)
            chunks.extend(section_chunks)

        return chunks

    def _extract_sections(self, content: str) -> Dict[str, str]:
        """문서를 주요 섹션으로 분할"""
        sections = {}

        # 공시문서 주요 섹션 패턴
        section_patterns = {
            "company_overview": r"(회사의\s*개요|기업개요|회사개요).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "business_content": r"(사업의\s*내용|주요\s*사업|사업현황).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "financial_status": r"(재무에\s*관한\s*사항|재무상태|재무제표|재무현황).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "management_analysis": r"(경영진\s*분석|재무성과\s*분석|경영성과).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "risk_factors": r"(위험요인|리스크\s*요인|사업위험).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
            "future_plans": r"(향후\s*계획|사업전망|미래전략).*?(?=\n\n|\n[IVX]+\.|\n\d+\.)",
        }

        remaining_content = content

        for section_name, pattern in section_patterns.items():
            matches = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if matches:
                section_content = matches.group(0)
                sections[section_name] = section_content
                remaining_content = remaining_content.replace(section_content, "")

        # 나머지 내용
        if remaining_content.strip():
            sections["others"] = remaining_content

        return sections

    def _process_section(
        self, content: str, section_name: str, document_id: str
    ) -> List[DocumentChunk]:
        """섹션별 처리"""
        chunks = []

        # 테이블 검출 및 처리
        if self._contains_table(content):
            table_chunks = self._chunk_tables(content, section_name, document_id)
            chunks.extend(table_chunks)
            # 테이블 제거 후 나머지 텍스트 처리
            content = self._remove_tables(content)

        # 남은 텍스트를 의미 단위로 청킹
        if content.strip():
            text_chunks = self._semantic_chunking(content, section_name, document_id)
            chunks.extend(text_chunks)

        return chunks

    def _contains_table(self, content: str) -> bool:
        """테이블 포함 여부 확인"""
        table_indicators = [
            r"\|.*\|",  # 마크다운 테이블
            r"┌.*┐",  # 박스 테이블
            r"─{3,}",  # 구분선
            r"^\s*\d+\s+[가-힣]+\s+\d+",  # 숫자 데이터 행
        ]

        for pattern in table_indicators:
            if re.search(pattern, content, re.MULTILINE):
                return True
        return False

    def _chunk_tables(
        self, content: str, section: str, document_id: str
    ) -> List[DocumentChunk]:
        """테이블 청킹"""
        chunks = []

        # 테이블 패턴으로 분할
        table_pattern = r"((?:.*\|.*\n){2,}|(?:.*─.*\n)+(?:.*\n)*)"
        tables = re.findall(table_pattern, content, re.MULTILINE)

        for i, table in enumerate(tables):
            if len(table.strip()) > 50:  # 최소 크기 체크
                chunk = DocumentChunk(
                    chunk_id=f"{document_id}_table_{section}_{i}",
                    document_id=document_id,
                    content=table.strip(),
                    chunk_type="table",
                    section=section,
                    metadata={"table_index": i},
                )
                chunks.append(chunk)

        return chunks

    def _remove_tables(self, content: str) -> str:
        """테이블 제거"""
        table_pattern = r"((?:.*\|.*\n){2,}|(?:.*─.*\n)+(?:.*\n)*)"
        return re.sub(table_pattern, "", content, flags=re.MULTILINE)

    def _semantic_chunking(
        self, content: str, section: str, document_id: str
    ) -> List[DocumentChunk]:
        """의미 단위 청킹"""
        chunks = []

        # 단락별로 분할
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

        current_chunk = ""
        chunk_count = 0

        for paragraph in paragraphs:
            # 토큰 수 체크
            test_chunk = (
                current_chunk + "\n\n" + paragraph if current_chunk else paragraph
            )
            token_count = len(self.encoding.encode(test_chunk))

            if token_count <= self.max_tokens:
                current_chunk = test_chunk
            else:
                # 현재 청크 저장
                if current_chunk:
                    chunk = DocumentChunk(
                        chunk_id=f"{document_id}_text_{section}_{chunk_count}",
                        document_id=document_id,
                        content=current_chunk,
                        chunk_type="text",
                        section=section,
                        metadata={"paragraph_count": current_chunk.count("\n\n") + 1},
                    )
                    chunks.append(chunk)
                    chunk_count += 1

                # 새로운 청크 시작 (오버랩 적용)
                if current_chunk:
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = overlap_text + "\n\n" + paragraph
                else:
                    current_chunk = paragraph

        # 마지막 청크 처리
        if current_chunk:
            chunk = DocumentChunk(
                chunk_id=f"{document_id}_text_{section}_{chunk_count}",
                document_id=document_id,
                content=current_chunk,
                chunk_type="text",
                section=section,
                metadata={"paragraph_count": current_chunk.count("\n\n") + 1},
            )
            chunks.append(chunk)

        return chunks

    def _get_overlap_text(self, text: str) -> str:
        """오버랩 텍스트 추출"""
        sentences = text.split(".")
        overlap_sentences = sentences[-2:] if len(sentences) > 2 else sentences
        return ".".join(overlap_sentences).strip()

    def count_tokens(self, text: str) -> int:
        """토큰 수 계산"""
        return len(self.encoding.encode(text))
