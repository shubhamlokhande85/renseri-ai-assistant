"""Live Google, Wikipedia & Web current-data fetcher and formatter for SL AI Assistant."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import parse_qs, quote, quote_plus, unquote, urlparse

import requests


HEADERS = {
    "User-Agent": "SL-AI-Assistant/1.0 (https://localhost)"
}

QUERY_PREFIX_RE = re.compile(
    r"^(?:"
    r"(?:please\s+)?(?:fetch|get|find|give\s+me|show\s+me|tell\s+me|search|look\s+up|check)\s+"
    r"(?:the\s+)?(?:name\s+of\s+)?(?:the\s+)?(?:current|live|latest|recent|real[-\s]?time|today'?s)?\s*"
    r"(?:data|info|information|news|updates?|results?|facts?)?\s*"
    r"(?:from\s+(?:the\s+)?(?:google|web|internet)|on\s+google)?\s*(?:for|about|on|regarding|of)?|"
    r"(?:who\s+is|who's|what\s+is|what's|name)\s+(?:the\s+)?(?:current|present)?|"
    r"(?:search\s+)?google\s+(?:for|about|on)?|"
    r"on\s+google\s+"
    r")\s*",
    re.IGNORECASE,
)

TOPIC_ONLY_PREFIX_RE = re.compile(
    r"^(?:the\s+)?(?:current|present|latest|name\s+of|who\s+is|what\s+is|tell\s+me)\s+",
    re.IGNORECASE,
)

WEATHER_QUERY_RE = re.compile(
    r"\b(?:weather|temperature|forecast|climate|rain)\b(?:\s+(?:in|at|for|of)\s+([a-zA-Z\s,.-]{2,40}))?",
    re.IGNORECASE,
)

LIST_OR_NEWS_RE = re.compile(
    r"\b(?:news|headlines|latest\s+updates?|top\s+\d+|list|table|compare|articles?|stories|breaking)\b",
    re.IGNORECASE,
)

CONCISE_FACT_RE = re.compile(
    r"\b(?:name\s+of|capital\s+of|currency\s+of|founder\s+of|ceo\s+of|"
    r"current\s+(?:prime\s+minister|president|ceo|chief\s+minister|governor|chancellor|king|queen|mayor|vice\s+president)|"
    r"weather\s+(?:in|at|for)|temperature\s+(?:in|at|for))\b",
    re.IGNORECASE,
)

TYPO_CORRECTIONS: tuple[tuple[str, str], ...] = (
    (r"\bminsters?\b", "minister"),
    (r"\bpresdients?\b", "president"),
    (r"\bpresedents?\b", "president"),
    (r"\bprimeminister\b", "prime minister"),
    (r"\bcaptial\b", "capital"),
    (r"\bgoverner\b", "governor"),
    (r"\bcurency\b", "currency"),
    (r"\bleanring\b", "learning"),
    (r"\blaerning\b", "learning"),
    (r"\bintellgience\b", "intelligence"),
    (r"\binteligence\b", "intelligence"),
    (r"\balgortihm\b", "algorithm"),
)


def _normalize_query_text(text: str) -> str:
    """Fix common spelling slips in entity/factual queries before web lookup."""
    out = (text or "").strip()
    for pat, repl in TYPO_CORRECTIONS:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return out


def _strip_tags(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text or "")
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _format_pub_date(raw_date: str) -> str:
    if not raw_date:
        return ""
    try:
        dt = parsedate_to_datetime(raw_date)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return raw_date.strip()


def clean_search_query(query: str) -> str:
    """Strip conversational wrapper phrases while keeping core search terms."""
    cleaned = _normalize_query_text(query)
    for _ in range(3):
        next_q = QUERY_PREFIX_RE.sub("", cleaned).strip(" ?!.,:")
        if next_q and next_q != cleaned:
            cleaned = next_q
        else:
            break
    return cleaned or _normalize_query_text(query)


def _extract_topic_query(query: str) -> str:
    topic = clean_search_query(query)
    for _ in range(2):
        nxt = TOPIC_ONLY_PREFIX_RE.sub("", topic).strip(" ?!.,:")
        if nxt and nxt != topic:
            topic = nxt
        else:
            break
    return topic or clean_search_query(query)


def resolve_wiki_topic(topic: str, timeout: int = 4) -> str:
    """Resolve topic names using Wikipedia OpenSearch / spell-correction suggestions."""
    clean = _extract_topic_query(topic).strip(" ?.,!:")
    if not clean:
        return topic
    # 1. OpenSearch (fast fuzzy prefix / exact title match)
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": clean,
                "limit": 3,
                "format": "json",
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if r.status_code == 200:
            titles = r.json()[1]
            if titles:
                return titles[0]
    except Exception:
        pass

    # 2. list=search suggestion
    try:
        r = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": clean,
                "format": "json",
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if r.status_code == 200:
            sugg = r.json().get("query", {}).get("searchinfo", {}).get("suggestion")
            if sugg:
                return sugg
            hits = r.json().get("query", {}).get("search", [])
            if hits:
                return hits[0].get("title")
    except Exception:
        pass
    return clean


def _extract_ddg_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        uddg = parse_qs(parsed.query).get("uddg")
        if uddg:
            return unquote(uddg[0])
    return href


def _clean_wikitext_value(raw: str) -> str:
    """Convert Wikipedia infobox wikitext fragments into readable plain text."""
    text = re.sub(r"<!--.*?-->", "", raw or "", flags=re.DOTALL)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<ref[^>]*/>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", ", ", text, flags=re.IGNORECASE)
    # Remove {{efn|...}} footnotes
    text = re.sub(r"\{\{(?:efn|sfn|cite)[^}]*\}\}", "", text, flags=re.IGNORECASE)
    # Convert [[Target|Display]] -> Display, [[Target]] -> Target
    text = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # Unwrap list templates like {{Ubl|a|b}} / {{plainlist|* a * b}}
    text = re.sub(r"\{\{(?:Ubl|Unbulleted list|plainlist|ubl|flatlist)\s*\|?", "", text, flags=re.IGNORECASE)
    text = text.replace("}}", "")
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = text.replace("|", ", ")
    text = re.sub(r"\s*,\s*,+", ", ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,*;")
    return text


def _parse_infobox_fields(wikitext: str) -> dict[str, str]:
    """Extract key structured fields from section-0 Wikipedia infobox wikitext."""
    fields: dict[str, str] = {}
    if not wikitext:
        return fields

    target_keys = (
        "incumbent",
        "officeholder",
        "capital",
        "currency",
        "ceo",
        "key_people",
        "founder",
        "founders",
        "leader_name1",
        "leader_title1",
        "leader_name2",
        "leader_title2",
        "population_estimate",
    )
    lines = wikitext.splitlines()
    idx = 0
    while idx < len(lines):
        m = re.match(r"^\s*\|\s*([a-zA-Z0-9_]+)\s*=\s*(.*)$", lines[idx])
        if m:
            key = m.group(1).lower()
            val_parts = [m.group(2)]
            idx += 1
            while idx < len(lines) and not re.match(r"^\s*[|}]", lines[idx]):
                val_parts.append(lines[idx])
                idx += 1
            if key in target_keys:
                cleaned = _clean_wikitext_value(" ".join(val_parts))
                if cleaned:
                    fields[key] = cleaned
            continue
        idx += 1
    return fields


def fetch_google_news_rss(query: str, timeout: int = 8) -> list[dict[str, str]]:
    """Fetch current articles and timestamps from Google News RSS."""
    results: list[dict[str, str]] = []
    try:
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        if resp.status_code != 200:
            return results
        root = ET.fromstring(resp.content)
        for item in root.findall("./channel/item")[:6]:
            raw_title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = _format_pub_date(item.findtext("pubDate") or "")
            source_el = item.find("source")
            source_name = (
                source_el.text.strip()
                if source_el is not None and source_el.text
                else "Google News"
            )
            title = raw_title
            if source_name and raw_title.endswith(f" - {source_name}"):
                title = raw_title[: -(len(source_name) + 3)].strip()

            desc_raw = _strip_tags(item.findtext("description") or "")
            if desc_raw.lower().startswith(title.lower()[:30]):
                snippet = ""
            else:
                snippet = desc_raw[:220]

            if title and link:
                results.append(
                    {
                        "title": title,
                        "snippet": snippet or f"Reported by {source_name}" + (f" on {pub_date}" if pub_date else ""),
                        "url": link,
                        "source": source_name,
                        "published": pub_date or "Latest",
                        "kind": "news",
                    }
                )
    except Exception:
        pass
    return results


def fetch_duckduckgo_instant(query: str, timeout: int = 7) -> list[dict[str, str]]:
    """Fetch structured instant-answer facts from DuckDuckGo JSON API."""
    results: list[dict[str, str]] = []
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return results
        data = resp.json()
        if data.get("Answer"):
            results.append(
                {
                    "title": data.get("Heading") or query,
                    "snippet": str(data["Answer"]).strip(),
                    "url": data.get("AbstractURL") or "https://duckduckgo.com/",
                    "source": "Instant Answer",
                    "published": "Live Fact",
                    "kind": "fact",
                }
            )
        if data.get("AbstractText"):
            results.append(
                {
                    "title": data.get("Heading") or query,
                    "snippet": data["AbstractText"],
                    "url": data.get("AbstractURL") or "https://duckduckgo.com/",
                    "source": data.get("AbstractSource") or "Web Knowledge",
                    "published": "Reference",
                    "kind": "fact",
                }
            )
    except Exception:
        pass
    return results


def fetch_duckduckgo_web(query: str, timeout: int = 8) -> list[dict[str, str]]:
    """Fetch organic live web search results via lightweight DuckDuckGo HTML endpoint."""
    results: list[dict[str, str]] = []
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=HEADERS,
            timeout=timeout,
        )
        if resp.status_code != 200:
            return results
        blocks = re.findall(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'(?:<a[^>]+class="result__snippet"[^>]*>(.*?)</a>|<div[^>]+class="result__snippet"[^>]*>(.*?)</div>)',
            resp.text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        for href, raw_title, snip1, snip2 in blocks[:5]:
            url = _extract_ddg_url(html.unescape(href))
            title = _strip_tags(raw_title)
            snippet = _strip_tags(snip1 or snip2)
            domain = urlparse(url).netloc.replace("www.", "") if url else "Web"
            if title and url.startswith("http"):
                results.append(
                    {
                        "title": title,
                        "snippet": snippet or title,
                        "url": url,
                        "source": domain or "Web",
                        "published": "Live Web",
                        "kind": "web",
                    }
                )
    except Exception:
        pass
    return results


def fetch_wikipedia_facts(query: str, timeout: int = 8) -> list[dict[str, Any]]:
    """Fetch Wikipedia intro extract + structured infobox fields (incumbent, capital, CEO, etc.)."""
    topic = _extract_topic_query(query)
    if not topic:
        return []

    def _query_wiki(search_term: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": search_term,
                    "gsrlimit": 2,
                    "prop": "extracts|revisions",
                    "exintro": 1,
                    "explaintext": 1,
                    "rvprop": "content",
                    "rvsection": 0,
                    "format": "json",
                },
                headers=HEADERS,
                timeout=timeout,
            )
            if resp.status_code != 200:
                return items
            pages_dict = resp.json().get("query", {}).get("pages", {})
            pages = sorted(pages_dict.values(), key=lambda p: p.get("index", 99))
            for page in pages:
                title = page.get("title", "")
                raw_extract = page.get("extract") or ""
                paras = [
                    re.sub(r"[ \t]+", " ", p).strip()
                    for p in raw_extract.split("\n")
                    if p.strip()
                ]
                extract = "\n\n".join(paras).strip()
                rev_list = page.get("revisions") or []
                wikitext = rev_list[0].get("*", "") if rev_list and isinstance(rev_list[0], dict) else ""
                infobox = _parse_infobox_fields(wikitext)
                if title and (extract or infobox):
                    items.append(
                        {
                            "title": title,
                            "snippet": extract or title,
                            "url": f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
                            "source": "Wikipedia",
                            "published": "Reference",
                            "kind": "fact",
                            "infobox": infobox,
                        }
                    )
        except Exception:
            pass
        return items

    results = _query_wiki(topic)
    if not results:
        resolved = resolve_wiki_topic(topic, timeout=min(timeout, 4))
        if resolved and resolved.lower() != topic.lower():
            results = _query_wiki(resolved)

    return results


def fetch_wikipedia_summary(query: str, timeout: int = 7) -> list[dict[str, str]]:
    """Backward-compatible wrapper returning clean Wikipedia summaries."""
    return [
        {k: str(v) for k, v in item.items() if k != "infobox"}
        for item in fetch_wikipedia_facts(query, timeout=timeout)
    ]


def fetch_live_weather(query: str, timeout: int = 7) -> list[dict[str, Any]]:
    """Fetch live temperature & conditions from Open-Meteo when user asks for weather."""
    m = WEATHER_QUERY_RE.search(query or "")
    if not m:
        return []
    city = (m.group(1) or "").strip(" ?!.,:")
    if not city:
        return []
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            headers=HEADERS,
            timeout=timeout,
        )
        if geo.status_code != 200:
            return []
        places = geo.json().get("results") or []
        if not places:
            return []
        place = places[0]
        lat, lon = place["latitude"], place["longitude"]
        label = ", ".join(p for p in (place.get("name"), place.get("country")) if p)
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,apparent_temperature",
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if w.status_code != 200:
            return []
        cur = w.json().get("current") or {}
        temp = cur.get("temperature_2m")
        feels = cur.get("apparent_temperature")
        hum = cur.get("relative_humidity_2m")
        wind = cur.get("wind_speed_10m")
        if temp is None:
            return []
        snippet = (
            f"The current weather in **{label}** is **{temp}°C** "
            f"(feels like {feels}°C, humidity {hum}%, wind {wind} km/h)."
        )
        return [
            {
                "title": f"Live Weather in {label}",
                "snippet": snippet,
                "url": f"https://open-meteo.com/en/docs#latitude={lat}&longitude={lon}",
                "source": "Open-Meteo Live",
                "published": str(cur.get("time") or "Current"),
                "kind": "weather",
                "direct_answer": snippet,
            }
        ]
    except Exception:
        return []


def search_google_and_web(query: str, max_results: int = 6) -> list[dict[str, Any]]:
    """Aggregate live weather, Wikipedia facts, instant answers, web & Google News in parallel."""
    norm_q = _normalize_query_text(query)
    clean_q = clean_search_query(norm_q)
    if not clean_q:
        return []

    wants_news = bool(LIST_OR_NEWS_RE.search(norm_q)) or "current data from google" in norm_q.lower()
    fetchers = (
        [
            fetch_live_weather,
            fetch_google_news_rss,
            fetch_wikipedia_facts,
            fetch_duckduckgo_web,
            fetch_duckduckgo_instant,
        ]
        if wants_news
        else [
            fetch_live_weather,
            fetch_wikipedia_facts,
            fetch_duckduckgo_instant,
            fetch_duckduckgo_web,
            fetch_google_news_rss,
        ]
    )

    topic_q = _extract_topic_query(norm_q)
    buckets: list[list[dict[str, Any]]] = []
    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = [
            pool.submit(fn, topic_q if fn in (fetch_wikipedia_facts, fetch_duckduckgo_instant) else clean_q)
            for fn in fetchers
        ]
        for fut in futures:
            try:
                buckets.append(fut.result(timeout=9))
            except Exception:
                buckets.append([])

    combined: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()

    for items in buckets:
        for item in items:
            url = str(item.get("url", "")).strip()
            title_key = re.sub(r"\W+", " ", str(item.get("title", "")).lower()).strip()
            if not url or url in seen_urls or (title_key and title_key in seen_titles):
                continue
            seen_urls.add(url)
            if title_key:
                seen_titles.add(title_key)
            combined.append(item)
            if len(combined) >= max_results:
                return combined

    return combined


def extract_direct_answer(query: str, results: list[dict[str, Any]]) -> str | None:
    """Synthesize a crisp 1-line factual answer when the user asks a direct question."""
    if not results or LIST_OR_NEWS_RE.search(query or ""):
        return None

    q_lower = _normalize_query_text(query).lower()

    # 1. Weather direct answer
    for r in results:
        if r.get("direct_answer"):
            return str(r["direct_answer"])

    # 2. Structured Wikipedia Infobox answers (PM, President, CEO, Capital, Currency, Founder)
    for r in results:
        infobox = r.get("infobox") or {}
        title = str(r.get("title") or "").strip()
        if not infobox:
            continue

        if infobox.get("incumbent") and any(
            kw in q_lower for kw in ("prime minister", "president", "chief minister", "governor", "chancellor", "mayor", "who is", "name", "current")
        ):
            person = infobox["incumbent"].split(",")[0].strip()
            if person:
                return f"The current {title} is **{person}**."

        if "capital" in q_lower and infobox.get("capital"):
            cap = re.sub(r"\s*\([^)]*\)", "", infobox["capital"].split(",")[0]).strip()
            if cap:
                return f"The capital of {title} is **{cap}**."

        if "currency" in q_lower and infobox.get("currency"):
            cur = infobox["currency"].split(",")[0].strip()
            if cur:
                return f"The currency of {title} is **{cur}**."

        if "ceo" in q_lower:
            raw_people = infobox.get("ceo") or infobox.get("key_people") or ""
            m_ceo = re.search(r"([A-Z][a-zA-Z.\s-]{2,40}?)\s*\([^)]*CEO[^)]*\)", raw_people)
            if m_ceo:
                return f"The CEO of {title} is **{m_ceo.group(1).strip()}**."
            if infobox.get("ceo"):
                return f"The CEO of {title} is **{infobox['ceo'].split(',')[0].strip()}**."

        if "founder" in q_lower and (infobox.get("founder") or infobox.get("founders")):
            fnd = infobox.get("founder") or infobox.get("founders") or ""
            return f"The founder(s) of {title}: **{fnd}**."

    # 3. Direct question snippet from Wikipedia / Instant Answer
    if CONCISE_FACT_RE.search(q_lower):
        for r in results:
            if r.get("kind") == "fact" and r.get("snippet"):
                first_sent = re.split(r"(?<=[.!?])\s+", str(r["snippet"]).strip())[0]
                if first_sent:
                    return first_sent

    return None


def strip_internal_result_fields(results: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Return clean source-chip dicts for frontend API responses."""
    cleaned: list[dict[str, str]] = []
    for r in results:
        if r.get("url") and r.get("title"):
            cleaned.append(
                {
                    "title": str(r["title"]),
                    "url": str(r["url"]),
                    "source": str(r.get("source") or "Web"),
                    "snippet": str(r.get("snippet") or ""),
                    "published": str(r.get("published") or ""),
                }
            )
    return cleaned


def format_google_results_markdown(
    query: str,
    results: list[dict[str, Any]],
    include_ai_tip: bool = False,
) -> str:
    """Format fetched Google/Web items: crisp ChatGPT-style answer for facts/topics, table only for news/lists."""
    if not results:
        return ""

    norm_q = _normalize_query_text(query)
    q_lower = norm_q.lower()
    direct = extract_direct_answer(norm_q, results)
    if direct:
        return direct

    wants_table = bool(LIST_OR_NEWS_RE.search(norm_q)) or "current data from google" in q_lower
    fact_items = [r for r in results if r.get("kind") == "fact" and r.get("snippet")]
    if not wants_table and not fact_items:
        resolved = resolve_wiki_topic(norm_q)
        if resolved:
            extra_facts = fetch_wikipedia_facts(resolved)
            if extra_facts:
                fact_items = extra_facts
    if not wants_table and fact_items:
        top = fact_items[0]
        raw_snippet = str(top.get("snippet") or "").strip()
        paragraphs = [p.strip() for p in raw_snippet.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in raw_snippet.split("\n") if p.strip()]

        lines: list[str] = []
        if paragraphs:
            lines.extend(paragraphs)
        elif raw_snippet:
            lines.append(raw_snippet)

        infobox = top.get("infobox") or {}
        if infobox:
            info_lines = []
            labels = [
                ("capital", "Capital"),
                ("currency", "Currency"),
                ("incumbent", "Leadership / Incumbent"),
                ("ceo", "CEO"),
                ("founder", "Founder(s)"),
                ("headquarters", "Headquarters"),
            ]
            for key, label in labels:
                if infobox.get(key):
                    clean_val = re.sub(r"\s*\([^)]*\)", "", str(infobox[key]).split(",")[0]).strip()
                    if clean_val:
                        info_lines.append(f"- **{label}**: {clean_val}")
            if info_lines:
                lines.append("")
                lines.append("#### Key Highlights")
                lines.extend(info_lines)

        links_lines = []
        seen_urls = set()
        if top.get("url"):
            seen_urls.add(top["url"])
            t_title = top.get("title") or "Wikipedia Overview"
            links_lines.append(f"- [{t_title} — Wikipedia]({top['url']})")

        for r in results:
            url = r.get("url")
            if url and url not in seen_urls and not str(url).startswith("https://news.google.com/rss/articles/"):
                seen_urls.add(url)
                r_title = r.get("title") or r.get("source") or "Web Source"
                links_lines.append(f"- [{r_title}]({url})")
            if len(links_lines) >= 4:
                break

        if links_lines:
            lines.append("")
            lines.append("### 🔗 Reference Links & Sources")
            lines.extend(links_lines)

        return "\n\n".join(lines).strip()

    clean_q = clean_search_query(norm_q)
    fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        f"### Current Google & Web Data: `{clean_q}`",
        f"> Fetched live at **{fetched_utc}** · **{len(results)}** verified result(s)",
        "",
        "#### Key Highlights",
    ]

    for idx, item in enumerate(results[:5], start=1):
        title = str(item.get("title", "")).replace("|", "-")
        source = str(item.get("source", "Web"))
        published = str(item.get("published", ""))
        snippet = str(item.get("snippet", ""))
        meta = f"{source}" + (f" · {published}" if published else "")
        if snippet and snippet.lower() != title.lower() and not snippet.lower().startswith("reported by"):
            lines.append(f"{idx}. **{title}** *({meta})* — {snippet}")
        else:
            lines.append(f"{idx}. **{title}** *({meta})*")

    lines.extend(
        [
            "",
            "| # | Topic / Headline | Source | Updated |",
            "| --- | --- | --- | --- |",
        ]
    )
    for idx, item in enumerate(results[:6], start=1):
        title = str(item.get("title") or "")[:90].replace("|", "/")
        source = str(item.get("source") or "Web").replace("|", "/")
        published = str(item.get("published") or "Current").replace("|", "/")
        lines.append(f"| {idx} | {title} | {source} | {published} |")

    if include_ai_tip:
        lines.extend(
            [
                "",
                "*Add a **Groq** or **Google Gemini** API key in **API Keys** for full AI synthesis & Google Search grounding.*",
            ]
        )

    return "\n".join(lines)


SKIP_TOPIC_CARD_RE = re.compile(
    r"\b(?:write\s+(?:a\s+)?(?:python|js|javascript|sql|code|script|function)|"
    r"explain\s+(?:sql|python|async|code)|group\s+by|select\s+\*|how\s+to\s+install|"
    r"dataset|csv|excel|upload|dashboard)\b",
    re.IGNORECASE,
)
GREETING_ONLY_RE = re.compile(r"^(?:hi|hello|hey|thanks|thank\s+you|help|ok|okay)[!.? ]*$", re.IGNORECASE)


def _trim_description(text: str, max_len: int = 420) -> str:
    clean = re.sub(r"\s+", " ", (text or "")).strip()
    if len(clean) <= max_len:
        return clean
    candidate = clean[:max_len]
    last_punct = max(candidate.rfind(". "), candidate.rfind("! "), candidate.rfind("? "))
    if last_punct > 120:
        return candidate[:last_punct + 1].strip()
    clipped = candidate.rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{clipped}..."


def _resolve_entity_candidates(
    query: str,
    results: list[dict[str, Any]] | None = None,
    reply: str = "",
) -> list[str]:
    """Infer ordered Wikipedia entity candidates from direct answers, infoboxes, and query."""
    candidates: list[str] = []
    norm_q = _normalize_query_text(query)
    q_lower = norm_q.lower()

    def _add(val: str) -> None:
        v = re.sub(r"\s+", " ", (val or "").strip(" *`\"'.,;:!?"))
        if v and len(v) >= 2 and v.lower() not in {c.lower() for c in candidates}:
            candidates.append(v)

    if results:
        direct = extract_direct_answer(norm_q, results) or ""
        m_bold = re.search(r"\*\*([^*]{2,60})\*\*", direct)
        if m_bold:
            _add(m_bold.group(1))
        for r in results:
            infobox = r.get("infobox") or {}
            if infobox.get("incumbent") and any(
                kw in q_lower for kw in ("prime minister", "president", "chief minister", "governor", "chancellor", "mayor", "who is", "name", "current")
            ):
                _add(infobox["incumbent"].split(",")[0])
            if "capital" in q_lower and infobox.get("capital"):
                _add(re.sub(r"\s*\([^)]*\)", "", infobox["capital"].split(",")[0]))

    if reply:
        first_line = reply.strip().splitlines()[0]
        m_bold_reply = re.search(r"\*\*([^*]{2,60})\*\*", first_line)
        if m_bold_reply:
            _add(m_bold_reply.group(1))
        m_is = re.search(
            r"\b(?:is|was|are|called)\s+(?:currently\s+|now\s+)?([A-Z][a-zA-Z0-9.'-]+(?:\s+(?:of|de|van|al|bin|the|[A-Z][a-zA-Z0-9.'-]+)){0,4})(?:\s*[.,!]|$)",
            first_line,
        )
        if m_is:
            _add(m_is.group(1))

    _add(_extract_topic_query(norm_q))
    resolved = resolve_wiki_topic(norm_q)
    if resolved:
        _add(resolved)
    return candidates[:4]


def _fetch_topic_gallery_images(topic: str, max_images: int = 4, timeout: int = 4) -> list[dict[str, str]]:
    """Fetch additional high-quality images from Wikimedia Commons for visual topic display."""
    images: list[dict[str, str]] = []
    clean_topic = _extract_topic_query(topic) or topic.strip()
    try:
        resp = requests.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": clean_topic,
                "gsrlimit": max_images + 2,
                "gsrnamespace": 6,
                "prop": "imageinfo",
                "iiprop": "url",
                "iiurlwidth": 640,
                "format": "json",
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if resp.status_code == 200:
            pages = resp.json().get("query", {}).get("pages", {})
            for pid, p in pages.items():
                info = (p.get("imageinfo") or [{}])[0]
                url = info.get("thumburl") or info.get("url")
                raw_t = (p.get("title") or "").replace("File:", "").split(".")[0].strip()
                if url and not url.lower().endswith(".pdf") and not url.lower().endswith(".tif"):
                    images.append({"url": url, "caption": raw_t[:60]})
                if len(images) >= max_images:
                    break
    except Exception:
        pass
    return images


def _fetch_wiki_page_summary(title: str, timeout: int = 4) -> dict[str, Any] | None:
    """Fetch Wikipedia summary description + thumbnail image for an entity/topic."""
    slug = quote(title.strip().replace(" ", "_"), safe="")
    if not slug:
        return None

    gallery = _fetch_topic_gallery_images(title, max_images=4, timeout=timeout)

    try:
        resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}",
            headers=HEADERS,
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("type") not in ("disambiguation", "no-extract") and data.get("extract"):
                thumb = (data.get("thumbnail") or data.get("originalimage") or {}).get("source", "")
                if not thumb and gallery:
                    thumb = gallery[0]["url"]
                return {
                    "title": str(data.get("title") or title),
                    "subtitle": str(data.get("description") or ""),
                    "description": _trim_description(str(data.get("extract") or "")),
                    "image_url": str(thumb or ""),
                    "images": gallery,
                    "url": str(
                        ((data.get("content_urls") or {}).get("desktop") or {}).get("page")
                        or f"https://en.wikipedia.org/wiki/{slug}"
                    ),
                    "source": "Wikipedia",
                }
    except Exception:
        pass

    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": title,
                "gsrlimit": 2,
                "redirects": 1,
                "prop": "pageimages|extracts|description",
                "piprop": "thumbnail",
                "pithumbsize": 480,
                "exintro": 1,
                "explaintext": 1,
                "format": "json",
            },
            headers=HEADERS,
            timeout=timeout,
        )
        if resp.status_code == 200:
            pages_dict = resp.json().get("query", {}).get("pages", {})
            pages = sorted(pages_dict.values(), key=lambda p: p.get("index", 99))
            for page in pages:
                p_title = str(page.get("title") or "").strip()
                extract = str(page.get("extract") or "").strip()
                thumb = str((page.get("thumbnail") or {}).get("source") or "")
                if not thumb and gallery:
                    thumb = gallery[0]["url"]
                desc = str(page.get("description") or "")
                if p_title and extract and "may refer to:" not in extract[:120].lower():
                    return {
                        "title": p_title,
                        "subtitle": desc,
                        "description": _trim_description(extract),
                        "image_url": thumb,
                        "images": gallery,
                        "url": f"https://en.wikipedia.org/wiki/{quote(p_title.replace(' ', '_'), safe='')}",
                        "source": "Wikipedia",
                    }
    except Exception:
        pass

    return None


def fetch_topic_card(
    query: str,
    results: list[dict[str, Any]] | None = None,
    reply: str = "",
    timeout: int = 4,
) -> dict[str, str] | None:
    """Build a visual knowledge card (title, subtitle, description, image) for general/topic answers."""
    q = (query or "").strip()
    if not q or GREETING_ONLY_RE.match(q):
        return None
    if WEATHER_QUERY_RE.search(q) or LIST_OR_NEWS_RE.search(q):
        return None
    if SKIP_TOPIC_CARD_RE.search(q) and not re.search(r"\b(?:who|what)\s+is\b", q, re.IGNORECASE):
        return None

    fallback_card: dict[str, str] | None = None
    for candidate in _resolve_entity_candidates(q, results=results, reply=reply):
        card = _fetch_wiki_page_summary(candidate, timeout=timeout)
        if not card:
            continue
        if card.get("image_url"):
            return card
        if fallback_card is None:
            fallback_card = card
    return fallback_card

