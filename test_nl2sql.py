"""Tests for NL-to-SQL translation, chatbot orchestration, and SQL security."""

from app.chatbot import handle_chat_message
from app.db_engine import SessionManager, execute_sql
from app.samples import load_sample_dataframe


def _make_sales_session():
    mgr = SessionManager()
    filename, raw_df = load_sample_dataframe("retail_sales")
    return mgr.create_session(filename, raw_df)


def test_nl_aggregations_and_groupby():
    session = _make_sales_session()

    res_count = handle_chat_message(session, "How many rows are in the dataset?")
    assert res_count["result"]["ok"] is True
    assert res_count["result"]["rows"][0]["total_count"] == 12

    res_sum = handle_chat_message(session, "Total revenue by region")
    assert res_sum["result"]["ok"] is True
    assert "GROUP BY" in res_sum["sql"].upper()
    assert len(res_sum["result"]["rows"]) >= 4
    assert res_sum["chart"]["type"] == "bar"

    res_top = handle_chat_message(session, "Top 3 products by revenue")
    assert res_top["result"]["ok"] is True
    assert len(res_top["result"]["rows"]) == 3


def test_nl_implicit_categorical_and_numeric_filters():
    session = _make_sales_session()

    res_north = handle_chat_message(session, "Total revenue in North")
    assert res_north["result"]["ok"] is True
    assert "north" in res_north["sql"].lower()
    # North orders: 2400 + 420.5 + 2100 = 4920.5
    val = list(res_north["result"]["rows"][0].values())[0]
    assert round(float(val), 2) == 4920.5

    res_gt = handle_chat_message(session, "Show rows where revenue > 1500")
    assert res_gt["result"]["ok"] is True
    assert all(r["revenue"] > 1500 for r in res_gt["result"]["rows"])


def test_monthly_trend_query():
    session = _make_sales_session()
    res = handle_chat_message(session, "Monthly revenue")
    assert res["result"]["ok"] is True
    assert res["chart"]["type"] == "line"
    assert len(res["result"]["rows"]) == 5


def test_read_only_sql_guardrail():
    session = _make_sales_session()

    for bad_sql in (
        "DROP TABLE messy_retail_sales;",
        "DELETE FROM messy_retail_sales;",
        "UPDATE messy_retail_sales SET revenue = 0;",
        "SELECT * FROM messy_retail_sales; DROP TABLE messy_retail_sales;",
    ):
        out = execute_sql(session, bad_sql)
        assert out["ok"] is False

    good = execute_sql(session, 'SELECT region, COUNT(*) AS cnt FROM "messy_retail_sales" GROUP BY region;')
    assert good["ok"] is True
    assert good["row_count"] >= 4


def test_groq_and_gemini_nl2sql_routing(monkeypatch):
    from app.nl2sql import translate_nl_to_sql

    session = _make_sales_session()

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_post(url, **kwargs):
        if "api.groq.com" in url:
            return FakeResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": '```sql\nSELECT "category", ROUND(SUM("revenue"), 2) AS total_rev FROM "messy_retail_sales" GROUP BY "category";\n```'
                            }
                        }
                    ]
                },
            )
        if "generativelanguage.googleapis.com" in url:
            return FakeResponse(
                200,
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": '```sql\nSELECT COUNT(*) AS cnt FROM "messy_retail_sales";\n```'
                                    }
                                ]
                            }
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("app.nl2sql.requests.post", fake_post)

    res_groq = translate_nl_to_sql(
        "Revenue by category",
        session,
        provider="groq",
        groq_api_key="gsk_test_1234567890",
    )
    assert res_groq.engine.startswith("groq:")
    assert "GROUP BY" in res_groq.sql

    res_gemini = translate_nl_to_sql(
        "Count rows",
        session,
        provider="gemini",
        gemini_api_key="AIza_test_1234567890",
    )
    assert res_gemini.engine.startswith("gemini:")
    assert "COUNT(*)" in res_gemini.sql

    # If LLM returns invalid column SQL, auto-fallback to local engine
    def fake_bad_post(url, **kwargs):
        return FakeResponse(
            200,
            {"choices": [{"message": {"content": '```sql\nSELECT nonexistent_col FROM "messy_retail_sales";\n```'}}]},
        )

    monkeypatch.setattr("app.nl2sql.requests.post", fake_bad_post)
    res_fb = translate_nl_to_sql(
        "Total revenue by region",
        session,
        provider="groq",
        groq_api_key="gsk_test_1234567890",
    )
    assert res_fb.engine == "local"
    assert '"region"' in res_fb.sql


def test_assistant_gemini_google_grounding_and_groq_web_synthesis(monkeypatch):
    from app.assistant import handle_assistant_message

    class FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_gemini_post(url, **kwargs):
        assert "generativelanguage.googleapis.com" in url
        assert kwargs["json"].get("tools") == [{"google_search": {}}]
        return FakeResp(
            200,
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Google Gemini live answer from web grounding."}]},
                        "groundingMetadata": {
                            "groundingChunks": [
                                {"web": {"title": "Example Source", "uri": "https://example.com/news"}}
                            ]
                        },
                    }
                ]
            },
        )

    monkeypatch.setattr("app.assistant.requests.post", fake_gemini_post)
    res_gem = handle_assistant_message(
        message="Search Google for Python 3.13 release",
        mode="web",
        provider="gemini",
        gemini_api_key="AIza_test_key_123456",
        history=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}],
    )
    assert res_gem["type"] == "ai_answer"
    assert res_gem["engine"].startswith("gemini:")
    assert "Google Gemini live answer" in res_gem["reply"]
    assert res_gem["sources"][0]["url"] == "https://example.com/news"

    # Mock live web fetch + Groq synthesis
    monkeypatch.setattr(
        "app.assistant.search_google_and_web",
        lambda q, max_results=5: [
            {"title": "Live News", "url": "https://news.example.com", "snippet": "Latest headline.", "source": "Google News"}
        ],
    )

    def fake_groq_post(url, **kwargs):
        assert "api.groq.com" in url
        return FakeResp(
            200,
            {"choices": [{"message": {"content": "Groq synthesized answer from Google News."}}]},
        )

    monkeypatch.setattr("app.assistant.requests.post", fake_groq_post)
    res_groq = handle_assistant_message(
        message="Latest news about AI",
        mode="web",
        provider="groq",
        groq_api_key="gsk_test_key_123456",
    )
    assert res_groq["type"] == "ai_answer"
    assert res_groq["engine"].startswith("groq:")
    assert "Groq synthesized answer" in res_groq["reply"]
    assert res_groq["sources"][0]["source"] == "Google News"


def test_voice_transcription_groq_and_gemini(monkeypatch):
    from app.voice import transcribe_audio_bytes

    class FakeResp:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    def fake_groq_audio(url, **kwargs):
        assert "audio/transcriptions" in url
        return FakeResp(200, {"text": "Show total revenue by region"})

    monkeypatch.setattr("app.voice.requests.post", fake_groq_audio)
    res_groq = transcribe_audio_bytes(
        audio_bytes=b"1234",
        provider="groq",
        groq_api_key="gsk_voice_test_1234",
    )
    assert res_groq["ok"] is True
    assert res_groq["text"] == "Show total revenue by region"
    assert res_groq["engine"].startswith("groq:")

    def fake_gemini_audio(url, **kwargs):
        assert "generativelanguage.googleapis.com" in url
        return FakeResp(
            200,
            {"candidates": [{"content": {"parts": [{"text": "Create analytics dashboard"}]}}]},
        )

    monkeypatch.setattr("app.voice.requests.post", fake_gemini_audio)
    res_gem = transcribe_audio_bytes(
        audio_bytes=b"1234",
        provider="gemini",
        gemini_api_key="AIza_voice_test_1234",
    )
    assert res_gem["ok"] is True
    assert res_gem["text"] == "Create analytics dashboard"
    assert res_gem["engine"].startswith("gemini:")


def test_google_current_data_formatter():
    from app.web_search import clean_search_query, format_google_results_markdown

    assert clean_search_query("fetch current data from google about Python 3.13") == "Python 3.13"
    assert clean_search_query("get the latest news on AI") == "AI"

    sample_results = [
        {
            "title": "Python 3.13 Released",
            "snippet": "Includes experimental free-threaded build and improved REPL.",
            "url": "https://example.com/py313",
            "source": "Python Blog",
            "published": "2026-11-12 09:00 UTC",
        },
        {
            "title": "AI Benchmarks Update",
            "snippet": "Reported by Google News",
            "url": "https://news.google.com/example",
            "source": "TechWire",
            "published": "2026-11-12 10:00 UTC",
        },
    ]
    md = format_google_results_markdown("fetch current data from google about Python 3.13", sample_results)
    assert "### Current Google & Web Data: `Python 3.13`" in md
    assert "#### Key Highlights" in md
    assert "| # | Topic / Headline | Source | Updated |" in md
    assert "| 1 | Python 3.13 Released | Python Blog | 2026-11-12 09:00 UTC |" in md
    assert "Reported by" not in md  # avoids duplicate filler snippet

    # Direct factual question returns a concise 1-line answer
    pm_results = [
        {
            "title": "Prime Minister of India",
            "snippet": "The prime minister of India is the head of government.",
            "url": "https://en.wikipedia.org/wiki/Prime_Minister_of_India",
            "source": "Wikipedia",
            "kind": "fact",
            "infobox": {"incumbent": "Narendra Modi"},
        }
    ]
    pm_reply = format_google_results_markdown(
        "tell me name of current prime minister of india", pm_results
    )
    assert pm_reply == "The current Prime Minister of India is **Narendra Modi**."


def test_feature1_general_mode_ignores_attached_dataset():
    from unittest.mock import MagicMock, patch
    from app.assistant import handle_assistant_message

    session = _make_sales_session()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Python was created by Guido van Rossum."}}]
    }

    with patch("app.assistant.requests.post", return_value=mock_resp) as post_mock:
        res = handle_assistant_message(
            "Who created Python?",
            session=session,
            provider="groq",
            groq_api_key="gsk-test-123",
            mode="general",
        )

    assert post_mock.called
    assert res["type"] == "ai_answer"
    assert res["engine"].startswith("groq")
    assert "Guido van Rossum" in res["reply"]
    assert "sql" not in res


def test_feature5_additional_user_cleaning_rules():
    import pandas as pd
    from app.cleaner import CleaningOptions, clean_dataset

    df = pd.DataFrame(
        {
            "Customer Name": ["alice smith", "BOB JONES"],
            "City": ["N/A", "nyc"],
            "Price": ["12.3456", "99.9876"],
            "Notes": ["temp", "drop me"],
        }
    )
    opts = CleaningOptions(
        text_case="title",
        fill_text_value="Not Provided",
        round_decimals=1,
        drop_columns=["notes"],
        find_text="Nyc",
        replace_text="New York",
        replace_column="city",
    )
    cleaned, report = clean_dataset(df, opts)
    assert "notes" not in cleaned.columns
    assert cleaned["customer_name"].tolist() == ["Alice Smith", "Bob Jones"]
    assert "Not Provided" in cleaned["city"].tolist()
    assert "New York" in cleaned["city"].tolist()
    assert cleaned["price"].tolist() == [12.3, 100.0]
    assert any(a["step"].startswith("user_") for a in report.actions)


def test_topic_card_with_description_and_image():
    from unittest.mock import MagicMock, patch
    from app.web_search import fetch_topic_card

    mock_wiki = MagicMock()
    mock_wiki.status_code = 200
    mock_wiki.json.return_value = {
        "type": "standard",
        "title": "Narendra Modi",
        "description": "Prime Minister of India since 2014",
        "extract": "Narendra Damodardas Modi is an Indian politician serving as the prime minister of India since May 2014.",
        "thumbnail": {"source": "https://upload.wikimedia.org/example/modi.jpg"},
        "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Narendra_Modi"}},
    }
    pm_results = [
        {
            "title": "Prime Minister of India",
            "snippet": "The prime minister of India is the head of government.",
            "url": "https://en.wikipedia.org/wiki/Prime_Minister_of_India",
            "source": "Wikipedia",
            "kind": "fact",
            "infobox": {"incumbent": "Narendra Modi"},
        }
    ]
    with patch("app.web_search.requests.get", return_value=mock_wiki) as get_mock:
        card = fetch_topic_card(
            "who is the current prime minister of india",
            results=pm_results,
            reply="The current Prime Minister of India is Narendra Modi.",
        )

    assert get_mock.called
    assert "Narendra_Modi" in get_mock.call_args[0][0]
    assert card is not None
    assert card["title"] == "Narendra Modi"
    assert "Prime Minister of India" in card["subtitle"]
    assert "Narendra Damodardas Modi" in card["description"]
    assert card["image_url"] == "https://upload.wikimedia.org/example/modi.jpg"
    assert fetch_topic_card("hello") is None

    # Regression test: typo "Current prime minster of india" resolves cleanly without news table
    from app.web_search import extract_direct_answer, format_google_results_markdown

    assert (
        extract_direct_answer("Current prime minster of india", pm_results)
        == "The current Prime Minister of India is **Narendra Modi**."
    )
    taj_results = [
        {
            "title": "Taj Mahal",
            "snippet": "The Taj Mahal is an ivory-white marble mausoleum in Agra, India. It was commissioned in 1631 by Shah Jahan.",
            "url": "https://en.wikipedia.org/wiki/Taj_Mahal",
            "source": "Wikipedia",
            "kind": "fact",
        },
        {
            "title": "Photo Gallery",
            "snippet": "Reported by News",
            "url": "https://news.example.com/1",
            "source": "News",
            "kind": "news",
        },
    ]
    taj_md = format_google_results_markdown("what is Taj Mahal", taj_results)
    assert "ivory-white marble mausoleum" in taj_md
    assert "Current Google & Web Data" not in taj_md



