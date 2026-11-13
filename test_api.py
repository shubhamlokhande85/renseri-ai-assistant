"""End-to-end API tests for the Starlette SQL Chatbot web application."""

import socket
import threading
import time

import pytest
import requests
import uvicorn

from app.main import app


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def base_url():
    port = _find_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    for _ in range(40):
        try:
            r = requests.get(f"{url}/api/health", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)

    yield url
    server.should_exit = True
    thread.join(timeout=3)


def test_health_and_ui(base_url):
    r_health = requests.get(f"{base_url}/api/health", timeout=5)
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "ok"

    r_ui = requests.get(f"{base_url}/", timeout=5)
    assert r_ui.status_code == 200
    assert "RENSERI AI ASSISTANT" in r_ui.text

    # Chat before uploading returns interactive quick actions instead of 404
    r_pre = requests.post(
        f"{base_url}/api/chat",
        json={"session_id": "", "message": "How does dataset cleaning work?"},
        timeout=5,
    )
    assert r_pre.status_code == 200
    pre_data = r_pre.json()
    assert pre_data["type"] in ("ai_answer", "no_dataset")
    assert len(pre_data["quick_actions"]) >= 2


def test_upload_clean_chat_reclean_and_export_flow(base_url):
    csv_content = (
        "Customer Name,Region,Amount ($),Join Date\n"
        '  Alice ,North,"$1,000.00",2024-01-10\n'
        '  Alice ,North,"$1,000.00",2024-01-10\n'
        "Bob,South,$500.00,02/15/2024\n"
        "Carol,N/A,null,Mar 01 2024\n"
    ).encode("utf-8")

    # 1. Upload dataset
    r_up = requests.post(
        f"{base_url}/api/upload",
        files={"file": ("sales_test.csv", csv_content, "text/csv")},
        data={"strategy": "smart"},
        timeout=5,
    )
    assert r_up.status_code == 200
    payload = r_up.json()
    session_id = payload["session_id"]
    assert payload["report"]["duplicates_removed"] == 1
    assert payload["report"]["cleaned_rows"] == 3

    # 2. Chat natural language question
    r_chat = requests.post(
        f"{base_url}/api/chat",
        json={"session_id": session_id, "message": "Total amount by region"},
        timeout=5,
    )
    assert r_chat.status_code == 200
    chat_data = r_chat.json()
    assert chat_data["result"]["ok"] is True
    assert chat_data["result"]["row_count"] >= 2

    # 3. Direct SQL execution
    r_sql = requests.post(
        f"{base_url}/api/sql",
        json={"session_id": session_id, "sql": 'SELECT COUNT(*) AS cnt FROM "sales_test";'},
        timeout=5,
    )
    assert r_sql.status_code == 200
    assert r_sql.json()["rows"][0]["cnt"] == 3

    # 4. Re-clean with keep_nulls strategy
    r_reclean = requests.post(
        f"{base_url}/api/dataset/{session_id}/reclean",
        json={"strategy": "keep_nulls"},
        timeout=5,
    )
    assert r_reclean.status_code == 200
    assert r_reclean.json()["report"]["cleaned_missing_cells"] >= 1

    # 5. Export CSV, XLSX, SQLite
    for fmt in ("csv", "xlsx", "sqlite"):
        r_exp = requests.get(f"{base_url}/api/dataset/{session_id}/export?format={fmt}", timeout=5)
        assert r_exp.status_code == 200
        assert len(r_exp.content) > 0


def test_sample_endpoint(base_url):
    r_list = requests.get(f"{base_url}/api/samples", timeout=5)
    assert r_list.status_code == 200
    samples = r_list.json()["samples"]
    assert len(samples) == 3

    r_load = requests.post(
        f"{base_url}/api/samples/hr_employees",
        json={"strategy": "smart"},
        timeout=5,
    )
    assert r_load.status_code == 200
    data = r_load.json()
    assert data["table_name"] == "hr_employees_dirty"
    assert data["report"]["duplicates_removed"] == 1


def test_dashboard_creation_via_prompt_and_api(base_url):
    r_load = requests.post(
        f"{base_url}/api/samples/retail_sales",
        json={"strategy": "smart"},
        timeout=5,
    )
    assert r_load.status_code == 200
    session_id = r_load.json()["session_id"]

    # 1. Prompt in chat: "create dashboard"
    r_chat = requests.post(
        f"{base_url}/api/chat",
        json={"session_id": session_id, "message": "create a sales dashboard"},
        timeout=5,
    )
    assert r_chat.status_code == 200
    body = r_chat.json()
    assert body["type"] == "dashboard"
    dash = body["dashboard"]
    assert len(dash["kpis"]) >= 3
    assert len(dash["charts"]) >= 3
    assert len(dash["top_table"]["rows"]) > 0

    # 2. Direct dashboard API with filter
    r_filtered = requests.post(
        f"{base_url}/api/dashboard",
        json={
            "session_id": session_id,
            "prompt": "dashboard",
            "filter_col": "region",
            "filter_val": "North",
        },
        timeout=5,
    )
    assert r_filtered.status_code == 200
    fdash = r_filtered.json()
    assert fdash["kpis"][0]["value"] == 3
    assert fdash["active_filter"]["value"] == "North"


def test_ai_config_endpoints(base_url):
    r_get = requests.get(f"{base_url}/api/ai/config", timeout=5)
    assert r_get.status_code == 200
    cfg0 = r_get.json()
    assert "groq_models" in cfg0
    assert "gemini_models" in cfg0

    r_post = requests.post(
        f"{base_url}/api/ai/config",
        json={
            "default_provider": "groq",
            "groq_api_key": "gsk_demo_abcdef1234",
            "gemini_api_key": "AIza_demo_xyz9876",
            "persist_env": False,
        },
        timeout=5,
    )
    assert r_post.status_code == 200
    cfg1 = r_post.json()
    assert cfg1["default_provider"] == "groq"
    assert cfg1["groq_configured"] is True
    assert cfg1["gemini_configured"] is True
    assert cfg1["groq_key_masked"].startswith("gsk_de")
    assert cfg1["gemini_key_masked"].startswith("AIza_d")

    # Reset back cleanly
    requests.post(
        f"{base_url}/api/ai/config",
        json={
            "default_provider": "auto",
            "clear_groq": True,
            "clear_gemini": True,
            "persist_env": False,
        },
        timeout=5,
    )


def test_paste_dataset_from_text_and_assistant_endpoint(base_url):
    csv_text = (
        "Product,Category,Price ($),Stock\n"
        '  Laptop ,Electronics,"$1,200.00",10\n'
        '  Laptop ,Electronics,"$1,200.00",10\n'
        "Desk Chair,Furniture,$250.50,15\n"
    )
    r_paste = requests.post(
        f"{base_url}/api/dataset/from-text",
        json={
            "name": "inventory_paste",
            "format": "csv",
            "text": csv_text,
            "options": {"strategy": "smart"},
        },
        timeout=10,
    )
    assert r_paste.status_code == 200
    ds = r_paste.json()
    sid = ds["session_id"]
    assert ds["report"]["duplicates_removed"] == 1
    assert ds["report"]["cleaned_rows"] == 2

    # Query the pasted dataset via /api/assistant/chat
    r_q = requests.post(
        f"{base_url}/api/assistant/chat",
        json={
            "session_id": sid,
            "message": "Total price by category",
            "mode": "dataset",
        },
        timeout=10,
    )
    assert r_q.status_code == 200
    q_data = r_q.json()
    assert q_data["result"]["ok"] is True
    assert len(q_data["result"]["rows"]) == 2


def test_voice_transcribe_endpoint_validation(base_url):
    # Empty file or unconfigured key returns structured 400 error JSON
    r = requests.post(
        f"{base_url}/api/voice/transcribe",
        files={"audio": ("voice.webm", b"fake-audio-bytes", "audio/webm")},
        timeout=5,
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert "error" in body


def test_reclean_with_additional_user_cleaning_rules(base_url):
    r_sample = requests.post(
        f"{base_url}/api/samples/retail_sales",
        json={"strategy": "smart"},
        timeout=5,
    )
    assert r_sample.status_code == 200
    sample_body = r_sample.json()
    session_id = sample_body["session_id"]
    cols = sample_body["cleaned_preview"]["columns"]
    col_to_drop = next(c for c in cols if c != "region")

    r_reclean = requests.post(
        f"{base_url}/api/dataset/{session_id}/reclean",
        json={
            "strategy": "smart",
            "text_case": "upper",
            "round_decimals": 0,
            "drop_columns": [col_to_drop],
            "find_text": "NORTH",
            "replace_text": "NORTH_ZONE",
            "replace_column": "region",
        },
        timeout=5,
    )
    assert r_reclean.status_code == 200
    body = r_reclean.json()
    assert col_to_drop not in body["cleaned_preview"]["columns"]
    regions = [
        row["region"] for row in body["cleaned_preview"]["rows"] if row.get("region")
    ]
    assert "NORTH_ZONE" in regions

