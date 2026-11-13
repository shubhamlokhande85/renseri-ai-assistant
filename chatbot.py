"""Backward-compatible wrapper delegating to the unified SL AI Assistant."""

from __future__ import annotations

from typing import Any

from app.assistant import generate_suggested_questions, handle_assistant_message
from app.db_engine import DatasetSession


def handle_chat_message(
    session: DatasetSession,
    message: str,
    api_key: str | None = None,
    provider: str | None = None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
    mode: str = "auto",
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return handle_assistant_message(
        message=message,
        session=session,
        mode=mode,
        api_key=api_key,
        provider=provider,
        groq_api_key=groq_api_key,
        gemini_api_key=gemini_api_key,
        history=history,
    )


def handle_no_session_chat(
    message: str,
    mode: str = "auto",
    provider: str | None = None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return handle_assistant_message(
        message=message,
        session=None,
        mode=mode,
        provider=provider,
        groq_api_key=groq_api_key,
        gemini_api_key=gemini_api_key,
        history=history,
    )
