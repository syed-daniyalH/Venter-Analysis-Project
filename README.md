# Venter Analysis Pipeline

## Overview

Venter Analysis Pipeline is a Python data-processing project for multilingual vendor and product-catalog data. It converts a noisy workbook into cleaner, analysis-ready Excel and CSV outputs while preserving the original source file and making the transformation logic reusable through a proper Python package and command-line script.

## Key Features

- Bilingual data cleanup for Arabic and English catalog content
- Currency normalization from IQD to PKR
- Reusable pipeline logic in `venter_analysis/`
- Command-line processing script for repeatable runs
- Workbook and CSV export generation without overwriting the source
- Matched and unmatched collection reporting
- Automated tests for the reusable pipeline

## Tech Stack

- Python
- pandas
- NumPy
- openpyxl

## Business Use Case

This project is useful for data-management, reporting, and business-automation workflows where multilingual vendor exports need cleaning, normalization, merging, and structured reporting before they can be used by operations or analysis teams.

## Current Data Snapshot

The bundled workbook in `Vender Analysis/Venter_Analysis.xlsx` contains the processed snapshot used in this repository.

| Metric | Value |
| --- | ---: |
| Items rows | 24,702 |
| Collections rows | 14,486 |
| Merged rows | 39,188 |
| Matched collection rows | 14,486 |
| Matched collection rate | 100% |
| IQD to PKR conversion rate | 0.2153927 |

## Setup

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run the pipeline:

```bash
python scripts/process_venter_analysis.py --verbose
```

Use a custom input workbook if needed:

```bash
python scripts/process_venter_analysis.py --input "Vender Analysis/Venter_Analysis.xlsx" --output-dir outputs
```

## Outputs

The pipeline writes processed exports such as:

- `outputs/Venter_Analysis_processed.xlsx`
- `outputs/Venter_Analysis_merged.csv`

It also generates workbook tabs for `Items`, `Collections`, `Merged`, `Matched_Collections`, `Unmatched_Collections`, and `Summary`.

## Project Status

Stable data-processing project with a clear improvement path from notebook exploration to reusable Python workflow. The current repository already presents well as a business-focused data-engineering project.

## Future Improvements

- Config-driven exchange-rate and column-mapping support
- Additional validation and malformed-data reporting
- Logging and audit output for batch runs
- Dashboard or visualization layer for summary reporting

## Developer Credit

- GitHub: [syed-daniyalH](https://github.com/syed-daniyalH)
