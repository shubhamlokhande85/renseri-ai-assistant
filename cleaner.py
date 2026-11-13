"""Dataset ingestion, profiling, and automated cleaning pipeline."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd


NULL_MARKERS = {
    "",
    "na",
    "n/a",
    "n.a.",
    "null",
    "none",
    "nan",
    "nil",
    "undefined",
    "-",
    "--",
    "?",
    "unknown",
    "missing",
}

BOOL_TRUE = {"true", "yes", "y", "1", "on"}
BOOL_FALSE = {"false", "no", "n", "0", "off"}

CURRENCY_RE = re.compile(r"^[\s$€£¥₹]*[-+]?[\d,]+(?:\.\d+)?[\s%]*$")
DATE_HINT_RE = re.compile(
    r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|"
    r"^[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4}"
)


@dataclass
class CleaningOptions:
    """User-configurable options for the cleaning pipeline."""

    strategy: str = "smart"  # smart | keep_nulls | drop_rows | minimal
    drop_duplicates: bool = True
    normalize_columns: bool = True
    trim_strings: bool = True
    parse_numeric: bool = True
    parse_dates: bool = True
    fill_missing: str = "smart"  # smart | none | drop_rows | median_mode
    # Feature 5: Additional user-defined cleaning rules
    text_case: str = "none"  # none | title | lower | upper
    fill_text_value: str = "Unknown"
    round_decimals: int | None = None
    drop_columns: list[str] = field(default_factory=list)
    find_text: str = ""
    replace_text: str = ""
    replace_column: str = ""
    # Power Query style transforms
    dtype_column: str = ""
    dtype_target: str = ""       # text | integer | float | date | boolean
    split_column: str = ""
    split_delimiter: str = ""
    split_max_parts: int = 2
    extract_column: str = ""
    extract_mode: str = ""       # first_chars | last_chars | between | digits | email | url
    extract_param: str = ""
    extract_output_col: str = ""
    # Additional Power Query transformations
    filter_column: str = ""
    filter_condition: str = ""   # equals | contains | not_null | greater_than | less_than
    filter_value: str = ""
    sort_column: str = ""
    sort_direction: str = "asc"  # asc | desc
    rename_column: str = ""
    rename_to: str = ""
    fill_direction_col: str = ""
    fill_direction: str = ""     # down | up


@dataclass
class CleaningAction:
    """Single audited cleaning transformation."""

    step: str
    description: str
    affected_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class CleaningReport:
    """Complete before/after audit report of dataset cleaning."""

    original_rows: int
    original_cols: int
    cleaned_rows: int
    cleaned_cols: int
    original_missing_cells: int
    cleaned_missing_cells: int
    duplicates_removed: int
    empty_rows_removed: int
    empty_cols_removed: int
    column_mapping: dict[str, str]
    detected_types: dict[str, str]
    actions: list[dict[str, Any]]
    warnings: list[str]
    quality_score_before: int
    quality_score_after: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_dataframe_from_bytes(filename: str, content: bytes) -> pd.DataFrame:
    """Load an uploaded dataset into a raw pandas DataFrame."""
    lower = filename.lower()
    buffer = io.BytesIO(content)

    if lower.endswith(".csv"):
        return _read_csv_flexible(content, sep=",")
    if lower.endswith(".tsv"):
        return _read_csv_flexible(content, sep="\t")
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(buffer, dtype=object)
    if lower.endswith(".json"):
        try:
            return pd.read_json(buffer, orient="records")
        except ValueError:
            buffer.seek(0)
            return pd.read_json(buffer, lines=True)
    if lower.endswith(".parquet"):
        return pd.read_parquet(buffer)

    raise ValueError(
        f"Unsupported file format for '{filename}'. "
        "Supported formats: CSV, TSV, XLSX, XLS, JSON, Parquet."
    )


def _read_csv_flexible(content: bytes, sep: str = ",") -> pd.DataFrame:
    """Decode CSV/TSV handling common encodings and messy delimiters."""
    last_err: Exception | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            return pd.read_csv(
                io.StringIO(text),
                sep=sep,
                dtype=object,
                keep_default_na=False,
                na_filter=False,
            )
        except Exception as exc:
            last_err = exc
    raise ValueError(f"Could not parse text dataset: {last_err}")


def to_snake_case(name: str, index: int) -> str:
    """Convert any messy column header into a safe SQLite identifier."""
    cleaned = str(name).strip()
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", cleaned)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", cleaned).strip("_").lower()
    if not cleaned:
        cleaned = f"column_{index + 1}"
    if cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"
    sql_reserved = {
        "select", "from", "where", "group", "order", "by", "table", "index",
        "insert", "update", "delete", "create", "drop", "alter", "join",
        "limit", "offset", "having", "union", "as", "on", "and", "or", "not",
        "null", "values", "into", "set", "distinct", "case", "when", "then",
        "else", "end", "date", "time", "year", "month", "day",
    }
    if cleaned in sql_reserved:
        cleaned = f"{cleaned}_col"
    return cleaned


def _count_missing(df: pd.DataFrame) -> int:
    """Count total null or placeholder-missing cells in a DataFrame."""
    if df.empty:
        return 0
    total = int(df.isna().sum().sum())
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            s = df[col].dropna().astype(str).str.strip().str.lower()
            total += int(s.isin(NULL_MARKERS).sum())
    return total


def _compute_quality_score(
    df: pd.DataFrame, missing_cells: int, duplicate_rows: int
) -> int:
    """Calculate a 0-100 dataset cleanliness score."""
    if df.empty or df.shape[0] == 0 or df.shape[1] == 0:
        return 0
    total_cells = df.shape[0] * df.shape[1]
    missing_ratio = min(1.0, missing_cells / max(1, total_cells))
    dup_ratio = min(1.0, duplicate_rows / max(1, df.shape[0]))
    score = 100.0 - (missing_ratio * 55.0) - (dup_ratio * 35.0)
    return max(0, min(100, int(round(score))))


def _try_parse_numeric(series: pd.Series) -> tuple[pd.Series | None, int, bool]:
    """Attempt to coerce currency/percentage/comma-formatted strings to numeric."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return None, 0, False

    if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
        return series, 0, False

    as_list = [str(v).strip() for v in non_null.tolist()]
    match_ratio = sum(1 for v in as_list if CURRENCY_RE.match(v)) / len(as_list)
    if match_ratio < 0.8:
        return None, 0, False

    is_pct = any("%" in v for v in as_list)
    cleaned = (
        series.astype(object)
        .where(series.notna(), None)
        .map(
            lambda v: (
                re.sub(r"[\s$€£¥₹,%]", "", str(v))
                if v is not None and pd.notna(v)
                else np.nan
            )
        )
    )
    numeric = pd.to_numeric(cleaned, errors="coerce")
    valid_after = int(numeric.notna().sum())
    if valid_after < max(1, int(len(non_null) * 0.8)):
        return None, 0, False

    coerced_nulls = int(len(non_null) - valid_after)
    if (numeric.dropna() % 1 == 0).all():
        numeric = numeric.astype("Int64")
    else:
        numeric = numeric.astype("float64")
    return numeric, coerced_nulls, is_pct


def _try_parse_datetime(series: pd.Series, col_name: str) -> tuple[pd.Series | None, int]:
    """Attempt to normalize date/datetime strings to ISO-8601 strings for SQLite."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return None, 0

    if pd.api.types.is_datetime64_any_dtype(series):
        formatted = series.dt.strftime("%Y-%m-%d %H:%M:%S").str.replace(
            " 00:00:00", "", regex=False
        )
        return formatted, 0

    if pd.api.types.is_numeric_dtype(series):
        return None, 0

    as_list = [str(v).strip() for v in non_null.tolist()]
    hint_ratio = sum(1 for v in as_list if DATE_HINT_RE.match(v)) / len(as_list)
    name_has_date = any(
        tok in col_name.lower() for tok in ("date", "time", "created", "updated", "dob", "joined")
    )
    if hint_ratio < 0.7 and not (name_has_date and hint_ratio >= 0.4):
        return None, 0

    parsed = pd.to_datetime(series, errors="coerce", format="mixed")
    valid_after = int(parsed.notna().sum())
    if valid_after < max(1, int(len(non_null) * 0.75)):
        return None, 0

    has_time = bool(((parsed.dropna().dt.hour != 0) | (parsed.dropna().dt.minute != 0)).any())
    fmt = "%Y-%m-%d %H:%M:%S" if has_time else "%Y-%m-%d"
    formatted = parsed.dt.strftime(fmt)
    formatted = formatted.where(parsed.notna(), np.nan)
    return formatted, int(len(non_null) - valid_after)


def _try_parse_boolean(series: pd.Series) -> pd.Series | None:
    """Normalize clear boolean columns to 1/0 integers or True/False."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return None
    if pd.api.types.is_bool_dtype(series):
        return series.astype("Int64")

    as_str = non_null.astype(str).str.strip().str.lower()
    unique_vals = set(as_str.unique())
    if len(unique_vals) <= 2 and unique_vals.issubset(BOOL_TRUE | BOOL_FALSE):
        # Avoid turning pure 0/1 numeric ID/count columns unless string true/false/yes/no
        if not unique_vals.issubset({"0", "1"}):
            mapped = series.map(
                lambda v: (
                    1
                    if str(v).strip().lower() in BOOL_TRUE
                    else (0 if str(v).strip().lower() in BOOL_FALSE else np.nan)
                )
                if pd.notna(v)
                else np.nan
            )
            return mapped.astype("Int64")
    return None


def clean_dataset(
    raw_df: pd.DataFrame, options: CleaningOptions | None = None
) -> tuple[pd.DataFrame, CleaningReport]:
    """Run the full automated cleaning pipeline and return cleaned DataFrame + report."""
    opts = options or CleaningOptions()
    if opts.strategy == "minimal":
        opts = CleaningOptions(
            strategy="minimal",
            drop_duplicates=True,
            normalize_columns=True,
            trim_strings=True,
            parse_numeric=False,
            parse_dates=False,
            fill_missing="none",
        )
    elif opts.strategy == "keep_nulls":
        opts.fill_missing = "none"
    elif opts.strategy == "drop_rows":
        opts.fill_missing = "drop_rows"

    df = raw_df.copy()
    orig_rows, orig_cols = df.shape
    orig_missing = _count_missing(df)
    orig_dups = int(df.duplicated().sum()) if orig_rows > 0 else 0
    quality_before = _compute_quality_score(df, orig_missing, orig_dups)

    actions: list[CleaningAction] = []
    warnings: list[str] = []

    # 1. Normalize column names
    column_mapping: dict[str, str] = {}
    if opts.normalize_columns:
        seen: dict[str, int] = {}
        new_cols: list[str] = []
        renamed_count = 0
        for idx, col in enumerate(df.columns):
            base = to_snake_case(str(col), idx)
            if base in seen:
                seen[base] += 1
                unique_col = f"{base}_{seen[base]}"
            else:
                seen[base] = 0
                unique_col = base
            if str(col) != unique_col:
                renamed_count += 1
            column_mapping[str(col)] = unique_col
            new_cols.append(unique_col)
        df.columns = new_cols
        if renamed_count > 0:
            actions.append(
                CleaningAction(
                    step="normalize_columns",
                    description=f"Standardized {renamed_count} column header(s) to SQL-safe snake_case.",
                    affected_count=renamed_count,
                    details={"mapping": column_mapping},
                )
            )
    else:
        column_mapping = {str(c): str(c) for c in df.columns}

    # 2. Trim whitespace and replace null markers
    trimmed_cells = 0
    nullified_cells = 0
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            series = df[col].astype(object)

            def _clean_cell(val: Any) -> Any:
                nonlocal trimmed_cells, nullified_cells
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    return np.nan
                if isinstance(val, str):
                    stripped = re.sub(r"\s+", " ", val.strip())
                    if stripped != val:
                        trimmed_cells += 1
                    if stripped.lower() in NULL_MARKERS:
                        nullified_cells += 1
                        return np.nan
                    return stripped
                return val

            df[col] = series.map(_clean_cell)

    if trimmed_cells > 0:
        actions.append(
            CleaningAction(
                step="trim_whitespace",
                description=f"Trimmed and collapsed irregular whitespace in {trimmed_cells} cell(s).",
                affected_count=trimmed_cells,
            )
        )
    if nullified_cells > 0:
        actions.append(
            CleaningAction(
                step="standardize_nulls",
                description=f"Normalized {nullified_cells} placeholder string(s) (N/A, null, -, etc.) to NULL.",
                affected_count=nullified_cells,
            )
        )

    # 3. Drop completely empty rows and columns
    before_empty_rows = len(df)
    df = df.dropna(how="all").reset_index(drop=True)
    empty_rows_removed = before_empty_rows - len(df)
    if empty_rows_removed > 0:
        actions.append(
            CleaningAction(
                step="remove_empty_rows",
                description=f"Removed {empty_rows_removed} completely empty row(s).",
                affected_count=empty_rows_removed,
            )
        )

    before_empty_cols = df.shape[1]
    empty_col_names = [c for c in df.columns if df[c].isna().all()]
    if empty_col_names:
        df = df.drop(columns=empty_col_names)
    empty_cols_removed = before_empty_cols - df.shape[1]
    if empty_cols_removed > 0:
        actions.append(
            CleaningAction(
                step="remove_empty_columns",
                description=f"Dropped {empty_cols_removed} completely empty column(s): {', '.join(empty_col_names)}.",
                affected_count=empty_cols_removed,
                details={"columns": empty_col_names},
            )
        )

    # 4. Deduplicate rows
    duplicates_removed = 0
    if opts.drop_duplicates and len(df) > 0:
        before_dup = len(df)
        df = df.drop_duplicates().reset_index(drop=True)
        duplicates_removed = before_dup - len(df)
        if duplicates_removed > 0:
            actions.append(
                CleaningAction(
                    step="remove_duplicates",
                    description=f"Removed {duplicates_removed} duplicate row(s).",
                    affected_count=duplicates_removed,
                )
            )

    # 5. Smart type inference (numeric, currency, percentage, dates, booleans)
    detected_types: dict[str, str] = {}
    converted_numeric: list[str] = []
    converted_dates: list[str] = []
    converted_bools: list[str] = []

    for col in df.columns:
        col_series = df[col]
        if opts.parse_numeric:
            num_series, bad_count, _ = _try_parse_numeric(col_series)
            if num_series is not None:
                df[col] = num_series
                detected_types[col] = (
                    "integer" if str(num_series.dtype) == "Int64" else "numeric"
                )
                converted_numeric.append(col)
                if bad_count > 0:
                    warnings.append(
                        f"Column '{col}': {bad_count} malformed value(s) became NULL during numeric conversion."
                    )
                continue

        bool_series = _try_parse_boolean(col_series)
        if bool_series is not None:
            df[col] = bool_series
            detected_types[col] = "boolean"
            converted_bools.append(col)
            continue

        if opts.parse_dates:
            dt_series, bad_dates = _try_parse_datetime(col_series, col)
            if dt_series is not None:
                df[col] = dt_series
                detected_types[col] = "date"
                converted_dates.append(col)
                if bad_dates > 0:
                    warnings.append(
                        f"Column '{col}': {bad_dates} unparseable date(s) became NULL."
                    )
                continue

        if pd.api.types.is_integer_dtype(col_series):
            detected_types[col] = "integer"
        elif pd.api.types.is_float_dtype(col_series):
            detected_types[col] = "numeric"
        else:
            detected_types[col] = "text"

    if converted_numeric:
        actions.append(
            CleaningAction(
                step="parse_numeric",
                description=f"Cleaned & converted {len(converted_numeric)} column(s) to numeric types (stripped currency/commas/%): {', '.join(converted_numeric)}.",
                affected_count=len(converted_numeric),
                details={"columns": converted_numeric},
            )
        )
    if converted_dates:
        actions.append(
            CleaningAction(
                step="standardize_dates",
                description=f"Standardized {len(converted_dates)} date column(s) to ISO-8601 format (YYYY-MM-DD): {', '.join(converted_dates)}.",
                affected_count=len(converted_dates),
                details={"columns": converted_dates},
            )
        )
    if converted_bools:
        actions.append(
            CleaningAction(
                step="standardize_booleans",
                description=f"Standardized {len(converted_bools)} boolean column(s) to 1/0: {', '.join(converted_bools)}.",
                affected_count=len(converted_bools),
                details={"columns": converted_bools},
            )
        )

    # 6. Missing value imputation / handling
    filled_cells = 0
    rows_dropped_missing = 0
    if opts.fill_missing == "drop_rows":
        before_drop = len(df)
        df = df.dropna().reset_index(drop=True)
        rows_dropped_missing = before_drop - len(df)
        if rows_dropped_missing > 0:
            actions.append(
                CleaningAction(
                    step="drop_missing_rows",
                    description=f"Dropped {rows_dropped_missing} row(s) containing missing values.",
                    affected_count=rows_dropped_missing,
                )
            )
    elif opts.fill_missing in ("smart", "median_mode"):
        imputed_cols: dict[str, str] = {}
        for col in df.columns:
            na_count = int(df[col].isna().sum())
            if na_count == 0:
                continue
            col_type = detected_types.get(col, "text")
            # Do not impute ID-like or date columns unless explicit
            if col == "id" or col.endswith("_id") or col_type == "date":
                continue
            if col_type in ("integer", "numeric"):
                median_val = df[col].median()
                if pd.notna(median_val):
                    fill_val = int(round(median_val)) if col_type == "integer" else round(float(median_val), 4)
                    df[col] = df[col].fillna(fill_val)
                    filled_cells += na_count
                    imputed_cols[col] = f"median ({fill_val})"
            elif col_type == "boolean":
                mode_series = df[col].mode()
                if not mode_series.empty:
                    fill_val = int(mode_series.iloc[0])
                    df[col] = df[col].fillna(fill_val)
                    filled_cells += na_count
                    imputed_cols[col] = f"mode ({fill_val})"
            else:
                # For low-cardinality categorical text, fill with mode or user placeholder
                non_null_nunique = df[col].dropna().nunique()
                placeholder = opts.fill_text_value if opts.fill_text_value is not None else "Unknown"
                if placeholder and non_null_nunique > 0 and non_null_nunique <= max(15, int(len(df) * 0.25)):
                    df[col] = df[col].fillna(placeholder)
                    filled_cells += na_count
                    imputed_cols[col] = f"'{placeholder}'"

        if filled_cells > 0:
            actions.append(
                CleaningAction(
                    step="impute_missing",
                    description=f"Imputed {filled_cells} missing cell(s) across {len(imputed_cols)} column(s).",
                    affected_count=filled_cells,
                    details={"imputed_columns": imputed_cols},
                )
            )

    # 7. Additional user-specified cleaning rules
    if opts.drop_columns:
        cols_to_drop = [c for c in opts.drop_columns if c in df.columns]
        if cols_to_drop and len(cols_to_drop) < len(df.columns):
            df = df.drop(columns=cols_to_drop)
            for c in cols_to_drop:
                detected_types.pop(c, None)
            actions.append(
                CleaningAction(
                    step="user_drop_columns",
                    description=f"Dropped user-selected column(s): {', '.join(cols_to_drop)}.",
                    affected_count=len(cols_to_drop),
                    details={"columns": cols_to_drop},
                )
            )

    if opts.text_case in ("title", "lower", "upper"):
        cased_cols: list[str] = []
        for col in df.columns:
            if detected_types.get(col) == "text":
                mask = df[col].notna()
                if opts.text_case == "title":
                    df.loc[mask, col] = df.loc[mask, col].astype(str).str.title()
                elif opts.text_case == "lower":
                    df.loc[mask, col] = df.loc[mask, col].astype(str).str.lower()
                elif opts.text_case == "upper":
                    df.loc[mask, col] = df.loc[mask, col].astype(str).str.upper()
                cased_cols.append(col)
        if cased_cols:
            actions.append(
                CleaningAction(
                    step="user_text_case",
                    description=f"Converted {len(cased_cols)} text column(s) to {opts.text_case} case.",
                    affected_count=len(cased_cols),
                )
            )

    if opts.find_text:
        target_cols = (
            [opts.replace_column]
            if opts.replace_column and opts.replace_column in df.columns
            else [c for c in df.columns if detected_types.get(c, "text") == "text"]
        )
        replaced_cells = 0
        for col in target_cols:
            s = df[col]
            mask = s.notna() & s.astype(str).str.contains(opts.find_text, regex=False)
            cnt = int(mask.sum())
            if cnt > 0:
                df.loc[mask, col] = s.loc[mask].astype(str).str.replace(
                    opts.find_text, opts.replace_text or "", regex=False
                )
                replaced_cells += cnt
        if replaced_cells > 0:
            actions.append(
                CleaningAction(
                    step="user_find_replace",
                    description=f"Replaced '{opts.find_text}' -> '{opts.replace_text}' in {replaced_cells} cell(s).",
                    affected_count=replaced_cells,
                )
            )

    if opts.round_decimals is not None and opts.round_decimals >= 0:
        rounded_cols: list[str] = []
        for col in df.columns:
            if detected_types.get(col) == "numeric":
                df[col] = pd.to_numeric(df[col], errors="coerce").round(opts.round_decimals)
                rounded_cols.append(col)
        if rounded_cols:
            actions.append(
                CleaningAction(
                    step="user_round_numeric",
                    description=f"Rounded {len(rounded_cols)} numeric column(s) to {opts.round_decimals} decimal place(s).",
                    affected_count=len(rounded_cols),
                )
            )

    # 7b. Change Data Type
    if opts.dtype_column and opts.dtype_target and opts.dtype_column in df.columns:
        col = opts.dtype_column
        try:
            if opts.dtype_target == "integer":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            elif opts.dtype_target == "float":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
            elif opts.dtype_target == "text":
                df[col] = df[col].astype(str).where(df[col].notna(), None)
            elif opts.dtype_target == "boolean":
                s = df[col].astype(str).str.strip().str.lower()
                df[col] = s.map({"true": True, "1": True, "yes": True, "false": False, "0": False, "no": False})
            elif opts.dtype_target == "date":
                df[col] = pd.to_datetime(df[col], errors="coerce")
            actions.append(
                CleaningAction(
                    step="user_dtype_cast",
                    description=f"Changed column '{col}' data type to {opts.dtype_target}.",
                    affected_count=int(df[col].notna().sum()),
                    details={"column": col, "target_type": opts.dtype_target},
                )
            )
        except Exception:
            pass

    # 7c. Split Column
    if opts.split_column and opts.split_delimiter and opts.split_column in df.columns:
        col = opts.split_column
        max_parts = max(2, opts.split_max_parts)
        try:
            split_df = df[col].astype(str).str.split(
                opts.split_delimiter, n=max_parts - 1, expand=True
            )
            new_cols = []
            for i in range(split_df.shape[1]):
                new_name = f"{col}_{i + 1}"
                df[new_name] = split_df[i]
                new_cols.append(new_name)
            actions.append(
                CleaningAction(
                    step="user_split_column",
                    description=f"Split column '{col}' on '{opts.split_delimiter}' into {len(new_cols)} new column(s): {', '.join(new_cols)}.",
                    affected_count=len(new_cols),
                    details={"source_column": col, "new_columns": new_cols},
                )
            )
        except Exception:
            pass

    # 7d. Extract from Column
    if opts.extract_column and opts.extract_mode and opts.extract_column in df.columns:
        col = opts.extract_column
        out_col = opts.extract_output_col.strip() or f"{col}_extracted"
        try:
            s = df[col].astype(str)
            if opts.extract_mode == "first_chars":
                n = int(opts.extract_param or 1)
                df[out_col] = s.str[:n]
            elif opts.extract_mode == "last_chars":
                n = int(opts.extract_param or 1)
                df[out_col] = s.str[-n:]
            elif opts.extract_mode == "between":
                parts = (opts.extract_param or ",").split(",", 1)
                start, end = parts[0], parts[1] if len(parts) > 1 else parts[0]
                df[out_col] = s.str.extract(
                    re.escape(start) + r"(.*?)" + re.escape(end), expand=False
                )
            elif opts.extract_mode == "digits":
                df[out_col] = s.str.extract(r"(\d+(?:\.\d+)?)", expand=False)
            elif opts.extract_mode == "email":
                df[out_col] = s.str.extract(
                    r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", expand=False
                )
            elif opts.extract_mode == "url":
                df[out_col] = s.str.extract(
                    r"(https?://[^\s]+)", expand=False
                )
            actions.append(
                CleaningAction(
                    step="user_extract_column",
                    description=f"Extracted '{opts.extract_mode}' from '{col}' into new column '{out_col}'.",
                    affected_count=int(df[out_col].notna().sum()) if out_col in df.columns else 0,
                    details={"source_column": col, "mode": opts.extract_mode, "output_column": out_col},
                )
            )
        except Exception:
            pass

    # 7e. Power Query: Filter Rows
    if opts.filter_column and opts.filter_condition and opts.filter_column in df.columns:
        fcol = opts.filter_column
        cond = opts.filter_condition
        val = str(opts.filter_value or "")
        orig_count = len(df)
        try:
            if cond == "equals":
                df = df[df[fcol].astype(str).str.lower() == val.lower()]
            elif cond == "contains":
                df = df[df[fcol].astype(str).str.contains(val, case=False, na=False)]
            elif cond == "not_null":
                df = df[df[fcol].notna() & (df[fcol].astype(str).str.strip() != "")]
            elif cond == "greater_than":
                num_s = pd.to_numeric(df[fcol], errors="coerce")
                cutoff = float(val)
                df = df[num_s > cutoff]
            elif cond == "less_than":
                num_s = pd.to_numeric(df[fcol], errors="coerce")
                cutoff = float(val)
                df = df[num_s < cutoff]

            kept = len(df)
            actions.append(
                CleaningAction(
                    step="user_filter_rows",
                    description=f"Power Query Filter: kept {kept} of {orig_count} rows where '{fcol}' {cond} '{val}'.",
                    affected_count=orig_count - kept,
                    details={"column": fcol, "condition": cond, "value": val},
                )
            )
        except Exception:
            pass

    # 7f. Power Query: Sort Rows
    if opts.sort_column and opts.sort_column in df.columns:
        scol = opts.sort_column
        ascending = opts.sort_direction != "desc"
        try:
            # If numeric or date, sort appropriately
            if detected_types.get(scol) in ("integer", "numeric"):
                df["__sort_tmp__"] = pd.to_numeric(df[scol], errors="coerce")
                df = df.sort_values(by="__sort_tmp__", ascending=ascending).drop(columns=["__sort_tmp__"])
            else:
                df = df.sort_values(by=scol, ascending=ascending)
            actions.append(
                CleaningAction(
                    step="user_sort_rows",
                    description=f"Power Query Sort: sorted by '{scol}' ({'ascending' if ascending else 'descending'}).",
                    affected_count=len(df),
                    details={"column": scol, "direction": opts.sort_direction},
                )
            )
        except Exception:
            pass

    # 7g. Power Query: Rename Column
    if opts.rename_column and opts.rename_to and opts.rename_column in df.columns:
        r_from = opts.rename_column
        r_to = to_snake_case(opts.rename_to.strip(), 0)
        if r_to and r_to != r_from:
            try:
                df = df.rename(columns={r_from: r_to})
                if r_from in detected_types:
                    detected_types[r_to] = detected_types.pop(r_from)
                actions.append(
                    CleaningAction(
                        step="user_rename_column",
                        description=f"Power Query Rename: renamed column '{r_from}' → '{r_to}'.",
                        affected_count=1,
                        details={"from": r_from, "to": r_to},
                    )
                )
            except Exception:
                pass

    # 7h. Power Query: Fill Values (Down / Up)
    if opts.fill_direction_col and opts.fill_direction in ("down", "up") and opts.fill_direction_col in df.columns:
        f_col = opts.fill_direction_col
        method = "ffill" if opts.fill_direction == "down" else "bfill"
        try:
            null_before = int(df[f_col].isna().sum())
            if method == "ffill":
                df[f_col] = df[f_col].ffill()
            else:
                df[f_col] = df[f_col].bfill()
            null_after = int(df[f_col].isna().sum())
            actions.append(
                CleaningAction(
                    step="user_fill_direction",
                    description=f"Power Query Fill: filled values {opts.fill_direction} in '{f_col}' ({null_before - null_after} cells filled).",
                    affected_count=null_before - null_after,
                    details={"column": f_col, "direction": opts.fill_direction},
                )
            )
        except Exception:
            pass

    # Check high-null warnings after cleaning
    for col in df.columns:
        na_pct = float(df[col].isna().mean() * 100) if len(df) > 0 else 0.0
        if na_pct >= 30.0:
            warnings.append(
                f"Column '{col}' still has {na_pct:.1f}% missing (NULL) values."
            )

    cleaned_missing = int(df.isna().sum().sum()) if not df.empty else 0
    quality_after = _compute_quality_score(df, cleaned_missing, 0)

    report = CleaningReport(
        original_rows=orig_rows,
        original_cols=orig_cols,
        cleaned_rows=len(df),
        cleaned_cols=df.shape[1],
        original_missing_cells=orig_missing,
        cleaned_missing_cells=cleaned_missing,
        duplicates_removed=duplicates_removed,
        empty_rows_removed=empty_rows_removed,
        empty_cols_removed=empty_cols_removed,
        column_mapping=column_mapping,
        detected_types=detected_types,
        actions=[asdict(a) for a in actions],
        warnings=warnings,
        quality_score_before=quality_before,
        quality_score_after=quality_after,
    )
    return df, report


def dataframe_preview(df: pd.DataFrame, limit: int = 50) -> dict[str, Any]:
    """Convert head of DataFrame into JSON-safe columns + rows."""
    subset = df.head(limit).copy()
    records: list[dict[str, Any]] = []
    for _, row in subset.iterrows():
        rec: dict[str, Any] = {}
        for col in subset.columns:
            val = row[col]
            if val is None or (isinstance(val, float) and np.isnan(val)) or pd.isna(val):
                rec[str(col)] = None
            elif isinstance(val, (np.integer,)):
                rec[str(col)] = int(val)
            elif isinstance(val, (np.floating,)):
                rec[str(col)] = round(float(val), 6)
            else:
                rec[str(col)] = str(val) if not isinstance(val, (int, float, bool)) else val
        records.append(rec)
    return {
        "columns": [str(c) for c in df.columns],
        "rows": records,
        "total_rows": len(df),
    }
