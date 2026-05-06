"""Application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Config:
    """Simple config holder. No pydantic-settings dependency needed."""

    # LLM
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")
    LLM_MOCK_MODE: bool = os.getenv(
        "USE_MOCK_LLM",
        os.getenv("LLM_MOCK_MODE", "true"),
    ).lower() in ("1", "true", "yes")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))

    # App
    APP_TITLE: str = "ROCm AgentOps"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")
    INCIDENT_SOURCE_MODE: str = os.getenv("INCIDENT_SOURCE_MODE", "Demo Dataset")

    # Scoring
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.75

    # Live signal intake
    LIVE_SIGNAL_TIMEOUT: int = int(os.getenv("LIVE_SIGNAL_TIMEOUT", "10"))
    LIVE_LOG_PATHS: str = os.getenv("LIVE_LOG_PATHS", "")
    LIVE_GPU_UTIL_THRESHOLD: float = float(os.getenv("LIVE_GPU_UTIL_THRESHOLD", "92"))
    LIVE_GPU_MEMORY_THRESHOLD: float = float(os.getenv("LIVE_GPU_MEMORY_THRESHOLD", "90"))
    LIVE_P95_THRESHOLD_MS: float = float(os.getenv("LIVE_P95_THRESHOLD_MS", "2500"))
    LIVE_THROUGHPUT_MIN_TOKENS_PER_SECOND: float = float(
        os.getenv("LIVE_THROUGHPUT_MIN_TOKENS_PER_SECOND", "350")
    )

    @classmethod
    def is_mock(cls) -> bool:
        return cls.LLM_MOCK_MODE


config = Config()
