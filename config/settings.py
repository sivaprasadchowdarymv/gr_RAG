"""
Central configuration for Datasheet RAG Agent.

Every value can come from an environment variable, a `.env` file, or
Streamlit secrets (Streamlit Community Cloud). The only secret is
GROQ_API_KEY; it is never displayed or logged.
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

try:  # optional: read a local .env file
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Lookup helpers: environment first, then Streamlit secrets
# ---------------------------------------------------------------------------
def _secret(name: str):
    try:
        import streamlit as st

        value = st.secrets.get(name)  # raises if no secrets file exists
    except Exception:
        return None
    return None if value is None else str(value)


def _lookup(name: str):
    value = os.getenv(name)
    if value is not None and value.strip():
        return value
    return _secret(name)


def _env_str(name: str, default: str) -> str:
    return (_lookup(name) or "").strip() or default


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(_lookup(name) or default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(_lookup(name) or default)))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = _lookup(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Retrieval constants (unchanged from the original RAG)
# ---------------------------------------------------------------------------
SCORE_THRESHOLDS = {"text": 52, "table": 52, "row": 58, "equation": 48, "figure": 42}
AVG_CHARS_PER_TOK = 4
MAX_PREVIEW = 400


@dataclass(frozen=True)
class Settings:
    # --- Groq LLM ---------------------------------------------------------
    groq_api_key: str = field(repr=False)  # secret: never shown or logged
    groq_model: str
    groq_base_url: str  # empty = Groq default (only change for testing/proxies)
    llm_temperature: float
    max_output_tokens: int  # includes the model's hidden reasoning tokens
    llm_timeout: float

    # --- Agent --------------------------------------------------------------
    agent_mode: str  # "agent" (ReAct with tools) or "quick" (one call)
    agent_max_steps: int  # tool rounds before the agent must answer
    observation_chars: int  # max characters per tool observation

    # --- Embeddings (run inside the app) -------------------------------------
    embed_model: str

    # --- Retrieval / chunking ---------------------------------------------
    top_k: int
    max_chunk_tokens: int
    overlap_tokens: int
    max_context_chunks: int
    max_context_chars: int
    max_chars_per_chunk: int

    # --- Uploads / figures ------------------------------------------------
    max_upload_mb: int
    max_pages: int
    min_figure_px: int

    # --- Storage / misc ---------------------------------------------------
    data_dir: Path
    enable_feedback: bool
    log_level: str

    @property
    def parse_signature(self) -> Tuple:
        return (self.max_chunk_tokens, self.overlap_tokens, self.min_figure_px)


def _writable_dir(preferred: Path) -> Path:
    """Use `preferred` if writable, else a temp folder (read-only hosts)."""
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return preferred
    except OSError:
        import tempfile

        fallback = Path(tempfile.gettempdir()) / "datasheet-rag-agent-data"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def load_settings() -> Settings:
    mode = _env_str("AGENT_MODE", "agent").lower()
    return Settings(
        groq_api_key=(_lookup("GROQ_API_KEY") or "").strip(),
        groq_model=_env_str("GROQ_MODEL", "openai/gpt-oss-120b"),
        groq_base_url=_env_str("GROQ_BASE_URL", ""),
        llm_temperature=_env_float("LLM_TEMPERATURE", 0.1, 0.0, 2.0),
        max_output_tokens=_env_int("MAX_OUTPUT_TOKENS", 1500, 200, 8000),
        llm_timeout=_env_float("LLM_TIMEOUT", 60.0, 5.0, 600.0),
        agent_mode=mode if mode in {"agent", "quick"} else "agent",
        agent_max_steps=_env_int("AGENT_MAX_STEPS", 3, 1, 6),
        observation_chars=_env_int("OBSERVATION_CHARS", 1800, 400, 8000),
        embed_model=_env_str("EMBED_MODEL", "nomic-ai/nomic-embed-text-v1.5-Q"),
        top_k=_env_int("TOP_K", 3, 1, 10),
        max_chunk_tokens=_env_int("CHUNK_SIZE", 400, 100, 800),
        overlap_tokens=_env_int("CHUNK_OVERLAP", 60, 0, 150),
        max_context_chunks=_env_int("MAX_CONTEXT_CHUNKS", 6, 1, 20),
        max_context_chars=_env_int("MAX_CONTEXT_CHARS", 5000, 1000, 50000),
        max_chars_per_chunk=_env_int("MAX_CHARS_PER_CHUNK", 900, 200, 10000),
        max_upload_mb=_env_int("MAX_UPLOAD_MB", 25, 1, 500),
        max_pages=_env_int("MAX_PAGES", 300, 1, 5000),
        min_figure_px=_env_int("MIN_FIGURE_PX", 48, 0, 2000),
        data_dir=_writable_dir(Path(_env_str("DATA_DIR", str(PROJECT_ROOT / "data"))).resolve()),
        enable_feedback=_env_bool("ENABLE_FEEDBACK", False),
        log_level=_env_str("LOG_LEVEL", "INFO").upper(),
    )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGER_NAME = "datasheet_rag"


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s %(name)s  %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(getattr(logging, level, logging.INFO))
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")
