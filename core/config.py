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
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_MOCK_MODE: bool = os.getenv("LLM_MOCK_MODE", "true").lower() in ("1", "true", "yes")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))

    # App
    APP_TITLE: str = "ROCm AgentOps"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("1", "true", "yes")

    # Scoring
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.75

    @classmethod
    def is_mock(cls) -> bool:
        return cls.LLM_MOCK_MODE


config = Config()
