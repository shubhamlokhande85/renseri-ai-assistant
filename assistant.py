"""Unified SL AI Assistant: Google Search Grounding, Groq/Gemini Chat, Dataset SQL & Dashboards."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import requests

from app.ai_config import resolve_provider_keys
from app.dashboard import build_dashboard
from app.db_engine import DatasetSession, execute_sql
from app.nl2sql import (
    _extract_where_clauses,
    find_mentioned_columns,
    translate_nl_to_sql,
)
from app.web_search import (
    extract_direct_answer,
    fetch_topic_card,
    format_google_results_markdown,
    search_google_and_web,
    strip_internal_result_fields,
)


SQL_START_RE = re.compile(
    r"^\s*(SELECT|WITH|PRAGMA|EXPLAIN|DROP|DELETE|INSERT|UPDATE|ALTER|CREATE)\b",
    re.IGNORECASE,
)

DASHBOARD_RE = re.compile(
    r"\b(?:create|build|generate|make|show|open|design|render)\b.*\bdashboard\b|^\s*dashboard\b",
    re.IGNORECASE,
)

WEB_SEARCH_RE = re.compile(
    r"\b(?:google|search\s+(?:the\s+)?web|search\s+online|fetch\s+(?:the\s+)?(?:current|live|latest)?\s*(?:data|info|news)?|"
    r"current\s+|live\s+|real[-\s]?time|latest\b|today(?:'s)?|weather\b|temperature\b|"
    r"stock\s+price|price\s+of|exchange\s+rate|news\s+about|breaking\s+news|who\s+is|what\s+is|tell\s+me\s+about|"
    r"tell\s+me\s+(?:the\s+)?name|name\s+of|capital\s+of|currency\s+of|(?:prime\s+)?min[ie]ster|president\s+of|ceo\s+of)\b",
    re.IGNORECASE,
)

DATASET_META_RE = re.compile(
    r"\b(clean(?:ing)?\s+report|what\s+was\s+cleaned|cleaning\s+summary|show\s+cleaning|audit\s+log|"
    r"schema|columns|fields|describe\s+table|table\s+info|summary\s+stats|summary\s+statistics|"
    r"how\s+many\s+rows|total\s+rows|top\s+\d+)\b",
    re.IGNORECASE,
)


def generate_suggested_questions(session: DatasetSession | None = None) -> list[str]:
    """Generate starter prompts tailored to whether a dataset is loaded."""
    if not session:
        return [
            "Search Google for latest AI trends",
            "What is SQLite vs PostgreSQL?",
            "How does dataset cleaning work?",
        ]

    profiles = session.profiles
    suggestions: list[str] = [
        "Create analytics dashboard",
        "How many rows are in the dataset?",
        "Show cleaning report",
    ]

    num_cols = [
        p for p in profiles
        if p.semantic_type in ("integer", "numeric") and p.name != "id" and not p.name.endswith("_id")
    ]
    cat_cols = [
        p for p in profiles
        if p.semantic_type == "text" and 2 <= p.distinct_count <= 30
    ]
    date_cols = [p for p in profiles if p.semantic_type == "date"]

    if num_cols and cat_cols:
        suggestions.append(f"Total {num_cols[0].name} by {cat_cols[0].name}")
        suggestions.append(f"Average {num_cols[0].name} per {cat_cols[0].name}")
    elif cat_cols:
        suggestions.append(f"Breakdown by {cat_cols[0].name}")

    if num_cols:
        suggestions.append(f"Top 5 rows by {num_cols[0].name}")
    if date_cols and num_cols:
        suggestions.append(f"Monthly {num_cols[0].name}")

    return suggestions[:7]


def _infer_chart(columns: list[str], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Infer KPI card, bar chart, or line chart from SQL results."""
    if not rows or not columns:
        return None

    if len(rows) == 1 and len(columns) <= 4:
        kpis = []
        for col in columns:
            val = rows[0].get(col)
            if isinstance(val, (int, float)):
                kpis.append({"label": col, "value": val})
        if kpis:
            return {"type": "kpi", "items": kpis}

    if 2 <= len(rows) <= 40 and len(columns) >= 2:
        label_col = columns[0]
        numeric_cols = [
            c for c in columns[1:]
            if any(isinstance(r.get(c), (int, float)) for r in rows)
        ]
        if numeric_cols:
            value_col = numeric_cols[0]
            chart_type = (
                "line"
                if label_col in ("period", "date", "month", "year")
                or "date" in label_col
                or "month" in label_col
                else "bar"
            )
            points = [
                {
                    "label": str(r.get(label_col) if r.get(label_col) is not None else "NULL"),
                    "value": float(r.get(value_col) or 0),
                }
                for r in rows[:20]
            ]
            return {
                "type": chart_type,
                "x_label": label_col,
                "y_label": value_col,
                "points": points,
            }
    return None


def _summarize_sql_result(result: dict[str, Any], explanation: str) -> str:
    if not result.get("ok"):
        return f"Query could not be executed: {result.get('error')}"

    rows = result.get("rows", [])
    cols = result.get("columns", [])
    count = result.get("row_count", 0)
    ms = result.get("execution_ms", 0)

    if count == 0:
        return f"{explanation} No matching rows were found ({ms} ms)."
    if count == 1 and len(cols) == 1:
        val = rows[0][cols[0]]
        return f"{explanation} Result: **{cols[0]} = {val}** ({ms} ms)."
    if count == 1 and len(cols) <= 6:
        pairs = ", ".join(f"**{c}**: {rows[0][c]}" for c in cols)
        return f"{explanation} Output: {pairs} ({ms} ms)."

    trunc_note = " (showing first 500 rows)" if result.get("truncated") else ""
    return f"{explanation} Returned **{count} row(s)**{trunc_note} in {ms} ms."


def _is_dataset_intent(text: str, session: DatasetSession | None, mode: str) -> bool:
    """Decide whether a message targets the uploaded dataset or general/Google AI."""
    if mode in ("dataset", "dashboard"):
        return True
    if mode in ("web", "chat"):
        return False
    if session is None:
        return False

    q_lower = text.lower()
    if SQL_START_RE.match(text) or DASHBOARD_RE.search(text) or DATASET_META_RE.search(q_lower):
        return True
    if WEB_SEARCH_RE.search(q_lower):
        return False

    # Check if any dataset column name, table name, or categorical value appears
    if session.table_name.lower() in q_lower:
        return True
    if find_mentioned_columns(text, session.profiles):
        return True
    clauses, _ = _extract_where_clauses(text, session.profiles)
    if clauses:
        return True

    data_words = (
        "dataset", "table", "row", "rows", "record", "records", "column", "columns",
        "csv", "excel", "average", "avg", "sum", "total", "count", "group by", "filter",
    )
    return any(re.search(rf"\b{re.escape(w)}\b", q_lower) for w in data_words)


def _call_gemini_assistant(
    prompt: str,
    api_key: str,
    model: str,
    use_google_search: bool = True,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Call Google Gemini API with optional native Google Search grounding."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    contents: list[dict[str, Any]] = []
    for turn in (history or [])[-6:]:
        role = "user" if turn.get("role") == "user" else "model"
        msg_text = turn.get("content") or turn.get("text") or ""
        if msg_text:
            contents.append({"role": role, "parts": [{"text": msg_text}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload: dict[str, Any] = {
        "contents": contents,
        "systemInstruction": {
            "parts": [
                {
                    "text": (
                        f"You are RENSERI AI ASSISTANT. Today is {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC. "
                        "Provide a comprehensive, in-depth description of the topic or question. "
                        "Structure your response with clear sections (e.g. Overview & Background, Key Dimensions / Features, Current Significance & Impact). "
                        "After the in-depth description, always include a dedicated section with clickable reference links titled '### 🔗 Reference Links & Sources'."
                    )
                }
            ]
        },
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 900},
    }
    if use_google_search:
        payload["tools"] = [{"google_search": {}}]

    try:
        resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=18)
        if resp.status_code == 400 and use_google_search:
            # Retry without google_search tool if model/account rejects tool format
            payload.pop("tools", None)
            resp = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=18)
        if resp.status_code != 200:
            return None

        data = resp.json()
        cand = (data.get("candidates") or [{}])[0]
        parts = cand.get("content", {}).get("parts", [])
        text = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
        if not text:
            return None

        # Extract Google Search grounding sources if returned
        sources: list[dict[str, str]] = []
        grounding = cand.get("groundingMetadata") or {}
        for chunk in grounding.get("groundingChunks") or []:
            web = chunk.get("web") or {}
            if web.get("uri"):
                sources.append({
                    "title": web.get("title") or web["uri"],
                    "url": web["uri"],
                    "source": "Google Search",
                })

        return {
            "reply": text,
            "engine": f"gemini:{model}",
            "sources": sources,
        }
    except Exception:
        return None


def _call_groq_assistant(
    prompt: str,
    api_key: str,
    model: str,
    web_results: list[dict[str, str]] | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    """Call Groq chat completions, optionally grounded in live web/Google results."""
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                f"You are RENSERI AI ASSISTANT. Today is {datetime.now(timezone.utc).strftime('%Y-%m-%d')} UTC. "
                "Provide a comprehensive, in-depth description of the topic or question. "
                "Structure your response with clear sections (e.g. Overview & Background, Key Dimensions / Features, Current Significance & Impact). "
                "After the in-depth description, always include a dedicated section with clickable reference links titled '### 🔗 Reference Links & Sources'."
            ),
        }
    ]
    for turn in (history or [])[-6:]:
        role = "user" if turn.get("role") == "user" else "assistant"
        msg_text = turn.get("content") or turn.get("text") or ""
        if msg_text:
            messages.append({"role": role, "content": msg_text})

    user_content = prompt
    if web_results:
        direct_fact = extract_direct_answer(prompt, web_results)
        ctx_lines = [
            f"- [{r['title']}]({r['url']}) ({r.get('source', 'Web')}): {r.get('snippet', '')}"
            for r in web_results
        ]
        fact_banner = f"\nVerified Infobox / Direct Fact: {direct_fact}\n" if direct_fact else ""
        user_content = (
            f"User Question: {prompt}{fact_banner}\n\n"
            f"Live Google & Web Search Results:\n" + "\n".join(ctx_lines) +
            "\n\nInstruction: First give an in-depth, structured description covering key aspects of the topic. "
            "Then conclude with a '### 🔗 Reference Links & Sources' section containing markdown links to the verified sources."
        )
    messages.append({"role": "user", "content": user_content})

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 900,
            },
            timeout=18,
        )
        if resp.status_code != 200:
            return None
        text = resp.json()["choices"][0]["message"]["content"].strip()
        if not text:
            return None
        return {
            "reply": text,
            "engine": f"groq:{model}",
            "sources": web_results or [],
        }
    except Exception:
        return None


def _build_ai_answer_payload(
    query: str,
    reply: str,
    engine: str,
    raw_results: list[dict[str, Any]] | None = None,
    sources: list[dict[str, str]] | None = None,
    session: DatasetSession | None = None,
) -> dict[str, Any]:
    """Build a uniform AI answer response with stripped sources and optional visual topic card."""
    clean_reply = (reply or "").strip()
    topic_card = fetch_topic_card(query, results=raw_results, reply=clean_reply)
    resolved_sources = sources if sources is not None else strip_internal_result_fields(raw_results or [])

    if topic_card and topic_card.get("url"):
        card_url = topic_card["url"]
        if not any(s.get("url") == card_url for s in resolved_sources):
            resolved_sources.append({
                "title": f"{topic_card.get('title', 'Topic')} — Wikipedia",
                "url": card_url,
                "source": "Wikipedia",
                "snippet": topic_card.get("description", ""),
                "published": "Reference",
            })

    if resolved_sources and "### 🔗 Reference Links & Sources" not in clean_reply and "### Reference Links" not in clean_reply:
        links_lines = []
        seen_urls = set()
        for s in resolved_sources:
            url = s.get("url")
            if url and url not in seen_urls and not str(url).startswith("https://news.google.com/rss/articles/"):
                seen_urls.add(url)
                title = s.get("title") or s.get("source") or "Web Source"
                links_lines.append(f"- [{title}]({url})")
            if len(links_lines) >= 4:
                break
        if links_lines:
            clean_reply = f"{clean_reply}\n\n### 🔗 Reference Links & Sources\n" + "\n".join(links_lines)

    payload: dict[str, Any] = {
        "reply": clean_reply,
        "type": "ai_answer",
        "engine": engine,
        "sources": resolved_sources,
        "suggestions": generate_suggested_questions(session),
    }
    if topic_card:
        payload["topic_card"] = topic_card
    return payload


def _handle_web_or_general_ai(
    text: str,
    mode: str,
    provider: str | None = None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
    history: list[dict[str, str]] | None = None,
    session: DatasetSession | None = None,
) -> dict[str, Any]:
    """Handle Google/Web live fetch & general AI Assistant conversation."""
    eff_provider, groq_key, groq_model, gemini_key, gemini_model = resolve_provider_keys(
        req_provider=provider,
        req_groq_key=groq_api_key,
        req_gemini_key=gemini_api_key,
    )
    wants_web = mode == "web" or bool(WEB_SEARCH_RE.search(text))

    # 1. If Gemini is selected or Auto+Gemini is preferred for Google Search grounding
    if eff_provider == "gemini" and gemini_key:
        gem_res = _call_gemini_assistant(
            text, gemini_key, gemini_model, use_google_search=True, history=history
        )
        if gem_res:
            raw_sources = gem_res.get("sources") or (
                search_google_and_web(text, max_results=5) if wants_web else []
            )
            return _build_ai_answer_payload(
                text, gem_res["reply"], gem_res["engine"], raw_results=raw_sources, session=session
            )

    # 2. If Auto and wants_web with Gemini key available -> try Gemini Google Grounding first
    if eff_provider == "auto" and wants_web and gemini_key:
        gem_res = _call_gemini_assistant(
            text, gemini_key, gemini_model, use_google_search=True, history=history
        )
        if gem_res:
            raw_sources = gem_res.get("sources") or search_google_and_web(text, max_results=5)
            return _build_ai_answer_payload(
                text, gem_res["reply"], gem_res["engine"], raw_results=raw_sources, session=session
            )

    # 3. Fetch web/Google results if web lookup requested (or for Groq grounding)
    web_results = search_google_and_web(text, max_results=5) if wants_web else []

    if eff_provider in ("auto", "groq") and groq_key:
        groq_res = _call_groq_assistant(
            text, groq_key, groq_model, web_results=web_results, history=history
        )
        if groq_res:
            raw_sources = groq_res.get("sources") or []
            return _build_ai_answer_payload(
                text, groq_res["reply"], groq_res["engine"], raw_results=raw_sources, session=session
            )

    if eff_provider in ("auto", "gemini") and gemini_key:
        gem_res = _call_gemini_assistant(
            text, gemini_key, gemini_model, use_google_search=True, history=history
        )
        if gem_res:
            raw_sources = gem_res.get("sources") or web_results
            return _build_ai_answer_payload(
                text, gem_res["reply"], gem_res["engine"], raw_results=raw_sources, session=session
            )

    # 4. Offline / Live Web Fetch fallback when no API key is configured
    if not web_results and mode == "web":
        web_results = search_google_and_web(text, max_results=5)
    elif not web_results and eff_provider == "local" and WEB_SEARCH_RE.search(text):
        web_results = search_google_and_web(text, max_results=5)

    if web_results:
        formatted = format_google_results_markdown(
            text, web_results, include_ai_tip=not (groq_key or gemini_key)
        )
        return _build_ai_answer_payload(
            text, formatted, "web_fetch", raw_results=web_results, session=session
        )

    # General offline greeting / capability overview
    if re.search(r"\b(clean|cleaning|how\s+does|what\s+can|features|help|hi|hello|hey|eda|analysis)\b", text.lower()):
        return {
            "reply": (
                "Hello! I'm **RENSERI AI ASSISTANT** — your full-scale Data Analysis Assistant for end-to-end data workflows:\n"
                "- **Dataset Ingestion & Auto-Cleaning**: Ingest CSV, Excel (.xlsx/.xls), JSON, Parquet, or raw text with automated type inference, missing value imputation, and deduplication.\n"
                "- **Exploratory Data Analysis (EDA)**: View statistical five-number summaries, skewness, Pearson correlation pairs, and top category concentrations.\n"
                "- **Interactive Dashboard with Slicers & KPIs**: Auto-generate executive dashboards with dynamic categorical slicers, real-time KPI aggregations, and high-impact charts.\n"
                "- **Executive Analytical Reports & Recommendations**: Structured business findings, risk alerts, and prioritized action plans for stakeholders.\n"
                "- **Google & Web Knowledge**: Real-time factual lookups and LLM synthesis powered by Groq and Google Gemini."
            ),
            "type": "ai_answer",
            "engine": "local",
            "quick_actions": (
                [
                    {"action": "upload", "label": "+ Upload Dataset"},
                    {"action": "paste", "label": "Paste CSV / JSON"},
                    {"action": "sample", "sample_id": "retail_sales", "label": "Load Retail Sales Sample"},
                ]
                if not session
                else []
            ),
            "suggestions": generate_suggested_questions(session),
        }

    # Try one quick web fetch for general factual questions even without explicit "google" keyword
    auto_web = search_google_and_web(text, max_results=5)
    if auto_web:
        formatted = format_google_results_markdown(
            text, auto_web, include_ai_tip=not (groq_key or gemini_key)
        )
        return _build_ai_answer_payload(
            text, formatted, "web_fetch", raw_results=auto_web, session=session
        )

    return {
        "reply": (
            "Add your **Groq** or **Google Gemini** API key in **API Keys** for full conversational AI & Google Search grounding, "
            "or **upload / paste a dataset** to clean it, query it with SQL, and build interactive dashboards!"
        ),
        "type": "ai_answer",
        "engine": "local",
        "quick_actions": [
            {"action": "keys", "label": "Configure Groq / Gemini Keys"},
            {"action": "upload", "label": "+ Upload Dataset"},
            {"action": "sample", "sample_id": "retail_sales", "label": "Try Sample Dataset"},
        ],
        "suggestions": generate_suggested_questions(session),
    }


def handle_assistant_message(
    message: str,
    session: DatasetSession | None = None,
    mode: str = "auto",
    api_key: str | None = None,
    provider: str | None = None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Main unified entry point for SL AI Assistant."""
    text = (message or "").strip()
    if not text:
        return {
            "reply": "Please enter a question, Google search query, SQL command, or dataset prompt.",
            "type": "info",
            "suggestions": generate_suggested_questions(session),
        }

    # Explicit general mode keeps Feature 1 (AI Assistant) 100% independent of any attached dataset
    if mode in ("web", "chat", "general"):
        return _handle_web_or_general_ai(
            text=text,
            mode="web" if mode == "web" else mode,
            provider=provider,
            groq_api_key=groq_api_key or api_key,
            gemini_api_key=gemini_api_key,
            history=history,
            session=None,
        )

    # If user explicitly picked dataset/dashboard mode without a dataset, guide cleanly
    if mode in ("dataset", "dashboard") and session is None:
        return {
            "reply": "No dataset is loaded yet! Use **Upload Dataset** to attach a CSV, Excel, JSON, or Parquet file first.",
            "type": "no_dataset",
            "quick_actions": [
                {"action": "upload", "label": "Upload Dataset"},
                {"action": "sample", "sample_id": "retail_sales", "label": "Try Retail Sales Sample"},
            ],
            "suggestions": generate_suggested_questions(None),
        }

    # Route to Dataset & SQL pipeline if applicable
    if session is not None and _is_dataset_intent(text, session, mode):
        q_lower = text.lower()

        if re.search(
            r"\b(clean(?:ing)?\s+report|what\s+was\s+cleaned|cleaning\s+summary|show\s+cleaning|audit\s+log)\b",
            q_lower,
        ):
            rep = session.report
            action_lines = [f"- {a['description']}" for a in rep.actions] or [
                "- Dataset was already clean; no transformations required."
            ]
            warn_lines = [f"- Warning: {w}" for w in rep.warnings]
            reply = (
                f"**Cleaning Summary for `{session.filename}`**\n"
                f"- Rows: {rep.original_rows} → **{rep.cleaned_rows}** "
                f"(removed {rep.duplicates_removed} duplicate(s), {rep.empty_rows_removed} empty row(s))\n"
                f"- Columns: {rep.original_cols} → **{rep.cleaned_cols}**\n"
                f"- Missing cells: {rep.original_missing_cells} → **{rep.cleaned_missing_cells}**\n"
                f"- Quality score: {rep.quality_score_before}% → **{rep.quality_score_after}%**\n\n"
                + "\n".join(action_lines)
                + ("\n\n" + "\n".join(warn_lines) if warn_lines else "")
            )
            return {
                "reply": reply,
                "type": "cleaning_report",
                "report": rep.to_dict(),
                "suggestions": generate_suggested_questions(session),
            }

        if re.search(r"^(?:show\s+)?(?:schema|columns|fields|describe|table\s+info)\b", q_lower):
            sql = f'PRAGMA table_info("{session.table_name}");'
            res = execute_sql(session, sql)
            col_list = ", ".join(f"`{p.name}` ({p.semantic_type})" for p in session.profiles)
            return {
                "reply": f"Table **`{session.table_name}`** has **{len(session.profiles)} columns**: {col_list}",
                "type": "sql_result",
                "sql": sql,
                "engine": "schema",
                "result": res,
                "suggestions": generate_suggested_questions(session),
            }

        if mode == "dashboard" or DASHBOARD_RE.search(text):
            dash = build_dashboard(session, prompt=text)
            reply = (
                f"Generated **`{dash['title']}`** using SQL queries on your cleaned dataset "
                f"(**{len(dash.get('kpis', []))} KPIs**, **{len(dash.get('charts', []))} charts**, and top records table)."
            )
            session.chat_history.append({"user": text, "sql": "DASHBOARD", "ok": True})
            return {
                "reply": reply,
                "type": "dashboard",
                "dashboard": dash,
                "suggestions": generate_suggested_questions(session),
            }

        if SQL_START_RE.match(text):
            res = execute_sql(session, text)
            chart = _infer_chart(res.get("columns", []), res.get("rows", [])) if res.get("ok") else None
            reply = _summarize_sql_result(res, "Executed your SQL query.")
            session.chat_history.append({"user": text, "sql": text, "ok": res.get("ok")})
            return {
                "reply": reply,
                "type": "sql_result",
                "sql": text,
                "engine": "direct_sql",
                "result": res,
                "chart": chart,
                "suggestions": generate_suggested_questions(session),
            }

        nl_res = translate_nl_to_sql(
            text,
            session,
            api_key=api_key,
            provider=provider,
            groq_api_key=groq_api_key,
            gemini_api_key=gemini_api_key,
        )
        exec_res = execute_sql(session, nl_res.sql)
        chart = (
            _infer_chart(exec_res.get("columns", []), exec_res.get("rows", []))
            if exec_res.get("ok")
            else None
        )
        reply = _summarize_sql_result(exec_res, nl_res.explanation)
        session.chat_history.append({"user": text, "sql": nl_res.sql, "ok": exec_res.get("ok")})
        return {
            "reply": reply,
            "type": "sql_result",
            "sql": nl_res.sql,
            "engine": nl_res.engine,
            "confidence": nl_res.confidence,
            "result": exec_res,
            "chart": chart,
            "suggestions": generate_suggested_questions(session),
        }

    # Route to Google / Web Fetch & General AI Assistant
    return _handle_web_or_general_ai(
        text=text,
        mode=mode,
        provider=provider,
        groq_api_key=groq_api_key,
        gemini_api_key=gemini_api_key,
        history=history,
        session=session,
    )
