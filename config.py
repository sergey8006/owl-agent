"""
OWL Agent — centralized configuration.
All paths, constants, and settings in one place.
"""

import json
import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
SERVER_DIR = Path(__file__).resolve().parent
STATIC_DIR = SERVER_DIR / "static"
SKILLS_DIR = SERVER_DIR / "skills"
MEMORY_DIR = SERVER_DIR / "memory"
TEMPLATES_DIR = SERVER_DIR / "templates"

# Ensure required dirs exist
MEMORY_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# ── Server ───────────────────────────────────────────────────────────────────
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 7860
RATE_LIMIT_PER_MINUTE = 60

# ── Provider presets ─────────────────────────────────────────────────────────
PROVIDERS = {
    "lmstudio": {
        "label": "LM Studio",
        "default_url": "http://127.0.0.1:1234/v1",
        "default_key": "lm-studio",
    },
    "ollama": {
        "label": "Ollama",
        "default_url": "http://127.0.0.1:11434/v1",
        "default_key": "ollama",
    },
}

# ── Provider config persistence ──────────────────────────────────────────────
PROVIDER_CONFIG_PATH = SERVER_DIR / ".provider_config.json"


def load_provider_config() -> dict:
    """Load saved provider config from disk."""
    try:
        if PROVIDER_CONFIG_PATH.exists():
            return json.loads(PROVIDER_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_provider_config(provider: str, url: str, api_key: str, model: str = ""):
    """Save provider config to disk."""
    try:
        PROVIDER_CONFIG_PATH.write_text(
            json.dumps(
                {"provider": provider, "url": url, "api_key": api_key, "model": model},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


# ── CORS ─────────────────────────────────────────────────────────────────────
CORS_ORIGINS = ["*"]  # Allow all origins for local development

# ── Model detection timeout ─────────────────────────────────────────────────
MODEL_DETECT_TIMEOUT = 3  # seconds

# ── Conversation history limit ──────────────────────────────────────────────
MAX_CONVERSATION_HISTORY = 20  # messages kept in context
