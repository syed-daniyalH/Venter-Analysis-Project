from __future__ import annotations

import math

import pandas as pd

from venter_analysis.pipeline import (
    build_merged_frame,
    build_match_report,
    build_summary,
    attach_price_columns,
    combine_text_columns,
    clean_collections,
    parse_price_iqd,
)


def test_combine_text_columns_merges_values_and_drops_source_column() -> None:
    frame = pd.DataFrame(
        {
            "left": ["Alpha", None, ""],
            "right": ["Beta", "Gamma", None],
        }
    )

    result = combine_text_columns(frame, "left", "right")

    assert result.columns.tolist() == ["left"]
    assert result["left"].tolist() == ["Alpha - Beta", "Gamma", ""]


def test_parse_price_iqd_strips_currency_text() -> None:
    series = pd.Series(["25,000د.ع", "300,000د.ع", None])

    result = parse_price_iqd(series)

    assert result.iloc[0] == 25000
    assert result.iloc[1] == 300000
    assert math.isnan(result.iloc[2])


def test_build_match_report_filters_collection_rows() -> None:
    items = pd.DataFrame({"Id": [1, 2], "Name": ["A", "B"]})
    collections = pd.DataFrame({"Item Id": [1, 3], "Item Name": ["A 1", "C 1"]})

    result = build_match_report(items, collections)

    assert result["Item Id"].tolist() == [1]


def test_build_summary_reports_counts() -> None:
    items = pd.DataFrame({"Id": [1, 2]})
    collections = pd.DataFrame({"Item Id": [1, 2]})
    merged = build_merged_frame(items, collections)
    matched = build_match_report(items, collections)
    unmatched = collections.iloc[0:0].copy()

    summary = build_summary(items, collections, merged, matched, unmatched, 0.2153927)
    summary_map = dict(zip(summary["Metric"], summary["Value"]))

    assert summary_map["Items rows"] == 2
    assert summary_map["Collections rows"] == 2
    assert summary_map["Matched collections rows"] == 2
    assert summary_map["Matched collections rate (%)"] == 100.0


def test_clean_collections_keeps_catalog_text_tight_and_drops_ui_columns() -> None:
    frame = pd.DataFrame(
        {
            "Item Id": [1],
            "Item Name": ["Mascara"],
            "Secondary Item Name": ["Mascara"],
            "Color": ["Black"],
            "Secondary Color": ["EN"],
            "Price": ["25,000د.ع"],
            "Picture": ["image.png"],
            "Is Active": [True],
        }
    )

    result = clean_collections(frame, 0.2153927)

    assert result["Item Name"].iloc[0] == "MascaraBlack"
    assert result["Secondary Item Name"].iloc[0] == "MascaraEN"
    assert "Picture" not in result.columns
    assert "Is Active" not in result.columns


def test_attach_price_columns_falls_back_to_raw_price_text() -> None:
    frame = pd.DataFrame(
        {
            "Price": ["25,000د.ع", "30,000د.ع"],
            "Price_IQD": [None, 40000],
        }
    )

    result = attach_price_columns(frame, 0.2153927)

    assert result["Price_IQD"].tolist() == [25000, 40000]
    assert result["Price_PKR"].tolist()[0] == 25000 * 0.2153927
