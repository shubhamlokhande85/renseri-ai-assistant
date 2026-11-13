"""Intelligent Natural-Language-to-SQL translator (local engine + optional LLM)."""

from __future__ import annotations

import difflib
import os
import re
from dataclasses import dataclass
from typing import Any

import requests

from app.ai_config import resolve_provider_keys
from app.db_engine import ColumnProfile, DatasetSession, validate_read_only_sql


@dataclass
class NL2SQLResult:
    """Generated SQL and explanation metadata."""

    sql: str
    explanation: str
    confidence: str  # high | medium | fallback
    engine: str  # local | groq | gemini
    intent: str  # aggregate | groupby | top_n | filter | list | schema | stats


AGG_PATTERNS: list[tuple[str, str, str]] = [
    (r"\b(count\s+distinct|unique|distinct)\b", "COUNT_DISTINCT", "unique count"),
    (r"\b(sum|total|combined|overall)\b", "SUM", "total"),
    (r"\b(avg|average|mean)\b", "AVG", "average"),
    (r"\b(max|maximum|highest|largest|biggest|most\s+expensive|top|peak)\b", "MAX", "maximum"),
    (r"\b(min|minimum|lowest|smallest|cheapest|least)\b", "MIN", "minimum"),
    (r"\b(how\s+many|count|number\s+of|total\s+rows|total\s+records)\b", "COUNT", "count"),
]

STOPWORDS = {
    "show", "me", "the", "a", "an", "of", "in", "on", "at", "to", "for", "from",
    "with", "by", "per", "each", "is", "are", "was", "were", "be", "that", "which",
    "what", "who", "where", "when", "how", "many", "much", "all", "give", "find",
    "get", "list", "display", "return", "calculate", "compute", "tell", "rows",
    "records", "entries", "items", "data", "dataset", "table", "please", "and",
    "or", "having", "group", "grouped", "order", "ordered", "sort", "sorted",
    "top", "bottom", "first", "last", "limit", "only", "breakdown", "distribution",
    "summary", "report", "compare", "comparison", "across", "between", "greater",
    "more", "above", "over", "less", "under", "below", "equals", "equal", "than",
    "not", "null", "missing", "empty", "contains", "containing", "starts", "ends",
}


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _col_aliases(profile: ColumnProfile) -> list[str]:
    """Generate natural-language aliases for a column."""
    aliases = {
        profile.name.lower(),
        profile.name.lower().replace("_", " "),
        profile.original_name.lower().strip(),
        re.sub(r"[^a-z0-9]+", " ", profile.original_name.lower()).strip(),
    }
    # Singular/plural variants
    expanded: set[str] = set()
    for a in aliases:
        if not a:
            continue
        expanded.add(a)
        if a.endswith("s") and len(a) > 3:
            expanded.add(a[:-1])
        else:
            expanded.add(a + "s")
    return sorted(expanded, key=len, reverse=True)


def find_mentioned_columns(
    question: str, profiles: list[ColumnProfile]
) -> list[tuple[ColumnProfile, int]]:
    """Return columns matched in the question along with their position index."""
    q_lower = question.lower()
    matched: dict[str, tuple[ColumnProfile, int]] = {}

    for p in profiles:
        for alias in _col_aliases(p):
            if len(alias) < 2:
                continue
            pattern = r"\b" + re.escape(alias) + r"\b"
            m = re.search(pattern, q_lower)
            if m:
                if p.name not in matched or m.start() < matched[p.name][1]:
                    matched[p.name] = (p, m.start())
                break

    # Fuzzy fallback on individual tokens if nothing matched directly
    if not matched:
        q_tokens = [t for t in _tokenize(q_lower) if t not in STOPWORDS and len(t) >= 3]
        col_names = [p.name for p in profiles]
        profile_by_name = {p.name: p for p in profiles}
        for tok in q_tokens:
            close = difflib.get_close_matches(tok, col_names, n=1, cutoff=0.78)
            if close:
                p = profile_by_name[close[0]]
                matched[p.name] = (p, q_lower.find(tok))

    return sorted(matched.values(), key=lambda x: x[1])


def _extract_limit(question: str) -> tuple[int | None, str]:
    """Extract top/bottom/first/limit N and direction ('DESC' or 'ASC')."""
    q = question.lower()
    m = re.search(r"\b(?:top|highest|largest|biggest|best)\s+(\d+)\b", q)
    if m:
        return int(m.group(1)), "DESC"
    m = re.search(r"\b(?:bottom|lowest|smallest|worst)\s+(\d+)\b", q)
    if m:
        return int(m.group(1)), "ASC"
    m = re.search(r"\b(?:first|limit|show)\s+(\d+)\b", q)
    if m:
        return int(m.group(1)), "ASC"
    return None, "DESC"


def _extract_where_clauses(
    question: str, profiles: list[ColumnProfile]
) -> tuple[list[str], list[str]]:
    """Extract SQL WHERE predicates and human-readable filter descriptions."""
    q = question
    q_lower = question.lower()
    clauses: list[str] = []
    descriptions: list[str] = []
    used_cols: set[str] = set()

    # 1. Explicit numeric comparisons: "<col> > 100", "<col> greater than 100", "<col> between 10 and 20"
    for p in profiles:
        if p.semantic_type not in ("integer", "numeric", "date"):
            continue
        for alias in _col_aliases(p):
            esc = re.escape(alias)
            # BETWEEN
            m_bet = re.search(
                rf"\b{esc}\b\s+(?:is\s+)?between\s+(['\"]?[\w.\-]+['\"]?)\s+and\s+(['\"]?[\w.\-]+['\"]?)",
                q_lower,
            )
            if m_bet:
                v1 = m_bet.group(1).strip("'\"")
                v2 = m_bet.group(2).strip("'\"")
                if p.semantic_type == "date":
                    clauses.append(f'"{p.name}" BETWEEN \'{v1}\' AND \'{v2}\'')
                else:
                    clauses.append(f'"{p.name}" BETWEEN {v1} AND {v2}')
                descriptions.append(f"{p.name} between {v1} and {v2}")
                used_cols.add(p.name)
                break

            # Operators
            op_patterns = [
                (r"(?:>=|at\s+least)", ">="),
                (r"(?:<=|at\s+most)", "<="),
                (r"(?:!=|<>|not\s+equal\s+to)", "!="),
                (r"(?:>|greater\s+than|more\s+than|above|over|after)", ">"),
                (r"(?:<|less\s+than|fewer\s+than|under|below|before)", "<"),
                (r"(?:=|equals|equal\s+to)", "="),
            ]
            matched_op = False
            for op_re, sql_op in op_patterns:
                m_op = re.search(
                    rf"\b{esc}\b\s+(?:is\s+)?{op_re}\s+[\$\€\£]?([\d,]+(?:\.\d+)?|\d{{4}}-\d{{2}}-\d{{2}})",
                    q_lower,
                )
                if m_op:
                    raw_val = m_op.group(1).replace(",", "")
                    val_sql = f"'{raw_val}'" if p.semantic_type == "date" else raw_val
                    clauses.append(f'"{p.name}" {sql_op} {val_sql}')
                    descriptions.append(f"{p.name} {sql_op} {raw_val}")
                    used_cols.add(p.name)
                    matched_op = True
                    break
            if matched_op:
                break

    # 2. Explicit NULL / missing checks
    for p in profiles:
        for alias in _col_aliases(p):
            esc = re.escape(alias)
            if re.search(
                rf"\b(?:missing|null|empty)\s+{esc}\b|\b{esc}\s+(?:is\s+)?(?:null|missing|empty)\b",
                q_lower,
            ):
                clauses.append(f'"{p.name}" IS NULL')
                descriptions.append(f"{p.name} IS NULL")
                used_cols.add(p.name)
                break
            if re.search(
                rf"\b{esc}\s+(?:is\s+)?not\s+(?:null|missing|empty)\b",
                q_lower,
            ):
                clauses.append(f'"{p.name}" IS NOT NULL')
                descriptions.append(f"{p.name} IS NOT NULL")
                used_cols.add(p.name)
                break

    # 3. String LIKE / contains / starts with / ends with
    for p in profiles:
        if p.semantic_type != "text":
            continue
        for alias in _col_aliases(p):
            esc = re.escape(alias)
            m_like = re.search(
                rf"\b{esc}\b\s+(?:contains|containing|like|includes)\s+['\"]?([a-zA-Z0-9_.@\- ]+)['\"]?",
                q,
                re.IGNORECASE,
            )
            if m_like:
                val = m_like.group(1).strip().replace("'", "''")
                clauses.append(f'LOWER("{p.name}") LIKE LOWER(\'%{val}%\')')
                descriptions.append(f"{p.name} contains '{val}'")
                used_cols.add(p.name)
                break

    # 4. Year filter on date columns: "in 2024", "year 2023"
    date_cols = [p for p in profiles if p.semantic_type == "date"]
    if date_cols:
        m_yr = re.search(r"\b(?:in|for|year)\s+(20\d{2}|19\d{2})\b", q_lower)
        if m_yr:
            yr = m_yr.group(1)
            dcol = date_cols[0].name
            if dcol not in used_cols:
                clauses.append(f'strftime(\'%Y\', "{dcol}") = \'{yr}\'')
                descriptions.append(f"{dcol} in {yr}")
                used_cols.add(dcol)

    # 5. Implicit categorical value matching (e.g., "sales in North", "orders that are Completed")
    # Skip values that collide with column names or SQL keywords.
    col_name_words = {p.name.lower().replace("_", " ") for p in profiles}
    for p in profiles:
        if p.name in used_cols or not p.categorical_values:
            continue
        # Sort longest values first so "New York" matches before "New"
        for cat_val in sorted(p.categorical_values, key=len, reverse=True):
            cv_clean = cat_val.strip()
            if len(cv_clean) < 2 or cv_clean.lower() in STOPWORDS or cv_clean.lower() in col_name_words:
                continue
            if re.search(r"\b" + re.escape(cv_clean) + r"\b", q, re.IGNORECASE):
                safe_val = cv_clean.replace("'", "''")
                clauses.append(f'LOWER("{p.name}") = LOWER(\'{safe_val}\')')
                descriptions.append(f"{p.name} = '{cv_clean}'")
                used_cols.add(p.name)
                break

    return clauses, descriptions


def _extract_groupby_columns(
    question: str, profiles: list[ColumnProfile], filter_cols: set[str]
) -> tuple[list[str], str | None]:
    """Identify GROUP BY expressions (supports 'by <col>', 'per <col>', 'monthly', 'yearly')."""
    q_lower = question.lower()
    date_cols = [p for p in profiles if p.semantic_type == "date"]

    # Time grain grouping
    if date_cols:
        dcol = date_cols[0].name
        if re.search(r"\b(monthly|by\s+month|per\s+month|each\s+month)\b", q_lower):
            return [f'strftime(\'%Y-%m\', "{dcol}")'], f"month ({dcol})"
        if re.search(r"\b(yearly|annually|by\s+year|per\s+year|each\s+year)\b", q_lower):
            return [f'strftime(\'%Y\', "{dcol}")'], f"year ({dcol})"

    # Explicit "by <col>" / "per <col>" / "for each <col>" / "breakdown of <col>"
    m_grp = re.search(
        r"\b(?:by|per|for\s+each|grouped\s+by|breakdown\s+of|distribution\s+of)\s+(.+)$",
        q_lower,
    )
    if m_grp:
        tail = m_grp.group(1)
        tail_matches = find_mentioned_columns(tail, profiles)
        dims = [
            f'"{p.name}"'
            for p, _ in tail_matches
            if p.name not in filter_cols and p.semantic_type in ("text", "boolean", "date", "integer")
        ]
        if dims:
            return dims[:2], None

    return [], None


def _pick_measure_column(
    question: str, profiles: list[ColumnProfile], exclude: set[str]
) -> ColumnProfile | None:
    """Select the best numeric measure column mentioned or inferred from the schema."""
    mentioned = find_mentioned_columns(question, profiles)
    for p, _ in mentioned:
        if p.name not in exclude and p.semantic_type in ("integer", "numeric"):
            return p

    # Infer by common business measure keywords
    numeric_cols = [
        p
        for p in profiles
        if p.semantic_type in ("integer", "numeric")
        and p.name not in exclude
        and not p.name.endswith("_id")
        and p.name != "id"
    ]
    if not numeric_cols:
        return None

    priority_terms = (
        "revenue", "sales", "amount", "total", "price", "profit",
        "salary", "income", "cost", "value", "score", "qty", "quantity",
    )
    for term in priority_terms:
        for p in numeric_cols:
            if term in p.name:
                return p
    return numeric_cols[0]


def translate_nl_to_sql_local(
    question: str, session: DatasetSession
) -> NL2SQLResult:
    """Translate a natural language question into SQLite SQL deterministically."""
    q_lower = question.lower().strip()
    table = f'"{session.table_name}"'
    profiles = session.profiles
    profile_map = {p.name: p for p in profiles}

    # Check if user asks for summary statistics / overview
    if re.search(r"\b(summary\s+stats|summary\s+statistics|describe\s+dataset|overview)\b", q_lower):
        num_cols = [
            p for p in profiles
            if p.semantic_type in ("integer", "numeric") and p.name != "id" and not p.name.endswith("_id")
        ][:4]
        if num_cols:
            select_parts = ["COUNT(*) AS total_rows"]
            for p in num_cols:
                select_parts.append(f'ROUND(AVG("{p.name}"), 2) AS avg_{p.name}')
                select_parts.append(f'ROUND(SUM("{p.name}"), 2) AS sum_{p.name}')
            sql = f"SELECT {', '.join(select_parts)} FROM {table};"
            return NL2SQLResult(
                sql=sql,
                explanation="Computed overall row count, averages, and totals across numeric columns.",
                confidence="high",
                engine="local",
                intent="stats",
            )

    where_clauses, filter_descs = _extract_where_clauses(question, profiles)
    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    filter_col_names = {
        desc.split()[0] for desc in filter_descs if desc.split()[0] in profile_map
    }

    limit_n, limit_dir = _extract_limit(question)

    # Detect aggregation intent
    agg_func: str | None = None
    agg_label = ""
    for pattern, func_name, label in AGG_PATTERNS:
        if re.search(pattern, q_lower):
            agg_func = func_name
            agg_label = label
            break

    # Detect GROUP BY
    group_exprs, time_label = _extract_groupby_columns(question, profiles, filter_col_names)
    group_col_names = {g.strip('"') for g in group_exprs if g.strip('"') in profile_map}

    mentioned = find_mentioned_columns(question, profiles)
    mentioned_cols = [p for p, _ in mentioned]

    # Case 1: Distribution / breakdown without explicit agg -> COUNT(*) GROUP BY
    is_breakdown = bool(
        re.search(r"\b(breakdown|distribution|counts?\s+by|how\s+many\s+.*by)\b", q_lower)
    )
    if (group_exprs and agg_func in (None, "COUNT")) or (is_breakdown and group_exprs):
        grp_select = []
        for idx, g in enumerate(group_exprs):
            alias = "period" if time_label and idx == 0 else g.strip('"')
            grp_select.append(f"{g} AS {alias}")
        select_str = ", ".join(grp_select) + ", COUNT(*) AS record_count"
        grp_by_str = ", ".join(group_exprs)
        lim = f" LIMIT {limit_n}" if limit_n else " LIMIT 100"
        sql = (
            f"SELECT {select_str} FROM {table}{where_sql} "
            f"GROUP BY {grp_by_str} ORDER BY record_count {limit_dir}{lim};"
        )
        return NL2SQLResult(
            sql=sql,
            explanation=f"Grouped records by {time_label or ', '.join(group_col_names)} and counted rows.",
            confidence="high",
            engine="local",
            intent="groupby",
        )

    # Case 2: Grouped aggregation (e.g., "total sales by region", "average salary per department")
    if group_exprs and agg_func in ("SUM", "AVG", "MAX", "MIN", "COUNT_DISTINCT"):
        measure = _pick_measure_column(question, profiles, group_col_names)
        if agg_func == "COUNT_DISTINCT":
            target_col = next(
                (p for p in mentioned_cols if p.name not in group_col_names),
                measure or profiles[0],
            )
            agg_expr = f'COUNT(DISTINCT "{target_col.name}")'
            agg_alias = f"unique_{target_col.name}"
        elif measure is not None:
            if agg_func in ("SUM", "AVG"):
                agg_expr = f'ROUND({agg_func}("{measure.name}"), 2)'
            else:
                agg_expr = f'{agg_func}("{measure.name}")'
            agg_alias = f"{agg_func.lower()}_{measure.name}"
        else:
            agg_expr = "COUNT(*)"
            agg_alias = "record_count"

        grp_select = [
            f"{g} AS {'period' if time_label and i == 0 else g.strip('\"')}"
            for i, g in enumerate(group_exprs)
        ]
        order_clause = (
            "ORDER BY period ASC"
            if time_label
            else f"ORDER BY {agg_alias} {limit_dir}"
        )
        lim = f" LIMIT {limit_n}" if limit_n else " LIMIT 100"
        sql = (
            f"SELECT {', '.join(grp_select)}, {agg_expr} AS {agg_alias} "
            f"FROM {table}{where_sql} "
            f"GROUP BY {', '.join(group_exprs)} {order_clause}{lim};"
        )
        return NL2SQLResult(
            sql=sql,
            explanation=f"Computed {agg_label} grouped by {time_label or ', '.join(group_col_names)}.",
            confidence="high",
            engine="local",
            intent="groupby",
        )

    # Case 3: Top-N / Bottom-N rows (e.g., "top 5 products by revenue" or "top 5 highest salaries")
    if limit_n is not None and agg_func in (None, "MAX", "MIN"):
        sort_col = _pick_measure_column(question, profiles, filter_col_names)
        if sort_col:
            # Determine which columns to project
            proj = "*"
            sql = (
                f'SELECT {proj} FROM {table}{where_sql} '
                f'WHERE "{sort_col.name}" IS NOT NULL '
                if not where_sql
                else f'SELECT {proj} FROM {table}{where_sql} AND "{sort_col.name}" IS NOT NULL '
            )
            sql += f'ORDER BY "{sort_col.name}" {limit_dir} LIMIT {limit_n};'
            return NL2SQLResult(
                sql=sql,
                explanation=f"Retrieved top {limit_n} records ordered by {sort_col.name} ({limit_dir}).",
                confidence="high",
                engine="local",
                intent="top_n",
            )

    # Case 4: Single-value aggregation (e.g., "how many rows", "total revenue", "average salary")
    if agg_func == "COUNT" and not group_exprs:
        sql = f"SELECT COUNT(*) AS total_count FROM {table}{where_sql};"
        return NL2SQLResult(
            sql=sql,
            explanation="Counted matching records in the cleaned dataset.",
            confidence="high",
            engine="local",
            intent="aggregate",
        )

    if agg_func in ("SUM", "AVG", "MAX", "MIN", "COUNT_DISTINCT") and not group_exprs:
        if agg_func == "COUNT_DISTINCT":
            target = next(
                (p for p in mentioned_cols if p.name not in filter_col_names),
                profiles[0],
            )
            sql = f'SELECT COUNT(DISTINCT "{target.name}") AS unique_{target.name} FROM {table}{where_sql};'
            return NL2SQLResult(
                sql=sql,
                explanation=f"Counted distinct values in '{target.name}'.",
                confidence="high",
                engine="local",
                intent="aggregate",
            )
        measure = _pick_measure_column(question, profiles, filter_col_names)
        if measure:
            expr = (
                f'ROUND({agg_func}("{measure.name}"), 2)'
                if agg_func in ("SUM", "AVG")
                else f'{agg_func}("{measure.name}")'
            )
            alias = f"{agg_func.lower()}_{measure.name}"
            sql = f"SELECT {expr} AS {alias} FROM {table}{where_sql};"
            return NL2SQLResult(
                sql=sql,
                explanation=f"Computed {agg_label} of '{measure.name}'.",
                confidence="high",
                engine="local",
                intent="aggregate",
            )

    # Case 5: Single categorical column distribution ("show categories", "list unique regions")
    if re.search(r"\b(unique|distinct|list\s+all|what\s+are\s+the)\b", q_lower) and mentioned_cols:
        col = mentioned_cols[0]
        sql = (
            f'SELECT "{col.name}", COUNT(*) AS count FROM {table}{where_sql} '
            f'GROUP BY "{col.name}" ORDER BY count DESC LIMIT 50;'
        )
        return NL2SQLResult(
            sql=sql,
            explanation=f"Listed distinct values and frequencies for '{col.name}'.",
            confidence="high",
            engine="local",
            intent="groupby",
        )

    # Case 6: Filtered or general listing query
    lim = limit_n or 50
    if where_clauses or mentioned_cols:
        if mentioned_cols and len(mentioned_cols) <= 5 and not where_clauses:
            cols_sql = ", ".join(f'"{p.name}"' for p in mentioned_cols)
        else:
            cols_sql = "*"
        sql = f"SELECT {cols_sql} FROM {table}{where_sql} LIMIT {lim};"
        return NL2SQLResult(
            sql=sql,
            explanation=(
                f"Filtered records matching: {', '.join(filter_descs)}."
                if filter_descs
                else "Selected requested columns from the cleaned dataset."
            ),
            confidence="high" if where_clauses else "medium",
            engine="local",
            intent="filter" if where_clauses else "list",
        )

    # Fallback: preview cleaned rows
    sql = f"SELECT * FROM {table} LIMIT {lim};"
    return NL2SQLResult(
        sql=sql,
        explanation="Showing rows from the cleaned dataset. Try specifying columns, aggregations (sum, avg, count), or filters!",
        confidence="fallback",
        engine="local",
        intent="list",
    )


def _build_schema_prompt(session: DatasetSession) -> str:
    cols_desc = []
    for p in session.profiles:
        extra = ""
        if p.categorical_values:
            extra = f" | values: {p.categorical_values[:8]}"
        elif p.min_value is not None:
            extra = f" | range: {p.min_value}..{p.max_value}"
        cols_desc.append(f'- "{p.name}" ({p.sqlite_type}, {p.semantic_type}){extra}')
    return (
        f'SQLite table name: "{session.table_name}"\n'
        f"Row count: {len(session.cleaned_df)}\n"
        "Columns:\n" + "\n".join(cols_desc)
    )


def _is_valid_sqlite_query(session: DatasetSession, sql: str) -> bool:
    """Validate read-only rules and compile-check SQL against SQLite."""
    ok, _ = validate_read_only_sql(sql)
    if not ok:
        return False
    try:
        session.conn.execute(f"EXPLAIN QUERY PLAN {sql.strip().rstrip(';')}")
        return True
    except Exception:
        return False


def translate_nl_to_sql(
    question: str,
    session: DatasetSession,
    api_key: str | None = None,
    provider: str | None = None,
    groq_api_key: str | None = None,
    gemini_api_key: str | None = None,
) -> NL2SQLResult:
    """Translate NL to SQL using Groq, Google Gemini, or the built-in local engine."""
    eff_provider, groq_key, groq_model, gemini_key, gemini_model = resolve_provider_keys(
        req_provider=provider,
        req_groq_key=groq_api_key or (api_key if provider == "groq" else None),
        req_gemini_key=gemini_api_key or (api_key if provider == "gemini" else None),
    )

    if eff_provider == "local":
        return translate_nl_to_sql_local(question, session)

    order: list[str]
    if eff_provider == "groq":
        order = ["groq"]
    elif eff_provider == "gemini":
        order = ["gemini"]
    else:  # auto
        order = ["groq", "gemini"]

    for target in order:
        if target == "groq" and groq_key:
            llm_res = _call_groq_nl2sql(question, session, groq_key, groq_model)
            if llm_res and _is_valid_sqlite_query(session, llm_res.sql):
                return llm_res
        elif target == "gemini" and gemini_key:
            llm_res = _call_gemini_nl2sql(question, session, gemini_key, gemini_model)
            if llm_res and _is_valid_sqlite_query(session, llm_res.sql):
                return llm_res

    return translate_nl_to_sql_local(question, session)


def _extract_sql_from_llm(text: str) -> str:
    m = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _build_llm_sql_prompt(question: str, session: DatasetSession) -> str:
    schema_txt = _build_schema_prompt(session)
    return (
        "You are an expert SQLite SQL generator.\n"
        "Rules:\n"
        "1. Return ONLY a single valid read-only SQLite SELECT or WITH query wrapped in ```sql ... ```.\n"
        "2. Quote column and table identifiers with double quotes like \"column_name\".\n"
        "3. Use ONLY columns from the schema below. Never use DROP, DELETE, UPDATE, INSERT, or ALTER.\n"
        "4. For case-insensitive text filters, prefer LOWER(\"col\") = LOWER('value').\n\n"
        f"{schema_txt}\n\nUser question: {question}"
    )


def _call_groq_nl2sql(
    question: str, session: DatasetSession, api_key: str, model: str
) -> NL2SQLResult | None:
    prompt = _build_llm_sql_prompt(question, session)
    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 512,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        sql = _extract_sql_from_llm(content)
        if not sql:
            return None
        return NL2SQLResult(
            sql=sql,
            explanation=f"Generated via Groq ({model}) against the cleaned SQLite schema.",
            confidence="high",
            engine=f"groq:{model}",
            intent="llm",
        )
    except Exception:
        return None


def _call_gemini_nl2sql(
    question: str, session: DatasetSession, api_key: str, model: str
) -> NL2SQLResult | None:
    prompt = _build_llm_sql_prompt(question, session)
    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 512},
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        sql = _extract_sql_from_llm(content)
        if not sql:
            return None
        return NL2SQLResult(
            sql=sql,
            explanation=f"Generated via Google Gemini ({model}) against the cleaned SQLite schema.",
            confidence="high",
            engine=f"gemini:{model}",
            intent="llm",
        )
    except Exception:
        return None
