"""Shared Groq client configuration for all AI modules.

Reads GROQ_API_KEY and GROQ_MODEL from environment (or .env file).
All AI modules import from here — never instantiate Groq directly elsewhere.
"""

from __future__ import annotations

import os
from pathlib import Path

# Load .env file if present (development)
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent.parent.parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # python-dotenv not installed — rely on real env vars

# Default model: openai/gpt-oss-120b is best for reasoning/JSON extraction; openai/gpt-oss-20b for fast tasks
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
FAST_MODEL = os.environ.get("GROQ_FAST_MODEL", "openai/gpt-oss-20b")


def get_groq_client(api_key: str | None = None):
    """Return a configured Groq client.

    Args:
        api_key: Override the GROQ_API_KEY env var. If None, uses env var.

    Raises:
        ImportError: if the groq package is not installed.
        ValueError: if no API key is available.
    """
    try:
        from groq import Groq
    except ImportError:
        raise ImportError(
            "The 'groq' package is required for AI features. "
            "Run: pip install groq"
        )

    resolved_key = api_key or os.environ.get("GROQ_API_KEY")
    if not resolved_key:
        raise ValueError(
            "No GROQ_API_KEY found. Set it in your .env file or environment:\n"
            "  GROQ_API_KEY=gsk_..."
        )

    return Groq(api_key=resolved_key)
