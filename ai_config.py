"""AI provider configuration (Groq, Google Gemini, and built-in local fallback)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv, set_key


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT_DIR, ".env")

load_dotenv(ENV_PATH, override=False)

GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "mixtral-8x7b-32768",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


@dataclass
class AIRuntimeConfig:
    """In-memory AI provider settings initialized from environment / .env."""

    default_provider: str = field(
        default_factory=lambda: os.getenv("DEFAULT_AI_PROVIDER", "auto").strip().lower() or "auto"
    )
    groq_api_key: str = field(
        default_factory=lambda: os.getenv("GROQ_API_KEY", "").strip()
    )
    groq_model: str = field(
        default_factory=lambda: os.getenv("GROQ_MODEL", GROQ_MODELS[0]).strip() or GROQ_MODELS[0]
    )
    gemini_api_key: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip()
    )
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", GEMINI_MODELS[0]).strip() or GEMINI_MODELS[0]
    )


runtime_ai_config = AIRuntimeConfig()


def mask_key(key: str) -> str:
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= 10:
        return "*" * len(k)
    return f"{k[:6]}...{k[-4:]}"


def get_public_ai_config() -> dict[str, Any]:
    """Return safe, masked AI configuration metadata for the UI."""
    groq_key = runtime_ai_config.groq_api_key or os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = runtime_ai_config.gemini_api_key or os.getenv("GEMINI_API_KEY", "").strip()
    return {
        "default_provider": runtime_ai_config.default_provider,
        "groq_configured": bool(groq_key),
        "groq_key_masked": mask_key(groq_key),
        "groq_model": runtime_ai_config.groq_model,
        "groq_models": GROQ_MODELS,
        "gemini_configured": bool(gemini_key),
        "gemini_key_masked": mask_key(gemini_key),
        "gemini_model": runtime_ai_config.gemini_model,
        "gemini_models": GEMINI_MODELS,
    }


def resolve_provider_keys(
    req_provider: str | None = None,
    req_groq_key: str | None = None,
    req_gemini_key: str | None = None,
) -> tuple[str, str, str, str, str]:
    """Resolve effective (provider, groq_key, groq_model, gemini_key, gemini_model)."""
    provider = (req_provider or runtime_ai_config.default_provider or "auto").strip().lower()
    groq_key = (
        (req_groq_key or "").strip()
        or runtime_ai_config.groq_api_key
        or os.getenv("GROQ_API_KEY", "").strip()
    )
    gemini_key = (
        (req_gemini_key or "").strip()
        or runtime_ai_config.gemini_api_key
        or os.getenv("GEMINI_API_KEY", "").strip()
    )
    return (
        provider,
        groq_key,
        runtime_ai_config.groq_model,
        gemini_key,
        runtime_ai_config.gemini_model,
    )


def update_ai_config(
    default_provider: str | None = None,
    groq_api_key: str | None = None,
    groq_model: str | None = None,
    gemini_api_key: str | None = None,
    gemini_model: str | None = None,
    clear_groq: bool = False,
    clear_gemini: bool = False,
    persist_env: bool = True,
) -> dict[str, Any]:
    """Update runtime AI keys/models and optionally persist to .env."""
    if default_provider is not None and default_provider.strip().lower() in (
        "auto", "groq", "gemini", "local"
    ):
        runtime_ai_config.default_provider = default_provider.strip().lower()
        os.environ["DEFAULT_AI_PROVIDER"] = runtime_ai_config.default_provider

    if clear_groq:
        runtime_ai_config.groq_api_key = ""
        os.environ.pop("GROQ_API_KEY", None)
    elif groq_api_key is not None and groq_api_key.strip():
        runtime_ai_config.groq_api_key = groq_api_key.strip()
        os.environ["GROQ_API_KEY"] = runtime_ai_config.groq_api_key

    if groq_model and groq_model.strip():
        runtime_ai_config.groq_model = groq_model.strip()
        os.environ["GROQ_MODEL"] = runtime_ai_config.groq_model

    if clear_gemini:
        runtime_ai_config.gemini_api_key = ""
        os.environ.pop("GEMINI_API_KEY", None)
    elif gemini_api_key is not None and gemini_api_key.strip():
        runtime_ai_config.gemini_api_key = gemini_api_key.strip()
        os.environ["GEMINI_API_KEY"] = runtime_ai_config.gemini_api_key

    if gemini_model and gemini_model.strip():
        runtime_ai_config.gemini_model = gemini_model.strip()
        os.environ["GEMINI_MODEL"] = runtime_ai_config.gemini_model

    if persist_env:
        if not os.path.exists(ENV_PATH):
            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.write("# SL DataPulse API Configuration\n")
        set_key(ENV_PATH, "DEFAULT_AI_PROVIDER", runtime_ai_config.default_provider)
        set_key(ENV_PATH, "GROQ_MODEL", runtime_ai_config.groq_model)
        set_key(ENV_PATH, "GEMINI_MODEL", runtime_ai_config.gemini_model)
        if runtime_ai_config.groq_api_key or clear_groq:
            set_key(ENV_PATH, "GROQ_API_KEY", runtime_ai_config.groq_api_key)
        if runtime_ai_config.gemini_api_key or clear_gemini:
            set_key(ENV_PATH, "GEMINI_API_KEY", runtime_ai_config.gemini_api_key)

    return get_public_ai_config()


def test_provider_connection(
    provider: str, api_key: str | None = None, model: str | None = None
) -> dict[str, Any]:
    """Verify Groq or Google Gemini API connectivity using a minimal request."""
    prov = (provider or "").strip().lower()
    if prov == "groq":
        key = (api_key or "").strip() or runtime_ai_config.groq_api_key or os.getenv("GROQ_API_KEY", "").strip()
        mdl = (model or "").strip() or runtime_ai_config.groq_model
        if not key:
            return {"ok": False, "provider": "groq", "message": "No Groq API key provided."}
        try:
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": mdl,
                    "messages": [{"role": "user", "content": "Reply with OK"}],
                    "max_tokens": 5,
                    "temperature": 0,
                },
                timeout=12,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": "groq", "model": mdl, "message": f"Groq connected ({mdl})."}
            err_msg = resp.json().get("error", {}).get("message", resp.text[:180])
            return {"ok": False, "provider": "groq", "model": mdl, "message": f"Groq error ({resp.status_code}): {err_msg}"}
        except Exception as exc:
            return {"ok": False, "provider": "groq", "model": mdl, "message": f"Groq request failed: {exc}"}

    if prov == "gemini":
        key = (api_key or "").strip() or runtime_ai_config.gemini_api_key or os.getenv("GEMINI_API_KEY", "").strip()
        mdl = (model or "").strip() or runtime_ai_config.gemini_model
        if not key:
            return {"ok": False, "provider": "gemini", "message": "No Google Gemini API key provided."}
        try:
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": "Reply with OK"}]}]},
                timeout=12,
            )
            if resp.status_code == 200:
                return {"ok": True, "provider": "gemini", "model": mdl, "message": f"Google Gemini connected ({mdl})."}
            err_msg = resp.json().get("error", {}).get("message", resp.text[:180])
            return {"ok": False, "provider": "gemini", "model": mdl, "message": f"Gemini error ({resp.status_code}): {err_msg}"}
        except Exception as exc:
            return {"ok": False, "provider": "gemini", "model": mdl, "message": f"Gemini request failed: {exc}"}

    return {"ok": False, "provider": prov, "message": f"Unsupported provider '{provider}'."}
