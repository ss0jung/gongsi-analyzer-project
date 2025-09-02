import os
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, Field
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class Settings(BaseSettings):
    """RAG 시스템 설정"""

    # === OpenAI 설정 ===
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL"
    )
    openai_temperature: float = Field(default=0.1, env="OPENAI_TEMPERATURE")

    # === Chroma DB 설정 ===
    chroma_db_path: str = Field(default="./data/vectorstore", env="CHROMA_DB_PATH")
    chroma_collection_name: str = Field(
        default="gongsi_documents", env="CHROMA_COLLECTION_NAME"
    )

    # === API 서버 설정 ===
    api_host: str = Field(default="localhost", env="API_HOST")
    api_port: int = Field(default=8001, env="API_PORT")
    api_debug: bool = Field(default=True, env="API_DEBUG")

    # === 문서 처리 설정 ===
    # 부모-자식 청킹 설정
    parent_chunk_size: int = Field(default=5000, env="PARENT_CHUNK_SIZE")
    parent_chunk_overlap: int = Field(default=500, env="PARENT_CHUNK_OVERLAP")
    child_chunk_size: int = Field(default=800, env="CHILD_CHUNK_SIZE")
    child_chunk_overlap: int = Field(default=150, env="CHILD_CHUNK_OVERLAP")

    # PDF 처리 설정
    max_file_size_mb: int = Field(default=50, env="MAX_FILE_SIZE_MB")

    # === 데이터 경로 설정 ===
    data_base_path: str = Field(default="./data", env="DATA_BASE_PATH")
    documents_path: str = Field(default="./data/documents", env="DOCUMENTS_PATH")
    summaries_path: str = Field(default="./data/summaries", env="SUMMARIES_PATH")

    # === 로깅 설정 ===
    logs_path: str = Field(default="./logs", env="LOGS_PATH")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        env="LOG_FORMAT",
    )

    # === RAG 시스템 설정 ===
    # 검색 설정
    retrieval_k: int = Field(default=5, env="RETRIEVAL_K")  # 검색할 문서 개수
    similarity_threshold: float = Field(default=0.7, env="SIMILARITY_THRESHOLD")

    # 요약 설정
    summary_max_tokens: int = Field(default=500, env="SUMMARY_MAX_TOKENS")
    enable_summary_cache: bool = Field(default=True, env="ENABLE_SUMMARY_CACHE")

    # === LangChain/LangGraph 설정 ===
    # LangSmith 설정 (선택적)
    langsmith_api_key: Optional[str] = Field(default=None, env="LANGSMITH_API_KEY")
    langsmith_project: str = Field(default="gongsi-rag", env="LANGSMITH_PROJECT")
    langsmith_enabled: bool = Field(default=False, env="LANGSMITH_ENABLED")

    # === 성능 설정 ===
    # 캐싱 설정
    enable_embedding_cache: bool = Field(default=True, env="ENABLE_EMBEDDING_CACHE")
    cache_ttl_hours: int = Field(default=24, env="CACHE_TTL_HOURS")

    # 배치 처리 설정
    embedding_batch_size: int = Field(default=10, env="EMBEDDING_BATCH_SIZE")

    # === 개발/테스트 설정 ===
    environment: str = Field(default="development", env="ENVIRONMENT")
    test_mode: bool = Field(default=True, env="TEST_MODE")
    enable_summary_agent: bool = Field(default=True, env="ENABLE_SUMMARY_AGENT")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def model_post_init(self, __context):
        """설정 초기화 후 필요한 디렉토리들 생성"""
        self._create_directories()
        self._setup_logging()

    def _create_directories(self):
        """필요한 디렉토리들 생성"""
        directories = [
            self.chroma_db_path,
            self.documents_path,
            self.summaries_path,
            self.logs_path,
            f"{self.summaries_path}/by_doc_id",
            f"{self.summaries_path}/by_date",
        ]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def _setup_logging(self):
        """기본 로깅 설정"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format=self.log_format,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f"{self.logs_path}/app.log", encoding="utf-8"),
            ],
        )

    @property
    def summary_by_id_path(self) -> str:
        """문서 ID별 요약 저장 경로"""
        return f"{self.summaries_path}/by_doc_id"

    @property
    def summary_by_date_path(self) -> str:
        """날짜별 요약 저장 경로"""
        return f"{self.summaries_path}/by_date"


# 전역 설정 인스턴스
settings = Settings()


def get_settings() -> Settings:
    """설정 인스턴스 반환"""
    return settings


# === 검증 함수들 ===
def validate_openai_key() -> bool:
    """OpenAI API 키 유효성 검사"""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        # 간단한 임베딩 테스트
        response = client.embeddings.create(
            model=settings.openai_embedding_model, input="test"
        )
        return len(response.data) > 0

    except Exception as e:
        logging.error(f"OpenAI API 키 검증 실패: {e}")
        return False


def validate_chroma_connection() -> bool:
    """Chroma DB 연결 테스트"""
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings

        client = chromadb.PersistentClient(
            path=settings.chroma_db_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # 테스트 컬렉션 생성 시도
        test_collection = client.get_or_create_collection("test")
        return True

    except Exception as e:
        logging.error(f"Chroma DB 연결 실패: {e}")
        return False


def validate_langsmith_connection() -> bool:
    """LangSmith 연결 테스트 (활성화된 경우)"""
    if not settings.langsmith_enabled or not settings.langsmith_api_key:
        return True  # 비활성화된 경우 통과

    try:
        from langsmith import Client

        client = Client(api_key=settings.langsmith_api_key)
        # 간단한 연결 테스트
        projects = list(client.list_projects())
        return True

    except Exception as e:
        logging.error(f"LangSmith 연결 실패: {e}")
        return False


def validate_all_connections() -> dict:
    """모든 외부 서비스 연결 검증"""
    results = {
        "openai": validate_openai_key(),
        "chroma": validate_chroma_connection(),
        "langsmith": validate_langsmith_connection(),
    }

    all_passed = all(results.values())
    results["all_passed"] = all_passed

    return results


def print_settings():
    """현재 설정값 출력 (민감정보 제외)"""
    print("=" * 50)
    print("🤖 공시분석 RAG 시스템 설정")
    print("=" * 50)

    print("📋 기본 설정:")
    print(f"  • 환경: {settings.environment}")
    print(f"  • OpenAI 모델: {settings.openai_model}")
    print(f"  • 임베딩 모델: {settings.openai_embedding_model}")
    print(f"  • API 서버: {settings.api_host}:{settings.api_port}")

    print("\n📁 데이터 경로:")
    print(f"  • 문서: {settings.documents_path}")
    print(f"  • 요약: {settings.summaries_path}")
    print(f"  • 벡터DB: {settings.chroma_db_path}")
    print(f"  • 로그: {settings.logs_path}")

    print("\n⚙️ 처리 설정:")
    print(f"  • 부모 청크: {settings.parent_chunk_size} 토큰")
    print(f"  • 자식 청크: {settings.child_chunk_size} 토큰")
    print(f"  • 검색 개수: {settings.retrieval_k}개")
    print(f"  • 유사도 임계값: {settings.similarity_threshold}")

    print("\n🔧 기능 설정:")
    print(f"  • 테스트 모드: {'✅' if settings.test_mode else '❌'}")
    print(f"  • 요약 에이전트: {'✅' if settings.enable_summary_agent else '❌'}")
    print(f"  • 임베딩 캐시: {'✅' if settings.enable_embedding_cache else '❌'}")
    print(f"  • LangSmith: {'✅' if settings.langsmith_enabled else '❌'}")

    print("=" * 50)


def print_connection_status():
    """연결 상태 출력"""
    print("\n🔍 연결 상태 확인 중...")
    results = validate_all_connections()

    print("📡 외부 서비스 연결:")
    for service, status in results.items():
        if service == "all_passed":
            continue
        emoji = "✅" if status else "❌"
        print(f"  • {service.upper()}: {emoji}")

    overall = "✅ 모든 연결 성공!" if results["all_passed"] else "❌ 일부 연결 실패"
    print(f"\n🎯 전체 상태: {overall}")
    print("=" * 50)


# === 초기화 함수 ===
def initialize_system():
    """시스템 초기화"""
    print("🚀 RAG 시스템 초기화 중...")

    # 설정 출력
    print_settings()

    # 연결 확인
    print_connection_status()

    print("✅ 시스템 초기화 완료!")


if __name__ == "__main__":
    # 설정 테스트
    initialize_system()
