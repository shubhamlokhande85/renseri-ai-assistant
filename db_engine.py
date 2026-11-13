"""SQLite session store, schema profiler, and safe SQL execution engine."""

from __future__ import annotations

import io
import os
import re
import sqlite3
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.cleaner import CleaningOptions, CleaningReport, clean_dataset, dataframe_preview


FORBIDDEN_SQL_RE = re.compile(
    r"\b(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|REPLACE|TRUNCATE|ATTACH|DETACH|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)


@dataclass
class ColumnProfile:
    """Rich metadata for a single cleaned column."""

    name: str
    original_name: str
    semantic_type: str  # integer | numeric | date | boolean | text
    sqlite_type: str
    null_count: int
    distinct_count: int
    min_value: Any = None
    max_value: Any = None
    mean_value: float | None = None
    sample_values: list[Any] = field(default_factory=list)
    categorical_values: list[str] = field(default_factory=list)


@dataclass
class DatasetSession:
    """In-memory session holding raw/cleaned data, SQLite DB, and chat state."""

    session_id: str
    filename: str
    table_name: str
    raw_df: pd.DataFrame
    cleaned_df: pd.DataFrame
    report: CleaningReport
    options: CleaningOptions
    conn: sqlite3.Connection
    profiles: list[ColumnProfile]
    reverse_column_map: dict[str, str]  # original lowercase -> cleaned name
    chat_history: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class SessionManager:
    """Manages active dataset sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, DatasetSession] = {}

    def create_session(
        self,
        filename: str,
        raw_df: pd.DataFrame,
        options: CleaningOptions | None = None,
    ) -> DatasetSession:
        session_id = uuid.uuid4().hex[:12]
        table_name = self._derive_table_name(filename)
        opts = options or CleaningOptions()
        cleaned_df, report = clean_dataset(raw_df, opts)
        conn = self._load_into_sqlite(cleaned_df, table_name, report.detected_types)
        profiles = self._profile_columns(cleaned_df, report)
        reverse_map = {
            orig.strip().lower(): clean
            for orig, clean in report.column_mapping.items()
        }

        session = DatasetSession(
            session_id=session_id,
            filename=filename,
            table_name=table_name,
            raw_df=raw_df,
            cleaned_df=cleaned_df,
            report=report,
            options=opts,
            conn=conn,
            profiles=profiles,
            reverse_column_map=reverse_map,
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> DatasetSession | None:
        return self._sessions.get(session_id)

    def reclean_session(
        self, session_id: str, options: CleaningOptions
    ) -> DatasetSession | None:
        session = self._sessions.get(session_id)
        if not session:
            return None
        try:
            session.conn.close()
        except Exception:
            pass

        cleaned_df, report = clean_dataset(session.raw_df, options)
        conn = self._load_into_sqlite(
            cleaned_df, session.table_name, report.detected_types
        )
        profiles = self._profile_columns(cleaned_df, report)
        reverse_map = {
            orig.strip().lower(): clean
            for orig, clean in report.column_mapping.items()
        }
        session.cleaned_df = cleaned_df
        session.report = report
        session.options = options
        session.conn = conn
        session.profiles = profiles
        session.reverse_column_map = reverse_map
        return session

    @staticmethod
    def _derive_table_name(filename: str) -> str:
        stem = os.path.splitext(os.path.basename(filename))[0].lower()
        stem = re.sub(r"[^a-z0-9]+", "_", stem).strip("_")
        if not stem or stem[0].isdigit():
            stem = f"dataset_{stem}" if stem else "dataset"
        return stem[:40]

    @staticmethod
    def _load_into_sqlite(
        df: pd.DataFrame, table_name: str, detected_types: dict[str, str]
    ) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        conn.row_factory = sqlite3.Row

        col_defs: list[str] = []
        for col in df.columns:
            sem = detected_types.get(col, "text")
            if sem in ("integer", "boolean"):
                sql_t = "INTEGER"
            elif sem == "numeric":
                sql_t = "REAL"
            else:
                sql_t = "TEXT"
            col_defs.append(f'"{col}" {sql_t}')

        ddl = f'CREATE TABLE "{table_name}" ({", ".join(col_defs)})'
        conn.execute(ddl)

        if not df.empty:
            placeholders = ", ".join(["?"] * len(df.columns))
            col_list = ", ".join(f'"{c}"' for c in df.columns)
            insert_sql = f'INSERT INTO "{table_name}" ({col_list}) VALUES ({placeholders})'

            rows_to_insert: list[tuple[Any, ...]] = []
            for row in df.itertuples(index=False, name=None):
                clean_row = []
                for val in row:
                    if val is None or (isinstance(val, float) and np.isnan(val)) or pd.isna(val):
                        clean_row.append(None)
                    elif isinstance(val, (np.integer,)):
                        clean_row.append(int(val))
                    elif isinstance(val, (np.floating,)):
                        clean_row.append(float(val))
                    elif isinstance(val, (np.bool_, bool)):
                        clean_row.append(int(val))
                    else:
                        clean_row.append(str(val))
                rows_to_insert.append(tuple(clean_row))
            conn.executemany(insert_sql, rows_to_insert)

        conn.commit()
        return conn

    @staticmethod
    def _profile_columns(
        df: pd.DataFrame, report: CleaningReport
    ) -> list[ColumnProfile]:
        clean_to_orig = {v: k for k, v in report.column_mapping.items()}
        profiles: list[ColumnProfile] = []

        for col in df.columns:
            series = df[col]
            sem = report.detected_types.get(col, "text")
            if sem in ("integer", "boolean"):
                sql_t = "INTEGER"
            elif sem == "numeric":
                sql_t = "REAL"
            else:
                sql_t = "TEXT"

            non_null = series.dropna()
            null_count = int(series.isna().sum())
            distinct_count = int(non_null.nunique())

            min_val = None
            max_val = None
            mean_val = None
            if len(non_null) > 0:
                if sem in ("integer", "numeric"):
                    min_val = float(non_null.min())
                    max_val = float(non_null.max())
                    if sem == "integer":
                        min_val = int(min_val)
                        max_val = int(max_val)
                    mean_val = round(float(non_null.mean()), 4)
                elif sem == "date":
                    min_val = str(non_null.min())
                    max_val = str(non_null.max())

            sample_vals: list[Any] = []
            for v in non_null.head(5).tolist():
                if isinstance(v, (np.integer,)):
                    sample_vals.append(int(v))
                elif isinstance(v, (np.floating,)):
                    sample_vals.append(round(float(v), 4))
                else:
                    sample_vals.append(str(v))

            cat_vals: list[str] = []
            if sem == "text" and 1 <= distinct_count <= 60:
                cat_vals = [str(v) for v in non_null.value_counts().head(40).index.tolist()]

            profiles.append(
                ColumnProfile(
                    name=col,
                    original_name=clean_to_orig.get(col, col),
                    semantic_type=sem,
                    sqlite_type=sql_t,
                    null_count=null_count,
                    distinct_count=distinct_count,
                    min_value=min_val,
                    max_value=max_val,
                    mean_value=mean_val,
                    sample_values=sample_vals,
                    categorical_values=cat_vals,
                )
            )
        return profiles


def strip_sql_comments(sql: str) -> str:
    """Remove -- line comments and /* */ block comments for validation."""
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


def validate_read_only_sql(sql: str) -> tuple[bool, str]:
    """Ensure SQL query is read-only and single-statement."""
    cleaned = strip_sql_comments(sql).rstrip(";").strip()
    if not cleaned:
        return False, "SQL query is empty."
    if ";" in cleaned:
        return False, "Only a single SQL statement is allowed per query."

    upper_head = cleaned.split(None, 1)[0].upper()
    if upper_head not in ("SELECT", "WITH", "PRAGMA", "EXPLAIN"):
        return (
            False,
            f"Only read-only SELECT / WITH / PRAGMA queries are permitted (got '{upper_head}').",
        )

    if upper_head == "PRAGMA" and not re.match(
        r"^PRAGMA\s+(table_info|table_list)\b", cleaned, re.IGNORECASE
    ):
        return False, "Only PRAGMA table_info / table_list is allowed."

    match = FORBIDDEN_SQL_RE.search(cleaned)
    if match:
        return (
            False,
            f"Mutating SQL keyword '{match.group(1).upper()}' is blocked in read-only chatbot mode.",
        )
    return True, ""


def execute_sql(
    session: DatasetSession, sql: str, max_rows: int = 500
) -> dict[str, Any]:
    """Execute a validated read-only SQL query against the session's SQLite DB."""
    ok, err = validate_read_only_sql(sql)
    if not ok:
        return {"ok": False, "error": err, "sql": sql}

    started = time.perf_counter()
    try:
        cursor = session.conn.execute(sql.strip().rstrip(";"))
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        all_rows = cursor.fetchmany(max_rows + 1)
        truncated = len(all_rows) > max_rows
        rows_slice = all_rows[:max_rows]
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

        formatted_rows: list[dict[str, Any]] = []
        for r in rows_slice:
            row_dict: dict[str, Any] = {}
            for idx, col in enumerate(columns):
                val = r[idx]
                if isinstance(val, float):
                    row_dict[col] = round(val, 4) if not val.is_integer() else int(val)
                else:
                    row_dict[col] = val
            formatted_rows.append(row_dict)

        return {
            "ok": True,
            "sql": sql.strip(),
            "columns": columns,
            "rows": formatted_rows,
            "row_count": len(formatted_rows),
            "truncated": truncated,
            "execution_ms": elapsed_ms,
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc), "sql": sql}


def export_dataset_bytes(session: DatasetSession, fmt: str) -> tuple[bytes, str, str]:
    """Serialize the cleaned dataset to CSV, XLSX, or SQLite DB bytes."""
    base = os.path.splitext(session.filename)[0]
    fmt = fmt.lower()

    if fmt == "csv":
        data = session.cleaned_df.to_csv(index=False).encode("utf-8-sig")
        return data, "text/csv; charset=utf-8", f"{base}_cleaned.csv"

    if fmt in ("xlsx", "excel"):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            session.cleaned_df.to_excel(writer, index=False, sheet_name="Cleaned_Data")
        return (
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{base}_cleaned.xlsx",
        )

    if fmt in ("sqlite", "db"):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            disk_conn = sqlite3.connect(tmp_path)
            session.conn.backup(disk_conn)
            disk_conn.close()
            with open(tmp_path, "rb") as f:
                data = f.read()
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return data, "application/octet-stream", f"{base}_cleaned.db"

    raise ValueError(f"Unsupported export format: {fmt}")


def _compute_eda_summary(df: pd.DataFrame, profiles: list[ColumnProfile]) -> dict[str, Any]:
    """Compute automated Exploratory Data Analysis metrics across numeric & categorical columns."""
    eda: dict[str, Any] = {
        "numeric_stats": [],
        "categorical_breakdown": [],
        "correlations": [],
        "missing_summary": [],
    }

    # 1. Numeric statistics (Mean, Median, Std, Min, 25%, 50%, 75%, Max, Skew)
    for p in profiles:
        if p.semantic_type in ("integer", "numeric") and p.name in df.columns:
            s = pd.to_numeric(df[p.name], errors="coerce").dropna()
            if len(s) > 0:
                try:
                    q25 = float(s.quantile(0.25))
                    q50 = float(s.median())
                    q75 = float(s.quantile(0.75))
                    std_val = float(s.std()) if len(s) > 1 else 0.0
                    skew_val = float(s.skew()) if len(s) > 2 else 0.0
                    eda["numeric_stats"].append({
                        "column": p.name,
                        "count": int(len(s)),
                        "mean": round(float(s.mean()), 2),
                        "std": round(std_val, 2),
                        "min": round(float(s.min()), 2),
                        "q25": round(q25, 2),
                        "median": round(q50, 2),
                        "q75": round(q75, 2),
                        "max": round(float(s.max()), 2),
                        "skew": round(skew_val, 2),
                    })
                except Exception:
                    pass

    # 2. Categorical breakdown (Top categories and frequency)
    for p in profiles:
        if p.semantic_type in ("text", "boolean") and p.name in df.columns and 1 <= p.distinct_count <= 50:
            s = df[p.name].dropna()
            vc = s.value_counts().head(5)
            total_n = len(s) if len(s) > 0 else 1
            top_items = [
                {"label": str(k), "count": int(v), "pct": round(float(v) / total_n * 100, 1)}
                for k, v in vc.items()
            ]
            eda["categorical_breakdown"].append({
                "column": p.name,
                "distinct_count": p.distinct_count,
                "top_categories": top_items,
            })

    # 3. Numeric correlation pairs
    num_cols = [p.name for p in profiles if p.semantic_type in ("integer", "numeric") and p.name in df.columns and p.name != "id" and not p.name.endswith("_id")]
    if len(num_cols) >= 2:
        try:
            num_df = df[num_cols].apply(pd.to_numeric, errors="coerce")
            corr_mat = num_df.corr()
            seen_pairs: set[tuple[str, str]] = set()
            for c1 in num_cols:
                for c2 in num_cols:
                    if c1 != c2 and (c2, c1) not in seen_pairs:
                        seen_pairs.add((c1, c2))
                        val = corr_mat.loc[c1, c2]
                        if not pd.isna(val):
                            r_val = round(float(val), 3)
                            strength = "Strong" if abs(r_val) >= 0.7 else ("Moderate" if abs(r_val) >= 0.4 else "Weak")
                            direction = "Positive" if r_val > 0 else "Negative"
                            eda["correlations"].append({
                                "col1": c1,
                                "col2": c2,
                                "correlation": r_val,
                                "strength": f"{strength} {direction}",
                            })
            eda["correlations"].sort(key=lambda x: abs(x["correlation"]), reverse=True)
        except Exception:
            pass

    return eda


def build_session_summary(session: DatasetSession) -> dict[str, Any]:
    """Build complete dataset metadata payload for the frontend."""
    return {
        "session_id": session.session_id,
        "filename": session.filename,
        "table_name": session.table_name,
        "report": session.report.to_dict(),
        "options": {
            "strategy": session.options.strategy,
            "drop_duplicates": session.options.drop_duplicates,
            "normalize_columns": session.options.normalize_columns,
            "trim_strings": session.options.trim_strings,
            "parse_numeric": session.options.parse_numeric,
            "parse_dates": session.options.parse_dates,
            "fill_missing": session.options.fill_missing,
        },
        "profiles": [
            {
                "name": p.name,
                "original_name": p.original_name,
                "semantic_type": p.semantic_type,
                "sqlite_type": p.sqlite_type,
                "null_count": p.null_count,
                "distinct_count": p.distinct_count,
                "min_value": p.min_value,
                "max_value": p.max_value,
                "mean_value": p.mean_value,
                "sample_values": p.sample_values,
                "categorical_values": p.categorical_values,
            }
            for p in session.profiles
        ],
        "eda": _compute_eda_summary(session.cleaned_df, session.profiles),
        "raw_preview": dataframe_preview(session.raw_df, limit=30),
        "cleaned_preview": dataframe_preview(session.cleaned_df, limit=50),
    }
