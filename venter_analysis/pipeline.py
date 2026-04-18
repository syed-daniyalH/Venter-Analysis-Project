"""Reusable data processing pipeline for the Venter Analysis project."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONVERSION_RATE = 0.2153927
DEFAULT_INPUT_FILE = PROJECT_ROOT / "Vender Analysis" / "Venter_Analysis.xlsx"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs"
ITEMS_SHEET_NAME = "Items"
COLLECTIONS_SHEET_NAME = "Collections"
MERGED_SHEET_NAME = "Merged"
MATCHED_SHEET_NAME = "Matched_Collections"
UNMATCHED_SHEET_NAME = "Unmatched_Collections"
SUMMARY_SHEET_NAME = "Summary"
MERGED_CSV_SUFFIX = "_merged.csv"
PROCESSED_XLSX_SUFFIX = "_processed.xlsx"

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PipelineResult:
    """Container for the cleaned data frames produced by the pipeline."""

    items: pd.DataFrame
    collections: pd.DataFrame
    merged: pd.DataFrame
    matched_collections: pd.DataFrame
    unmatched_collections: pd.DataFrame
    summary: pd.DataFrame


def _resolve_sheet_name(sheet_names: Sequence[str], target_name: str) -> str:
    """Return the sheet name that matches ``target_name`` ignoring case."""

    for sheet_name in sheet_names:
        if sheet_name.casefold() == target_name.casefold():
            return sheet_name
    available = ", ".join(sheet_names)
    raise ValueError(f"Could not find '{target_name}' in workbook sheets: {available}")


def _clean_text(series: pd.Series) -> pd.Series:
    """Normalize a text series into trimmed strings with empty values preserved."""

    return series.fillna("").astype(str).str.strip()


def combine_text_columns(
    frame: pd.DataFrame,
    left_column: str,
    right_column: str,
    separator: str = " - ",
) -> pd.DataFrame:
    """Merge two text columns into the left column and drop the right column.

    The function is intentionally defensive: if either column is missing, the
    input frame is returned unchanged. This keeps the pipeline idempotent, so it
    can run on both raw and already-processed workbooks.
    """

    if left_column not in frame.columns or right_column not in frame.columns:
        return frame

    result = frame.copy()
    left = _clean_text(result[left_column])
    right = _clean_text(result[right_column])

    combined = left.copy()
    both_present = left.ne("") & right.ne("")
    right_only = left.eq("") & right.ne("")

    combined.loc[both_present] = left.loc[both_present] + separator + right.loc[both_present]
    combined.loc[right_only] = right.loc[right_only]

    result[left_column] = combined
    result = result.drop(columns=[right_column])
    return result


def normalize_integer_column(frame: pd.DataFrame, column_name: str) -> pd.DataFrame:
    """Convert an identifier column to nullable integers when the column exists."""

    if column_name not in frame.columns:
        return frame

    result = frame.copy()
    numeric = pd.to_numeric(result[column_name], errors="coerce")
    result[column_name] = numeric.round().astype("Int64")
    return result


def parse_price_iqd(series: pd.Series) -> pd.Series:
    """Convert IQD price strings such as ``25,000د.ع`` into numeric values."""

    cleaned = _clean_text(series)
    cleaned = cleaned.str.replace("د.ع", "", regex=False)
    cleaned = cleaned.str.replace(",", "", regex=False)
    cleaned = cleaned.str.replace(" ", "", regex=False)
    cleaned = cleaned.str.replace(r"[^\d.]", "", regex=True)
    cleaned = cleaned.replace("", pd.NA)
    return pd.to_numeric(cleaned, errors="coerce")


def attach_price_columns(frame: pd.DataFrame, conversion_rate: float) -> pd.DataFrame:
    """Ensure the frame has numeric IQD and PKR price columns."""

    result = frame.copy()
    price_from_existing = None
    price_from_raw = None

    if "Price_IQD" in result.columns:
        price_from_existing = pd.to_numeric(result["Price_IQD"], errors="coerce")
    elif "Price" in result.columns:
        price_from_existing = pd.Series(index=result.index, dtype="float64")

    if "Price" in result.columns:
        price_from_raw = parse_price_iqd(result["Price"])

    if price_from_existing is None and price_from_raw is None:
        result["Price_IQD"] = pd.NA
    elif price_from_existing is None:
        result["Price_IQD"] = price_from_raw
    elif price_from_raw is None:
        result["Price_IQD"] = price_from_existing
    else:
        result["Price_IQD"] = price_from_existing.combine_first(price_from_raw)

    result["Price_PKR"] = pd.to_numeric(result["Price_IQD"], errors="coerce") * conversion_rate
    return result


def clean_items(items_df: pd.DataFrame, conversion_rate: float) -> pd.DataFrame:
    """Apply the project-specific cleanup rules to the Items sheet."""

    result = items_df.copy()
    result = combine_text_columns(result, "Name", "Brand", separator=" - ")
    result = combine_text_columns(result, "Secondary Name", "Secondary Brand", separator=" - ")
    result = normalize_integer_column(result, "Id")
    result = attach_price_columns(result, conversion_rate)
    result["Sheet"] = ITEMS_SHEET_NAME
    return result


def clean_collections(collections_df: pd.DataFrame, conversion_rate: float) -> pd.DataFrame:
    """Apply the project-specific cleanup rules to the Collections sheet."""

    result = collections_df.copy()
    result = combine_text_columns(result, "Item Name", "Color", separator="")
    result = combine_text_columns(result, "Secondary Item Name", "Secondary Color", separator="")

    drop_candidates = ["Color Code", "Size", "Unit Level", "Code", "Barcode", "Picture", "Is Active"]
    existing_drop_candidates = [column for column in drop_candidates if column in result.columns]
    if existing_drop_candidates:
        result = result.drop(columns=existing_drop_candidates)

    result = normalize_integer_column(result, "Item Id")
    result = attach_price_columns(result, conversion_rate)
    result["Sheet"] = COLLECTIONS_SHEET_NAME
    return result


def build_merged_frame(items_df: pd.DataFrame, collections_df: pd.DataFrame) -> pd.DataFrame:
    """Combine the two cleaned sheets into one analysis-ready table."""

    merged = pd.concat([items_df, collections_df], ignore_index=True, sort=False)
    ordered_columns = list(dict.fromkeys(list(items_df.columns) + list(collections_df.columns)))
    return merged.reindex(columns=ordered_columns)


def build_match_report(items_df: pd.DataFrame, collections_df: pd.DataFrame) -> pd.DataFrame:
    """Return the collection rows that map back to item IDs in the items sheet."""

    if "Item Id" not in collections_df.columns or "Id" not in items_df.columns:
        return collections_df.iloc[0:0].copy()

    item_ids = set(items_df["Id"].dropna().tolist())
    return collections_df[collections_df["Item Id"].isin(item_ids)].copy()


def build_unmatched_report(items_df: pd.DataFrame, collections_df: pd.DataFrame) -> pd.DataFrame:
    """Return collection rows that do not map back to the items sheet."""

    if "Item Id" not in collections_df.columns or "Id" not in items_df.columns:
        return collections_df.copy()

    item_ids = set(items_df["Id"].dropna().tolist())
    return collections_df[~collections_df["Item Id"].isin(item_ids)].copy()


def build_summary(
    items_df: pd.DataFrame,
    collections_df: pd.DataFrame,
    merged_df: pd.DataFrame,
    matched_df: pd.DataFrame,
    unmatched_df: pd.DataFrame,
    conversion_rate: float,
) -> pd.DataFrame:
    """Build a human-readable summary table for the workbook."""

    collections_total = len(collections_df)
    match_rate = (len(matched_df) / collections_total * 100) if collections_total else 0.0

    summary_rows = [
        ("Items rows", len(items_df)),
        ("Collections rows", len(collections_df)),
        ("Merged rows", len(merged_df)),
        ("Matched collections rows", len(matched_df)),
        ("Unmatched collections rows", len(unmatched_df)),
        ("Matched collections rate (%)", round(match_rate, 2)),
        ("Unique item IDs", int(items_df["Id"].nunique(dropna=True)) if "Id" in items_df.columns else 0),
        (
            "Unique collection item IDs",
            int(collections_df["Item Id"].nunique(dropna=True)) if "Item Id" in collections_df.columns else 0,
        ),
        ("IQD to PKR conversion rate", conversion_rate),
    ]

    return pd.DataFrame(summary_rows, columns=["Metric", "Value"])


def load_source_workbook(workbook_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the Items and Collections sheets from the source workbook."""

    excel_file = pd.ExcelFile(workbook_path)
    items_sheet_name = _resolve_sheet_name(excel_file.sheet_names, ITEMS_SHEET_NAME)
    collections_sheet_name = _resolve_sheet_name(excel_file.sheet_names, COLLECTIONS_SHEET_NAME)

    items_df = pd.read_excel(workbook_path, sheet_name=items_sheet_name)
    collections_df = pd.read_excel(workbook_path, sheet_name=collections_sheet_name)
    return items_df, collections_df


def resolve_input_path(input_path: Path) -> Path:
    """Resolve the workbook path, with a fallback to the bundled data folder."""

    if input_path.exists():
        return input_path

    project_relative = PROJECT_ROOT / input_path
    if project_relative.exists():
        return project_relative

    fallback = PROJECT_ROOT / "Vender Analysis" / input_path.name
    if fallback.exists():
        return fallback

    return input_path


def resolve_output_dir(output_dir: Path) -> Path:
    """Resolve the output directory so relative paths stay inside the project."""

    if output_dir.is_absolute():
        return output_dir

    return PROJECT_ROOT / output_dir


def process_workbook(
    input_path: Path | str = DEFAULT_INPUT_FILE,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    conversion_rate: float = DEFAULT_CONVERSION_RATE,
) -> tuple[PipelineResult, Path, Path]:
    """Run the full processing pipeline and persist the generated artifacts."""

    input_path = Path(input_path)
    output_dir = Path(output_dir)
    input_path = resolve_input_path(input_path)
    output_dir = resolve_output_dir(output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_path}")

    raw_items_df, raw_collections_df = load_source_workbook(input_path)
    items_df = clean_items(raw_items_df, conversion_rate)
    collections_df = clean_collections(raw_collections_df, conversion_rate)
    merged_df = build_merged_frame(items_df, collections_df)
    matched_df = build_match_report(items_df, collections_df)
    unmatched_df = build_unmatched_report(items_df, collections_df)
    summary_df = build_summary(items_df, collections_df, merged_df, matched_df, unmatched_df, conversion_rate)

    result = PipelineResult(
        items=items_df,
        collections=collections_df,
        merged=merged_df,
        matched_collections=matched_df,
        unmatched_collections=unmatched_df,
        summary=summary_df,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = output_dir / f"{input_path.stem}{PROCESSED_XLSX_SUFFIX}"
    csv_path = output_dir / f"{input_path.stem}{MERGED_CSV_SUFFIX}"

    with pd.ExcelWriter(workbook_path, engine="openpyxl") as writer:
        result.items.to_excel(writer, sheet_name=ITEMS_SHEET_NAME, index=False)
        result.collections.to_excel(writer, sheet_name=COLLECTIONS_SHEET_NAME, index=False)
        result.merged.to_excel(writer, sheet_name=MERGED_SHEET_NAME, index=False)
        result.matched_collections.to_excel(writer, sheet_name=MATCHED_SHEET_NAME, index=False)
        result.unmatched_collections.to_excel(writer, sheet_name=UNMATCHED_SHEET_NAME, index=False)
        result.summary.to_excel(writer, sheet_name=SUMMARY_SHEET_NAME, index=False)

    result.merged.to_csv(csv_path, index=False, encoding="utf-8-sig")
    return result, workbook_path, csv_path


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the data-processing script."""

    parser = argparse.ArgumentParser(
        description="Process the Venter Analysis workbook into clean, analysis-ready outputs.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help="Path to the source workbook (default: Venter_Analysis.xlsx).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated files (default: outputs/).",
    )
    parser.add_argument(
        "--conversion-rate",
        type=float,
        default=DEFAULT_CONVERSION_RATE,
        help="IQD to PKR conversion rate used for Price_PKR.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print progress messages while the pipeline runs.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by both the script wrapper and package execution."""

    parser = build_argument_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    try:
        result, workbook_path, csv_path = process_workbook(
            input_path=args.input,
            output_dir=args.output_dir,
            conversion_rate=args.conversion_rate,
        )
    except Exception as exc:  # pragma: no cover - surfaced to CLI users
        logger.exception("Processing failed")
        print(f"Processing failed: {exc}")
        return 1

    print(f"Processed workbook: {workbook_path}")
    print(f"Merged CSV: {csv_path}")
    print(
        "Rows -> items: {items}, collections: {collections}, merged: {merged}, matched: {matched}".format(
            items=len(result.items),
            collections=len(result.collections),
            merged=len(result.merged),
            matched=len(result.matched_collections),
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover - convenience for direct execution
    raise SystemExit(main())
