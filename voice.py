"""AI Voice Assistant backend helpers: Groq Whisper & Google Gemini audio transcription."""

from __future__ import annotations

import base64
from typing import Any

import requests

from app.ai_config import resolve_provider_keys


GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"


def _transcribe_with_groq(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    api_key: str,
    language: str | None = None,
) -> dict[str, Any] | None:
    files = {
        "file": (filename or "voice.webm", audio_bytes, content_type or "audio/webm"),
    }
    data: dict[str, str] = {"model": GROQ_WHISPER_MODEL, "response_format": "json"}
    if language:
        data["language"] = language.split("-")[0]

    try:
        resp = requests.post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
            data=data,
            timeout=25,
        )
        if resp.status_code != 200:
            return None
        payload = resp.json()
        text = str(payload.get("text", "")).strip()
        if not text:
            return None
        return {"ok": True, "text": text, "engine": f"groq:{GROQ_WHISPER_MODEL}"}
    except Exception:
        return None


def _transcribe_with_gemini(
    audio_bytes: bytes,
    content_type: str,
    api_key: str,
    model: str,
) -> dict[str, Any] | None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    encoded = base64.b64encode(audio_bytes).decode("ascii")
    mime = content_type.split(";")[0].strip() if content_type else "audio/webm"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            "Transcribe this spoken user query accurately into plain text only. "
                            "Do not add commentary or quotes."
                        )
                    },
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": encoded,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 300},
    }

    try:
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=25,
        )
        if resp.status_code != 200:
            return None
        cand = (resp.json().get("candidates") or [{}])[0]
        parts = cand.get("content", {}).get("parts", [])
        text = " ".join(p.get("text", "") for p in parts if p.get("text")).strip()
        if not text:
            return None
        return {"ok": True, "text": text, "engine": f"gemini:{model}"}
    except Exception:
        return None


def transcribe_audio_bytes(
    audio_bytes: bytes,
    filename: str = "voice.webm",
    content_type: str = "audio/webm",
    provider: str | None = None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Transcribe uploaded voice audio using Groq Whisper or Google Gemini."""
    if not audio_bytes:
        return {"ok": False, "text": "", "error": "Recorded audio is empty."}

    eff_provider, groq_key, _, gemini_key, gemini_model = resolve_provider_keys(
        req_provider=provider,
        req_groq_key=groq_api_key,
        req_gemini_key=gemini_api_key,
    )

    order = (
        ["gemini", "groq"]
        if eff_provider == "gemini"
        else ["groq", "gemini"]
    )

    for prov in order:
        if prov == "groq" and groq_key:
            res = _transcribe_with_groq(audio_bytes, filename, content_type, groq_key, language)
            if res:
                return res
        elif prov == "gemini" and gemini_key:
            res = _transcribe_with_gemini(audio_bytes, content_type, gemini_key, gemini_model)
            if res:
                return res

    return {
        "ok": False,
        "text": "",
        "error": (
            "Audio file transcription requires a configured Groq or Google Gemini API key "
            "(or use a browser with built-in SpeechRecognition such as Chrome / Edge)."
        ),
    }
