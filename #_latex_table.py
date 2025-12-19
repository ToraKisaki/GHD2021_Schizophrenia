#!/usr/bin/env python3
"""
Generate the LaTeX tables that summarise incidence and DALYs results.

The script scans the available IHME CSV extracts, pulls the requested
metrics for each table row (Global, Sex, SDI buckets, and GBD regions),
computes EAPC values from the age-standardised rates, and writes a `.tex`
file that mirrors the structure of `table.tex`.

Examples
--------
Generate `table_generated.tex` using the default CSV inputs:

    python #_latex_table.py

Write to a custom path and include extra CSV sources:

    python #_latex_table.py --output results/new_table.tex \\
        --sources IHME-GBD_2021_DATA-575f1e63-1.csv Schiz/IHME-GBD_2021_DATA-851501aa-*.csv \\
        --category-map region_members.json
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist
from textwrap import dedent
from typing import Dict, Iterable, List, Optional, Tuple


MeasureData = Dict[str, Dict[str, Dict[int, Tuple[float, float, float]]]]


def default_sources() -> List[Path]:
    """Return every CSV file that is tracked in the repository."""
    repo_root = Path(".")
    csv_paths = sorted(
        path for path in repo_root.rglob("*.csv") if path.is_file()
    )
    return csv_paths


def baseline_category_specs() -> Dict[str, Dict[str, Iterable[Dict[str, str]]]]:
    """Build the default category definitions."""
    region_names_part1 = [
        "Andean Latin America",
        "Australasia",
        "Caribbean",
        "Central Asia",
        "Central Europe",
        "Central Latin America",
        "Central Sub-Saharan Africa",
        "East Asia",
        "Eastern Europe",
        "Eastern Sub-Saharan Africa",
    ]
    region_names_part2 = [
        "High-income Asia Pacific",
        "High-income North America",
        "North Africa and Middle East",
        "Oceania",
        "South Asia",
        "Southeast Asia",
        "Southern Latin America",
        "Southern Sub-Saharan Africa",
        "Tropical Latin America",
        "Western Europe",
        "Western Sub-Saharan Africa",
    ]

    specs: Dict[str, Dict[str, Iterable[Dict[str, str]]]] = {
        "global": {"members": [{"location": "Global", "sex": "Both"}]},
        "sex_male": {"members": [{"location": "Global", "sex": "Male"}]},
        "sex_female": {"members": [{"location": "Global", "sex": "Female"}]},
        "sdi_high": {"members": [{"location": "High SDI", "sex": "Both"}]},
        "sdi_high_middle": {"members": [{"location": "High-middle SDI", "sex": "Both"}]},
        "sdi_middle": {"members": [{"location": "Middle SDI", "sex": "Both"}]},
        "sdi_low_middle": {"members": [{"location": "Low-middle SDI", "sex": "Both"}]},
        "sdi_low": {"members": [{"location": "Low SDI", "sex": "Both"}]},
    }

    for idx, name in enumerate(region_names_part1 + region_names_part2, start=1):
        key = f"region_{idx}"
        specs[key] = {"members": [{"location": name, "sex": "Both"}]}
    return specs


def load_category_specs(custom_path: Optional[Path]) -> Dict[str, Dict[str, Iterable[Dict[str, str]]]]:
    """Merge the baseline category specs with optional overrides."""
    specs = baseline_category_specs()
    if custom_path and custom_path.exists():
        with custom_path.open(encoding="utf-8") as handle:
            overrides = json.load(handle)
        for key, value in overrides.items():
            specs[key] = value
    return specs


def safe_float(value: str) -> Optional[float]:
    """Convert a string to float, returning None if it is blank."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def new_measure_bucket() -> Dict[str, Dict]:
    """Create an empty storage bucket for a single measure."""
    return {
        "cases": {},
        "asr": {},
        "series": {},
        "eapc": None,
    }


def init_measurements(category_specs: Dict[str, Dict[str, Iterable[Dict[str, str]]]]) -> Dict[str, Dict[str, Dict]]:
    """Prepare the nested measurement dictionary."""
    measurements: Dict[str, Dict[str, Dict]] = {}
    for key in category_specs:
        measurements[key] = {
            "incidence": new_measure_bucket(),
            "dalys": new_measure_bucket(),
        }
    return measurements


def build_member_index(category_specs: Dict[str, Dict[str, Iterable[Dict[str, str]]]]) -> Dict[Tuple[str, str], List[str]]:
    """Map (location, sex) combinations back to the target categories."""
    lookup: Dict[Tuple[str, str], List[str]] = defaultdict(list)
    for key, spec in category_specs.items():
        for member in spec.get("members", []):
            location = member.get("location")
            sex = member.get("sex", "Both")
            if not location:
                continue
            lookup[(location, sex)].append(key)
    return lookup


def parse_sources(
    csv_paths: List[Path],
    category_specs: Dict[str, Dict[str, Iterable[Dict[str, str]]]],
) -> Dict[str, Dict[str, Dict]]:
    """Populate the measurement dictionary from all CSV sources."""
    measurements = init_measurements(category_specs)
    member_index = build_member_index(category_specs)
    if not member_index:
        logging.error("No category members defined. Check the category map.")
        return measurements

    for csv_path in csv_paths:
        if not csv_path.exists():
            logging.warning("Skipping missing source %s", csv_path)
            continue
        logging.info("Reading %s", csv_path)
        with csv_path.open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if row.get("cause_name") and row["cause_name"] != "Schizophrenia":
                    continue
                location = row.get("location_name")
                sex = row.get("sex_name", "Both")
                matched_keys = member_index.get((location, sex))
                if not matched_keys:
                    continue

                measure_raw = row.get("measure_name", "")
                if measure_raw.startswith("Incidence"):
                    measure_key = "incidence"
                elif measure_raw.startswith("DALYs"):
                    measure_key = "dalys"
                else:
                    continue

                metric = row.get("metric_name")
                age = row.get("age_name", "")
                year_str = row.get("year")
                val = safe_float(row.get("val"))
                upper = safe_float(row.get("upper"))
                lower = safe_float(row.get("lower"))

                if None in (year_str, val, upper, lower):
                    continue
                try:
                    year = int(year_str)
                except ValueError:
                    continue

                bucket = measurements
                for cat_key in matched_keys:
                    cat_bucket = bucket[cat_key][measure_key]
                    if metric == "Number" and age.lower() == "all ages":
                        cat_bucket["cases"][year] = (val, lower, upper)
                    elif metric == "Rate" and age == "Age-standardized":
                        cat_bucket["asr"][year] = (val, lower, upper)
                        if val > 0:
                            cat_bucket["series"][year] = val
    compute_eapc_values(measurements)
    return measurements


def compute_eapc_values(measurements: Dict[str, Dict[str, Dict]]) -> None:
    """Compute EAPC for each category/measure combination."""
    dist = NormalDist()
    for measure_by_category in measurements.values():
        for measure_bucket in measure_by_category.values():
            series_map = measure_bucket["series"]
            if len(series_map) < 2:
                continue
            points = sorted((year, value) for year, value in series_map.items() if value > 0)
            if len(points) < 2:
                continue

            years = [p[0] for p in points]
            rates = [p[1] for p in points]
            log_rates = [math.log(rate) for rate in rates]
            mean_year = sum(years) / len(years)
            mean_log = sum(log_rates) / len(log_rates)

            s_xx = sum((year - mean_year) ** 2 for year in years)
            if s_xx == 0:
                continue
            s_xy = sum((year - mean_year) * (log_rate - mean_log) for year, log_rate in zip(years, log_rates))
            slope = s_xy / s_xx
            intercept = mean_log - slope * mean_year

            fitted = [slope * year + intercept for year in years]
            residuals = [obs - fit for obs, fit in zip(log_rates, fitted)]
            dof = len(points) - 2
            if dof <= 0:
                continue
            se = math.sqrt(sum(res ** 2 for res in residuals) / dof)
            slope_se = se / math.sqrt(s_xx)
            t_crit = dist.inv_cdf(0.975)

            eapc = (math.exp(slope) - 1.0) * 100.0
            lower = (math.exp(slope - t_crit * slope_se) - 1.0) * 100.0
            upper = (math.exp(slope + t_crit * slope_se) - 1.0) * 100.0

            measure_bucket["eapc"] = (eapc, lower, upper)


def format_ci(entry: Optional[Tuple[float, float, float]], scale: float = 1.0) -> str:
    """Format a value and CI into the `\\valrng` latex macro."""
    if not entry:
        return "--"
    value, lower, upper = entry
    return f"\\valrng{{{value * scale:.2f}}}{{{lower * scale:.2f}-{upper * scale:.2f}}}"


def format_eapc(entry: Optional[Tuple[float, float, float]]) -> str:
    """Format the EAPC triple."""
    if not entry:
        return "--"
    value, lower, upper = entry
    low, high = sorted((lower, upper))
    return f"\\valrng{{{value:.3f}}}{{{low:.3f} \\text{{ to }} {high:.3f}}}"


def render_label(label: str, indent: int = 0) -> str:
    """Indent labels with `\\hspace` when needed."""
    if indent <= 0:
        return label
    return f"\\hspace{{{indent}em}}{label}"


def build_table_rows(
    layout: List[Dict[str, str]],
    measurements: Dict[str, Dict[str, Dict]],
    case_scale: float,
) -> str:
    """Build the row block for a single table body."""
    lines: List[str] = []
    for node in layout:
        kind = node["type"]
        if kind == "midrule":
            lines.append("\\midrule")
            continue
        if kind == "section":
            lines.append(f"\\multicolumn{{11}}{{@{{}}l}}{{\\textbf{{{node['label']}}}}} \\\\")
            continue
        if kind == "continued":
            lines.append("\\multicolumn{11}{r}{\\textit{(Continued)}} \\\\")
            lines.append("\\bottomrule")
            continue

        key = node["key"]
        label = render_label(node["label"], node.get("indent", 0))
        inc_data = measurements.get(key, {}).get("incidence", {})
        daly_data = measurements.get(key, {}).get("dalys", {})

        inc_cases_1990 = format_ci(inc_data.get("cases", {}).get(1990), case_scale)
        inc_asr_1990 = format_ci(inc_data.get("asr", {}).get(1990))
        inc_cases_2021 = format_ci(inc_data.get("cases", {}).get(2021), case_scale)
        inc_asr_2021 = format_ci(inc_data.get("asr", {}).get(2021))
        inc_eapc = format_eapc(inc_data.get("eapc"))

        daly_cases_1990 = format_ci(daly_data.get("cases", {}).get(1990), case_scale)
        daly_asr_1990 = format_ci(daly_data.get("asr", {}).get(1990))
        daly_cases_2021 = format_ci(daly_data.get("cases", {}).get(2021), case_scale)
        daly_asr_2021 = format_ci(daly_data.get("asr", {}).get(2021))
        daly_eapc = format_eapc(daly_data.get("eapc"))

        line = " & ".join(
            [
                label,
                inc_cases_1990,
                inc_asr_1990,
                inc_cases_2021,
                inc_asr_2021,
                inc_eapc,
                daly_cases_1990,
                daly_asr_1990,
                daly_cases_2021,
                daly_asr_2021,
                daly_eapc,
            ]
        )
        lines.append(f"{line} \\\\")
    return "\n".join(lines)


TABLE_ONE_LAYOUT = [
    {"type": "row", "key": "global", "label": "Global"},
    {"type": "midrule"},
    {"type": "section", "label": "Sex"},
    {"type": "row", "key": "sex_male", "label": "Male", "indent": 1},
    {"type": "row", "key": "sex_female", "label": "Female", "indent": 1},
    {"type": "midrule"},
    {"type": "section", "label": "Socio-demographic index"},
    {"type": "row", "key": "sdi_high", "label": "High SDI", "indent": 1},
    {"type": "row", "key": "sdi_high_middle", "label": "High-middle SDI", "indent": 1},
    {"type": "row", "key": "sdi_middle", "label": "Middle SDI", "indent": 1},
    {"type": "row", "key": "sdi_low_middle", "label": "Low-middle SDI", "indent": 1},
    {"type": "row", "key": "sdi_low", "label": "Low SDI", "indent": 1},
    {"type": "midrule"},
    {"type": "section", "label": "Region"},
]


TABLE_TWO_LAYOUT: List[Dict[str, str]] = [
    {"type": "section", "label": "Region"},
]


def extend_region_layouts() -> None:
    """Populate the region entries across the two tables."""
    region_labels = [
        "Andean Latin America",
        "Australasia",
        "Caribbean",
        "Central Asia",
        "Central Europe",
        "Central Latin America",
        "Central Sub-Saharan Africa",
        "East Asia",
        "Eastern Europe",
        "Eastern Sub-Saharan Africa",
        "High-income Asia Pacific",
        "High-income North America",
        "North Africa and Middle East",
        "Oceania",
        "South Asia",
        "Southeast Asia",
        "Southern Latin America",
        "Southern Sub-Saharan Africa",
        "Tropical Latin America",
        "Western Europe",
        "Western Sub-Saharan Africa",
    ]
    for idx, label in enumerate(region_labels, start=1):
        node = {"type": "row", "key": f"region_{idx}", "label": label, "indent": 1}
        if idx <= 10:
            TABLE_ONE_LAYOUT.append(node)
        else:
            TABLE_TWO_LAYOUT.append(node)
    TABLE_ONE_LAYOUT.append({"type": "continued"})


extend_region_layouts()


TABLE_HEADER = dedent(
    r"""
    % Auto-generated ARIMA summary table
    \begin{landscape}
    \begin{table}[htbp]
    \centering
    \caption{The incident cases and DALYs and their age-standardised rate of schizophrenia in 1990 and 2021, and their temporal trends from 1990 to 2021}
    \label{tab:schizophrenia_data}
    \footnotesize
    \setlength{\tabcolsep}{4pt}
    \renewcommand{\arraystretch}{1.25}
    \begin{tabularx}{24cm}{@{}l*{10}{l}@{}}
    \toprule
    & \multicolumn{5}{c}{\textbf{Incidence}} & \multicolumn{5}{c}{\textbf{DALYs}} \\
    \cmidrule(lr){2-6} \cmidrule(lr){7-11}
    \textbf{Category} &
      \textbf{\shortstack{Cases in 1990 \\ \tiny{(No. $\times 10^3$)}}} &
      \textbf{\shortstack{ASR in 1990 \\ \tiny{(per 100,000 persons)}}} &
      \textbf{\shortstack{Cases in 2021 \\ \tiny{(No. $\times 10^3$)}}} &
      \textbf{\shortstack{ASR in 2021 \\ \tiny{(per 100,000 persons)}}} &
      \textbf{EAPC} &
      \textbf{\shortstack{Cases in 1990 \\ \tiny{(No. $\times 10^3$)}}} &
      \textbf{\shortstack{ASR in 1990 \\ \tiny{(per 100,000 persons)}}} &
      \textbf{\shortstack{Cases in 2021 \\ \tiny{(No. $\times 10^3$)}}} &
      \textbf{\shortstack{ASR in 2021 \\ \tiny{(per 100,000 persons)}}} &
      \textbf{EAPC} \\
    \midrule
    """
).strip()


TABLE_FOOTER = dedent(
    r"""
    \end{tabularx}
    \end{table}
    \end{landscape}
    """
).strip()


def render_tables(measurements: Dict[str, Dict[str, Dict]]) -> str:
    """Render both table blocks."""
    case_scale = 1 / 1000.0
    table_one_rows = build_table_rows(TABLE_ONE_LAYOUT, measurements, case_scale)
    table_two_rows = build_table_rows(TABLE_TWO_LAYOUT, measurements, case_scale)

    parts = [
        TABLE_HEADER,
        table_one_rows,
        TABLE_FOOTER,
        TABLE_HEADER,
        table_two_rows,
        TABLE_FOOTER,
    ]
    return "\n".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the schizophrenia LaTeX table.")
    parser.add_argument(
        "--output",
        default="table_generated.tex",
        help="Path to the .tex file that will be created.",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        help="Optional list of CSV sources. Wildcards are expanded by the shell.",
    )
    parser.add_argument(
        "--category-map",
        type=Path,
        help="Optional JSON file that overrides the default category/member mapping.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s: %(message)s")

    source_paths: List[Path]
    if args.sources:
        source_paths = [Path(path) for path in args.sources]
    else:
        source_paths = default_sources()

    category_specs = load_category_specs(args.category_map)
    measurements = parse_sources(source_paths, category_specs)
    rendered = render_tables(measurements)
    output_path = Path(args.output)
    output_path.write_text(rendered + "\n", encoding="utf-8")
    logging.info("Wrote %s", output_path)


if __name__ == "__main__":
    main()
