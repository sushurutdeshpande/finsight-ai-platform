"""
Centralized configuration, validation, and logging setup.

All configurable values live here — no magic strings scattered across the app.
"""

import logging
import os
import sys
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


# ══════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════

class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""


class LLMConnectionError(Exception):
    """Raised when LLM API is unreachable or returns an error."""


class FileValidationError(Exception):
    """Raised when an uploaded file fails validation."""


class RAGProcessingError(Exception):
    """Raised when the PDF RAG pipeline encounters an error."""


# ══════════════════════════════════════════════════════
# APPLICATION CONFIG
# ══════════════════════════════════════════════════════

@dataclass(frozen=True)
class AppConfig:
    """Immutable application configuration loaded from environment."""

    # LLM
    groq_api_key: str = ""
    model_name: str = "openai/gpt-oss-120b"
    model_temperature: float = 0.0

    # File limits (MB)
    max_csv_size_mb: int = 50
    max_pdf_size_mb: int = 20

    # RAG settings
    chunk_size: int = 1000
    chunk_overlap: int = 200
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    retriever_top_k: int = 4

    # Supabase (auth & chat persistence)
    supabase_url: str = ""
    supabase_key: str = ""

    # OCR (Tesseract)
    tesseract_cmd: str = "tesseract"

    # Logging
    log_level: str = "INFO"

    # App metadata
    app_title: str = "FinSight — AI Financial Analysis Platform"
    app_icon: str = "📊"


def _get_env_or_secret(key: str, default: str = "") -> str:
    """Read a setting from environment variable or Streamlit secrets."""
    val = os.getenv(key, "")
    if not val:
        try:
            import streamlit as st
            val = st.secrets.get(key, "")
        except Exception:
            pass
    return str(val).strip() if val else default


def load_config() -> AppConfig:
    """
    Load configuration from environment variables with validation.

    Raises:
        ConfigurationError: If required variables are missing.
    """
    api_key = _get_env_or_secret("GROQ_API_KEY")

    if not api_key or api_key == "your_groq_api_key_here":
        raise ConfigurationError(
            "GROQ_API_KEY is not set. Please create a .env file with your API key.\n"
            "Get one free at: https://console.groq.com/keys\n"
            "Then add to .env: GROQ_API_KEY=your_key_here"
        )

    supabase_url = _get_env_or_secret("SUPABASE_URL")
    supabase_key = _get_env_or_secret("SUPABASE_KEY")

    # Supabase is optional — auth & chat persistence will be disabled without it
    if not supabase_url or supabase_url == "your_supabase_project_url":
        supabase_url = ""
    if not supabase_key or supabase_key == "your_supabase_anon_key":
        supabase_key = ""

    return AppConfig(
        groq_api_key=api_key,
        model_name=_get_env_or_secret("MODEL_NAME", "openai/gpt-oss-120b"),
        model_temperature=float(_get_env_or_secret("MODEL_TEMPERATURE", "0")),
        max_csv_size_mb=int(_get_env_or_secret("MAX_CSV_SIZE_MB", "50")),
        max_pdf_size_mb=int(_get_env_or_secret("MAX_PDF_SIZE_MB", "20")),
        chunk_size=int(_get_env_or_secret("CHUNK_SIZE", "1000")),
        chunk_overlap=int(_get_env_or_secret("CHUNK_OVERLAP", "200")),
        embedding_model=_get_env_or_secret(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        retriever_top_k=int(_get_env_or_secret("RETRIEVER_TOP_K", "4")),
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        tesseract_cmd=_get_env_or_secret("TESSERACT_CMD", "tesseract"),
        log_level=_get_env_or_secret("LOG_LEVEL", "INFO"),
    )


# ══════════════════════════════════════════════════════
# LOGGING SETUP
# ══════════════════════════════════════════════════════

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured logging for the application."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("faiss").setLevel(logging.WARNING)

    logger = logging.getLogger("financial_analyst")
    logger.setLevel(log_level)
    return logger
