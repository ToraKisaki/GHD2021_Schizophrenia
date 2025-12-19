#!/usr/bin/env python3
"""
Split the IHME GBD 2023 schizophrenia extract into year-specific CSV files.

The script reads the (potentially large) CSV once, then writes one file per
`year` into `GDB_2023/` (or a directory provided via ``--output-dir``).
Each output file preserves the original header and contains only the rows
for its respective year, e.g.:

    GDB_2023/IHME-GBD_2023_DATA-52b88409-1_year_1990.csv

Usage
-----
    python split_gbd_2023.py \
        --source IHME-GBD_2023_DATA-52b88409-1.csv \
        --output-dir GDB_2023
"""

from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path
from typing import Dict, Iterable, Optional, TextIO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split the GBD 2023 CSV by year.")
    parser.add_argument(
        "--source",
        default="IHME-GBD_2023_DATA-52b88409-1.csv",
        help="Path to the IHME GBD 2023 CSV extract.",
    )
    parser.add_argument(
        "--output-dir",
        default="GDB_2023",
        help="Directory that will receive the year-specific CSV files.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8-sig",
        help="Encoding of the source file (default handles UTF-8 with BOM).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logs.",
    )
    return parser.parse_args()


def ensure_header(reader: csv.DictReader) -> Iterable[str]:
    """Return the header row and validate the presence of the year field."""
    header = reader.fieldnames or []
    if not header:
        raise ValueError("The source CSV is missing a header row.")
    if "year" not in header and "year_id" not in header:
        raise ValueError("No 'year' or 'year_id' column found in the CSV header.")
    return header


def open_writer(
    year: str,
    header: Iterable[str],
    output_dir: Path,
    source_stem: str,
) -> tuple[csv.DictWriter, TextIO, Path]:
    """Create a writer for the given year."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target_path = output_dir / f"{source_stem}_year_{year}.csv"
    handle = target_path.open("w", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=header)
    writer.writeheader()
    return writer, handle, target_path


def split_by_year(source_path: Path, output_dir: Path, encoding: str = "utf-8-sig") -> Dict[str, int]:
    """
    Stream the CSV once and write year-specific files.

    Returns
    -------
    Dict[str, int]
        Mapping from year to the number of rows written for that year.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Source CSV not found: {source_path}")

    writers: Dict[str, csv.DictWriter] = {}
    handles: Dict[str, TextIO] = {}
    counts: Dict[str, int] = {}

    with source_path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.DictReader(handle)
        header = ensure_header(reader)
        source_stem = source_path.stem

        for idx, row in enumerate(reader, start=1):
            year_value: Optional[str] = row.get("year") or row.get("year_id")
            if not year_value:
                logging.debug("Skipping row %s with missing year", idx)
                continue
            year = str(year_value).strip()
            if not year:
                logging.debug("Skipping row %s with blank year", idx)
                continue

            if year not in writers:
                writer, file_handle, target_path = open_writer(year, header, output_dir, source_stem)
                writers[year] = writer
                handles[year] = file_handle
                logging.info("Writing %s", target_path)

            writers[year].writerow(row)
            counts[year] = counts.get(year, 0) + 1

    for handle in handles.values():
        handle.close()
    return counts


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")

    source_path = Path(args.source)
    output_dir = Path(args.output_dir)
    counts = split_by_year(source_path, output_dir, encoding=args.encoding)

    total_rows = sum(counts.values())
    logging.info("Processed %s rows into %s year files.", total_rows, len(counts))
    print("Year-wise row counts:")
    for year in sorted(counts):
        print(f"  {year}: {counts[year]} rows")


if __name__ == "__main__":
    main()
