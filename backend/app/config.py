"""
SMM PANEL / SOCIAL GROWTH DASHBOARD - CONFIGURATION
DISCLAIMER: Simulation only – does not interact with TikTok.
"""
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # App Information
    PROJECT_NAME: str = "Sarab SMM Panel & Social Growth Simulator"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Security & JWT
    SECRET_KEY: str = "sarab-super-secret-jwt-key-change-in-production-2026-xyz"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://frontend:3000",
        "*"
    ]

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/smm_db"
    )
    # Sync database URL for sync operations/migrations if needed
    SYNC_DATABASE_URL: str = os.getenv(
        "SYNC_DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/smm_db"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Simulation Engine Defaults
    # GHI RO TRON CODE: Simulation only – does not interact with TikTok.
    SIMULATION_DISCLAIMER: str = "Simulation only – does not interact with TikTok."
    SIMULATION_ENABLED: bool = True
    SIMULATION_DEFAULT_SPEED: float = 1.0  # multiplier
    SIMULATION_STEP_INTERVAL_SEC: float = 2.0  # step update frequency in seconds
    SIMULATION_COMPLETION_RATE: float = 0.90  # 90% normal completion
    SIMULATION_PARTIAL_RATE: float = 0.08     # 8% partial completion
    SIMULATION_FAILURE_RATE: float = 0.02     # 2% simulation failure

    # Anti-Fraud & Limits
    RATE_LIMIT_PER_MINUTE: int = 60
    MAX_ACTIVE_ORDERS_PER_USER: int = 50
    DUPLICATE_ORDER_WINDOW_SECONDS: int = 60
    MIN_DEPOSIT_USD: float = 5.0
    MAX_DEPOSIT_USD: float = 5000.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
