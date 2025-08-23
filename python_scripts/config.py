from pydantic import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    NAVER_CLIENT_ID: str = os.getenv("NAVER_CLIENT_ID")
    NAVER_CLIENT_SECRET: str = os.getenv("NAVER_CLIENT_SECRET")

    # OpenAI Models
    OPENAI_MODEL: str = "gpt-4"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Naver News API
    NAVER_NEWS_URL: str = "https://openapi.naver.com/v1/search/news.json"
    NEWS_SEARCH_MONTHS: int = 3
    NEWS_DISPLAY_COUNT: int = 20

    # Vector Database
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    COLLECTION_NAME: str = "dart_documents"

    # Chunking Settings
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 200
    MAX_TOKENS_PER_CHUNK: int = 1000

    # Summary Settings
    SUMMARY_MAX_LENGTH: int = 1500  # 약 A4 1페이지
    SUMMARY_TIMEOUT: int = 60  # 1분 제한

    # Processing Settings
    MAX_CONCURRENT_CHUNKS: int = 5
    EMBEDDING_BATCH_SIZE: int = 10

    # FastAPI Settings
    APP_TITLE: str = "공시 분석 AI API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
