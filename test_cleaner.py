"""Unit tests for the dataset ingestion and cleaning pipeline."""

import io
import pandas as pd

from app.cleaner import CleaningOptions, clean_dataset, load_dataframe_from_bytes


def test_clean_messy_dataframe():
    raw = pd.DataFrame(
        [
            {"Order ID": "1", " Order Date ": "01/05/2024", "Revenue ($)": "$1,200.50", "Region": "  North ", "EmptyCol": ""},
            {"Order ID": "1", " Order Date ": "01/05/2024", "Revenue ($)": "$1,200.50", "Region": "  North ", "EmptyCol": ""},
            {"Order ID": "2", " Order Date ": "2024-02-14", "Revenue ($)": "$800.00", "Region": "N/A", "EmptyCol": "null"},
            {"Order ID": "", " Order Date ": "", "Revenue ($)": "", "Region": "", "EmptyCol": ""},
            {"Order ID": "3", " Order Date ": "Mar 10, 2024", "Revenue ($)": "null", "Region": "South", "EmptyCol": "-"},
        ]
    )

    cleaned, report = clean_dataset(raw, CleaningOptions(strategy="smart"))

    # Empty row & duplicate row removed (5 -> 3 rows)
    assert report.original_rows == 5
    assert report.cleaned_rows == 3
    assert report.duplicates_removed == 1
    assert report.empty_rows_removed == 1
    assert report.empty_cols_removed == 1

    # Column normalization
    assert "order_id" in cleaned.columns
    assert "order_date" in cleaned.columns
    assert "revenue" in cleaned.columns
    assert "empty_col" not in cleaned.columns

    # Currency parsed & missing value imputed with median
    assert report.detected_types["revenue"] == "numeric"
    assert cleaned["revenue"].isna().sum() == 0

    # Dates normalized to ISO-8601
    assert report.detected_types["order_date"] == "date"
    assert list(cleaned["order_date"]) == ["2024-01-05", "2024-02-14", "2024-03-10"]

    # Quality score improved
    assert report.quality_score_after >= report.quality_score_before


def test_keep_nulls_strategy():
    raw = pd.DataFrame(
        [
            {"Name": "Alice", "Score": "90"},
            {"Name": "Bob", "Score": "N/A"},
        ]
    )
    cleaned, report = clean_dataset(raw, CleaningOptions(strategy="keep_nulls"))
    assert pd.isna(cleaned.loc[1, "score"])
    assert report.cleaned_missing_cells == 1


def test_drop_rows_strategy():
    raw = pd.DataFrame(
        [
            {"Name": "Alice", "Score": "90"},
            {"Name": "Bob", "Score": "N/A"},
        ]
    )
    cleaned, report = clean_dataset(raw, CleaningOptions(strategy="drop_rows"))
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["name"] == "Alice"


def test_load_csv_and_excel_bytes():
    csv_bytes = b"Name,Amount\nAlice,$50\nBob,$75\n"
    df_csv = load_dataframe_from_bytes("test.csv", csv_bytes)
    assert len(df_csv) == 2

    buf = io.BytesIO()
    df_csv.to_excel(buf, index=False)
    df_xlsx = load_dataframe_from_bytes("test.xlsx", buf.getvalue())
    assert len(df_xlsx) == 2
