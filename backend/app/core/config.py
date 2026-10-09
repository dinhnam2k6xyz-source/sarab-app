from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Novel Translator AI"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./novel_translator.db"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "novel_translator"
    POSTGRES_PORT: str = "5432"

    # Redis & Queue
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_REDIS_QUEUE: bool = False  # Set to True when Redis is connected

    # Security
    SECRET_KEY: str = "supersecretnoveltranslatorkey-change-in-production-123456"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["*"]

    # Translation Providers & Keys
    TRANSLATION_PROVIDER: str = "offline"  # gemini, openai, deepl, offline
    FALLBACK_PROVIDER: str = "offline"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"

    DEEPL_API_KEY: str = ""
    DEEPL_FORMALITY: str = "default"

    # Scraping & Anti-abuse
    SCRAPER_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )
    SCRAPER_TIMEOUT_SECONDS: int = 25
    SCRAPER_MAX_REDIRECTS: int = 5
    SCRAPER_MAX_BODY_BYTES: int = 15 * 1024 * 1024  # 15 MB

    # Rate Limiting
    RATE_LIMIT_ANALYZE_PER_MINUTE: int = 20
    RATE_LIMIT_TRANSLATE_PER_MINUTE: int = 60
    RATE_LIMIT_CRAWL_PER_MINUTE: int = 30

    # Chunking & Quality
    CHUNK_MAX_CHARS: int = 1800
    CHUNK_OVERLAP_CONTEXT_PARAS: int = 2
    QUALITY_MIN_RATIO: float = 0.20
    QUALITY_MAX_RATIO: float = 4.00
    TRANSLATION_MAX_RETRIES: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()
