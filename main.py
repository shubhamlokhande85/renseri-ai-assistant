"""Starlette web application and API endpoints for the SQL Cleaning Chatbot."""

from __future__ import annotations

import os
from typing import Any

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from app.ai_config import (
    get_public_ai_config,
    test_provider_connection,
    update_ai_config,
)
from app.assistant import generate_suggested_questions, handle_assistant_message
from app.cleaner import CleaningOptions, load_dataframe_from_bytes
from app.dashboard import build_dashboard
from app.db_engine import (
    SessionManager,
    build_session_summary,
    execute_sql,
    export_dataset_bytes,
)
from app.samples import get_sample_catalog, load_sample_dataframe
from app.voice import transcribe_audio_bytes


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

session_manager = SessionManager()


def _parse_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _options_from_dict(data: dict[str, Any]) -> CleaningOptions:
    raw_round = data.get("round_decimals")
    round_decimals: int | None = None
    if raw_round not in (None, "", "none"):
        try:
            round_decimals = max(0, min(6, int(raw_round)))
        except (TypeError, ValueError):
            round_decimals = None

    raw_drop = data.get("drop_columns") or []
    if isinstance(raw_drop, str):
        drop_columns = [c.strip() for c in raw_drop.split(",") if c.strip()]
    elif isinstance(raw_drop, list):
        drop_columns = [str(c).strip() for c in raw_drop if str(c).strip()]
    else:
        drop_columns = []

    return CleaningOptions(
        strategy=str(data.get("strategy", "smart")),
        drop_duplicates=_parse_bool(data.get("drop_duplicates"), True),
        normalize_columns=_parse_bool(data.get("normalize_columns"), True),
        trim_strings=_parse_bool(data.get("trim_strings"), True),
        parse_numeric=_parse_bool(data.get("parse_numeric"), True),
        parse_dates=_parse_bool(data.get("parse_dates"), True),
        fill_missing=str(data.get("fill_missing", "smart")),
        text_case=str(data.get("text_case", "none")).lower(),
        fill_text_value=str(data.get("fill_text_value", "Unknown")),
        round_decimals=round_decimals,
        drop_columns=drop_columns,
        find_text=str(data.get("find_text", "")),
        replace_text=str(data.get("replace_text", "")),
        replace_column=str(data.get("replace_column", "")),
        # Power Query style transforms
        dtype_column=str(data.get("dtype_column", "")),
        dtype_target=str(data.get("dtype_target", "")),
        split_column=str(data.get("split_column", "")),
        split_delimiter=str(data.get("split_delimiter", "")),
        split_max_parts=int(data.get("split_max_parts", 2) or 2),
        extract_column=str(data.get("extract_column", "")),
        extract_mode=str(data.get("extract_mode", "")),
        extract_param=str(data.get("extract_param", "")),
        extract_output_col=str(data.get("extract_output_col", "")),
        # Power Query extended transforms
        filter_column=str(data.get("filter_column", "")),
        filter_condition=str(data.get("filter_condition", "")),
        filter_value=str(data.get("filter_value", "")),
        sort_column=str(data.get("sort_column", "")),
        sort_direction=str(data.get("sort_direction", "asc")),
        rename_column=str(data.get("rename_column", "")),
        rename_to=str(data.get("rename_to", "")),
        fill_direction_col=str(data.get("fill_direction_col", "")),
        fill_direction=str(data.get("fill_direction", "")),
    )


async def index(request: Request) -> FileResponse:
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "SL AI SQL Chatbot"})


async def list_samples(request: Request) -> JSONResponse:
    return JSONResponse({"samples": get_sample_catalog()})


async def load_sample(request: Request) -> JSONResponse:
    sample_id = request.path_params["sample_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}
    options = _options_from_dict(body if isinstance(body, dict) else {})

    try:
        filename, raw_df = load_sample_dataframe(sample_id)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=404)

    session = session_manager.create_session(filename, raw_df, options)
    payload = build_session_summary(session)
    payload["suggestions"] = generate_suggested_questions(session)
    return JSONResponse(payload)


async def upload_dataset(request: Request) -> JSONResponse:
    try:
        form = await request.form()
    except Exception as exc:
        return JSONResponse({"error": f"Invalid multipart upload: {exc}"}, status_code=400)

    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        return JSONResponse({"error": "No dataset file provided in 'file' field."}, status_code=400)

    filename = getattr(upload, "filename", None) or "dataset.csv"
    content = await upload.read()
    if not content:
        return JSONResponse({"error": "Uploaded file is empty."}, status_code=400)

    options = _options_from_dict(
        {
            "strategy": form.get("strategy", "smart"),
            "drop_duplicates": form.get("drop_duplicates", "true"),
            "normalize_columns": form.get("normalize_columns", "true"),
            "trim_strings": form.get("trim_strings", "true"),
            "parse_numeric": form.get("parse_numeric", "true"),
            "parse_dates": form.get("parse_dates", "true"),
            "fill_missing": form.get("fill_missing", "smart"),
        }
    )

    try:
        raw_df = load_dataframe_from_bytes(filename, content)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    if raw_df.empty and len(raw_df.columns) == 0:
        return JSONResponse({"error": "Dataset contains no readable columns or rows."}, status_code=400)

    session = session_manager.create_session(filename, raw_df, options)
    payload = build_session_summary(session)
    payload["suggestions"] = generate_suggested_questions(session)
    return JSONResponse(payload)


async def get_dataset(request: Request) -> JSONResponse:
    session_id = request.path_params["session_id"]
    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Dataset session not found."}, status_code=404)
    payload = build_session_summary(session)
    payload["suggestions"] = generate_suggested_questions(session)
    return JSONResponse(payload)


async def reclean_dataset(request: Request) -> JSONResponse:
    session_id = request.path_params["session_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}
    options = _options_from_dict(body if isinstance(body, dict) else {})
    session = session_manager.reclean_session(session_id, options)
    if not session:
        return JSONResponse({"error": "Dataset session not found."}, status_code=404)
    payload = build_session_summary(session)
    payload["suggestions"] = generate_suggested_questions(session)
    return JSONResponse(payload)


async def export_dataset(request: Request) -> Response:
    session_id = request.path_params["session_id"]
    fmt = request.query_params.get("format", "csv")
    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Dataset session not found."}, status_code=404)
    try:
        data, media_type, out_name = export_dataset_bytes(session, fmt)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


async def add_dataset_from_text(request: Request) -> JSONResponse:
    """Ingest a user-pasted CSV/TSV/JSON dataset, clean it, and load into SQLite."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    raw_text = (body.get("text") or "").strip()
    fmt = (body.get("format") or "csv").strip().lower().lstrip(".")
    name = (body.get("name") or f"user_dataset.{fmt}").strip()
    if not name.lower().endswith(f".{fmt}"):
        name = f"{name}.{fmt}"

    if not raw_text:
        return JSONResponse({"error": "Dataset text is empty."}, status_code=400)

    options = _options_from_dict(body.get("options") if isinstance(body.get("options"), dict) else body)
    try:
        raw_df = load_dataframe_from_bytes(name, raw_text.encode("utf-8"))
    except Exception as exc:
        return JSONResponse({"error": f"Could not parse pasted dataset: {exc}"}, status_code=400)

    if raw_df.empty and len(raw_df.columns) == 0:
        return JSONResponse({"error": "Dataset contains no readable columns or rows."}, status_code=400)

    session = session_manager.create_session(name, raw_df, options)
    payload = build_session_summary(session)
    payload["suggestions"] = generate_suggested_questions(session)
    return JSONResponse(payload)


async def chat(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    session_id = body.get("session_id", "")
    message = body.get("message", "")
    mode = (body.get("mode") or "auto").strip().lower()
    history = body.get("history") if isinstance(body.get("history"), list) else []
    api_key = body.get("api_key") or None
    provider = body.get("provider") or None
    groq_api_key = body.get("groq_api_key") or None
    gemini_api_key = body.get("gemini_api_key") or None

    session = session_manager.get_session(session_id)
    response_payload = handle_assistant_message(
        message=message,
        session=session,
        mode=mode,
        api_key=api_key,
        provider=provider,
        groq_api_key=groq_api_key,
        gemini_api_key=gemini_api_key,
        history=history,
    )
    return JSONResponse(response_payload)


async def run_sql(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    session_id = body.get("session_id", "")
    sql = body.get("sql", "")
    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Dataset session not found."}, status_code=404)

    result = execute_sql(session, sql)
    return JSONResponse(result)


async def generate_dashboard(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    session_id = body.get("session_id", "")
    prompt = body.get("prompt", "")
    filter_col = body.get("filter_col") or body.get("filter_column") or None
    filter_val = body.get("filter_val") or body.get("filter_value") or None
    filters = body.get("filters") if isinstance(body.get("filters"), dict) else None

    session = session_manager.get_session(session_id)
    if not session:
        return JSONResponse({"error": "Dataset session not found."}, status_code=404)

    dash = build_dashboard(
        session, prompt=prompt, filter_col=filter_col, filter_val=filter_val, filters=filters
    )
    return JSONResponse(dash)


async def ai_config_get(request: Request) -> JSONResponse:
    return JSONResponse(get_public_ai_config())


async def ai_config_post(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    cfg = update_ai_config(
        default_provider=body.get("default_provider"),
        groq_api_key=body.get("groq_api_key"),
        groq_model=body.get("groq_model"),
        gemini_api_key=body.get("gemini_api_key"),
        gemini_model=body.get("gemini_model"),
        clear_groq=bool(body.get("clear_groq", False)),
        clear_gemini=bool(body.get("clear_gemini", False)),
        persist_env=bool(body.get("persist_env", True)),
    )
    return JSONResponse(cfg)


async def ai_test_post(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body."}, status_code=400)

    res = test_provider_connection(
        provider=body.get("provider", ""),
        api_key=body.get("api_key"),
        model=body.get("model"),
    )
    return JSONResponse(res)


async def voice_transcribe_post(request: Request) -> JSONResponse:
    try:
        form = await request.form()
    except Exception as exc:
        return JSONResponse({"ok": False, "error": f"Invalid audio form upload: {exc}"}, status_code=400)

    audio_file = form.get("audio")
    if audio_file is None or not hasattr(audio_file, "read"):
        return JSONResponse({"ok": False, "error": "No audio recording provided in 'audio' field."}, status_code=400)

    audio_bytes = await audio_file.read()
    filename = getattr(audio_file, "filename", None) or "voice.webm"
    content_type = getattr(audio_file, "content_type", None) or "audio/webm"
    provider = str(form.get("provider", "")).strip() or None
    language = str(form.get("language", "")).strip() or None

    res = transcribe_audio_bytes(
        audio_bytes=audio_bytes,
        filename=filename,
        content_type=content_type,
        provider=provider,
        language=language,
    )
    status = 200 if res.get("ok") else 400
    return JSONResponse(res, status_code=status)


routes = [
    Route("/", index, methods=["GET"]),
    Route("/api/health", health, methods=["GET"]),
    Route("/api/samples", list_samples, methods=["GET"]),
    Route("/api/samples/{sample_id}", load_sample, methods=["POST"]),
    Route("/api/upload", upload_dataset, methods=["POST"]),
    Route("/api/dataset/from-text", add_dataset_from_text, methods=["POST"]),
    Route("/api/dataset/{session_id}", get_dataset, methods=["GET"]),
    Route("/api/dataset/{session_id}/reclean", reclean_dataset, methods=["POST"]),
    Route("/api/dataset/{session_id}/export", export_dataset, methods=["GET"]),
    Route("/api/chat", chat, methods=["POST"]),
    Route("/api/assistant/chat", chat, methods=["POST"]),
    Route("/api/sql", run_sql, methods=["POST"]),
    Route("/api/dashboard", generate_dashboard, methods=["POST"]),
    Route("/api/ai/config", ai_config_get, methods=["GET"]),
    Route("/api/ai/config", ai_config_post, methods=["POST"]),
    Route("/api/ai/test", ai_test_post, methods=["POST"]),
    Route("/api/voice/transcribe", voice_transcribe_post, methods=["POST"]),
    Mount("/static", StaticFiles(directory=STATIC_DIR), name="static"),
]

app = Starlette(debug=False, routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
