#!/usr/bin/env python3
"""
Generate a LaTeX table comparing algorithms on structured experiments.

Rows: structure patterns (blocks, checkerboard, diagonal, etc.)
Cols: algorithms
Cell: two lines via \\shortstack:
  line 1: compression ratio mean ± stdev (or objective mean ± stdev)
  line 2: (runtime mean ± stdev) s

The compression ratio is computed as: optimal_area / objective^2 (for square objective type).

Options:
- --metric: "compression" (default) or "objective" - which metric to show on top line
- --exclude-algorithms: comma-separated algorithm names to exclude
- --bold-best: bold best values (max compression or min objective, min runtime) per row
- --time-no-std: show only mean time (no ± stdev)
- --aggregate-by: "pattern" (default) or "pattern_size" - how to group data
"""

from __future__ import annotations
import argparse
import math
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set

import pandas as pd


DEFAULT_ALG_ORDER = "cplex,merge_greedy,greedy,stochastic_greedy,beam_search,genetic_greedy,genetic_stochastic"

# Default algorithm name mapping for display in LaTeX
DEFAULT_ALG_NAME_MAP = {
    "cplex": "CPLEX",
    "merge_greedy": "M-Greedy",
    "greedy": "T-Greedy",
    "stochastic_greedy": "ST-Greedy",
    "genetic_greedy": "T-GA",
    "genetic_stochastic": "ST-GA",
    "beam_search": "Beam Search",
}

# Pattern display names
DEFAULT_PATTERN_NAME_MAP = {
    "blocks": "Blocks",
    "checkerboard": "Checkerboard",
    "diagonal": "Diagonal",
    "gradient": "Gradient",
    "qrcode": "QR Code",
    "random": "Random",
    "sparse": "Sparse",
    "dense": "Dense",
    "stripes_h": "Stripes (H)",
    "stripes_v": "Stripes (V)",
}

# Default pattern order
DEFAULT_PATTERN_ORDER = "blocks,checkerboard,diagonal,stripes_h,stripes_v,gradient,sparse,dense,random,qrcode"


def latex_escape(s: str) -> str:
    return (
        s.replace("\\", "\\textbackslash{}")
         .replace("_", "\\_")
         .replace("%", "\\%")
         .replace("&", "\\&")
         .replace("#", "\\#")
         .replace("{", "\\{")
         .replace("}", "\\}")
         .replace("$", "\\$")
    )


def is_bad(x: float) -> bool:
    return x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def fmt_mean_only(mean: float, precision: int, bold: bool = False) -> str:
    """LaTeX math fragment (NO $): mean"""
    if is_bad(mean):
        return ""
    m = f"{mean:.{precision}f}"
    return f"\\mathbf{{{m}}}" if bold else m


def fmt_pm_core(mean: float, std: float, precision: int, bold: bool = False) -> str:
    """
    Return a LaTeX math fragment (NO surrounding $...$):
      mean\\pm std
    If bold=True, bold numbers via \\mathbf{...}.
    """
    if is_bad(mean):
        return ""
    m = f"{mean:.{precision}f}"
    if is_bad(std):
        return f"\\mathbf{{{m}}}" if bold else m

    s = f"{std:.{precision}f}"
    if not bold:
        return f"{m}\\pm{s}"
    return f"\\mathbf{{{m}}}\\pm\\mathbf{{{s}}}"


def parse_csv_list(s: str) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def parse_exclude_list(s: str) -> Set[str]:
    return set(parse_csv_list(s))


def order_items(found_items: List[str], order_csv: str) -> List[str]:
    preferred = [x.lower() for x in parse_csv_list(order_csv)]
    low_to_orig: Dict[str, str] = {}
    for a in found_items:
        al = str(a).lower()
        if al not in low_to_orig:
            low_to_orig[al] = str(a)

    used: Set[str] = set()
    ordered: List[str] = []

    for al in preferred:
        if al in low_to_orig and al not in used:
            ordered.append(low_to_orig[al])
            used.add(al)

    remaining = [low_to_orig[al] for al in low_to_orig.keys() if al not in used]
    remaining.sort(key=lambda x: x.lower())
    ordered.extend(remaining)
    return ordered


def parse_name_map(s: str, defaults: Dict[str, str]) -> Dict[str, str]:
    """Parse comma-separated key=value pairs into a dict."""
    result = defaults.copy()
    if not s:
        return result
    for pair in s.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def get_display_name(name: str, name_map: Dict[str, str]) -> str:
    """Get display name, falling back to original if not mapped."""
    return name_map.get(name, name)


def load_structured_data(base_dir: Path) -> pd.DataFrame:
    """
    Load all results from structured experiment subdirectories.
    Each subdirectory (blocks, checkerboard, etc.) contains all_results.csv.
    """
    all_dfs = []
    
    for pattern_dir in base_dir.iterdir():
        if pattern_dir.is_dir():
            csv_path = pattern_dir / "all_results.csv"
            if csv_path.exists():
                df = pd.read_csv(csv_path)
                if "pattern" not in df.columns:
                    df["pattern"] = pattern_dir.name
                all_dfs.append(df)
    
    if not all_dfs:
        raise ValueError(f"No all_results.csv files found in subdirectories of {base_dir}")
    
    return pd.concat(all_dfs, ignore_index=True)


def aggregate_by_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate results by pattern and algorithm.
    Returns: pattern, algorithm, avg_objective, stdev_objective, avg_runtime, stdev_runtime,
             avg_compression, stdev_compression, avg_optimal_area
    """
    df = df.copy()
    
    # Ensure required columns exist
    required_cols = ["pattern", "algorithm", "objective", "runtime"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Compute compression ratio (area-based: optimal_area / objective²)
    # Always recompute to ensure correct formula is used
    if "optimal_area" in df.columns:
        df["compression_ratio"] = df["optimal_area"] / (df["objective"] ** 2)
    
    gcols = ["pattern", "algorithm"]
    
    # Use named aggregation for clearer column names
    agg_funcs = {
        "avg_objective": ("objective", "mean"),
        "stdev_objective": ("objective", lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0),
        "avg_runtime": ("runtime", "mean"),
        "stdev_runtime": ("runtime", lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0),
    }
    
    if "compression_ratio" in df.columns:
        agg_funcs["avg_compression"] = ("compression_ratio", "mean")
        agg_funcs["stdev_compression"] = ("compression_ratio", lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0)
    
    if "optimal_area" in df.columns:
        agg_funcs["avg_optimal_area"] = ("optimal_area", "mean")
    
    agg = df.groupby(gcols, dropna=False).agg(**agg_funcs).reset_index()
    
    return agg


def aggregate_by_pattern_and_size(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate results by pattern, source size, and algorithm.
    Returns more fine-grained grouping.
    """
    df = df.copy()
    
    # Create size identifier
    if "source_width" in df.columns and "source_height" in df.columns:
        df["size"] = df.apply(lambda r: f"{int(r['source_width'])}x{int(r['source_height'])}", axis=1)
    else:
        df["size"] = "unknown"
    
    df["pattern_size"] = df["pattern"] + " (" + df["size"] + ")"
    
    # Ensure required columns exist
    required_cols = ["pattern_size", "algorithm", "objective", "runtime"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Compute compression ratio (area-based: optimal_area / objective²)
    # Always recompute to ensure correct formula is used
    if "optimal_area" in df.columns:
        df["compression_ratio"] = df["optimal_area"] / (df["objective"] ** 2)
    
    gcols = ["pattern_size", "pattern", "algorithm"]
    
    # Use named aggregation for clearer column names
    agg_funcs = {
        "avg_objective": ("objective", "mean"),
        "stdev_objective": ("objective", lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0),
        "avg_runtime": ("runtime", "mean"),
        "stdev_runtime": ("runtime", lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0),
    }
    
    if "compression_ratio" in df.columns:
        agg_funcs["avg_compression"] = ("compression_ratio", "mean")
        agg_funcs["stdev_compression"] = ("compression_ratio", lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0)
    
    if "optimal_area" in df.columns:
        agg_funcs["avg_optimal_area"] = ("optimal_area", "mean")
    
    agg = df.groupby(gcols, dropna=False).agg(**agg_funcs).reset_index()
    
    return agg


def build_latex_table(
    stats: pd.DataFrame,
    algorithms: List[str],
    row_col: str,  # "pattern" or "pattern_size"
    rows: List[str],
    metric: str,  # "compression" or "objective"
    precision_metric: int,
    precision_time: int,
    table_env: bool = True,
    bold_best: bool = False,
    time_no_std: bool = False,
    alg_name_map: Optional[Dict[str, str]] = None,
    pattern_name_map: Optional[Dict[str, str]] = None,
    separator_after: Optional[str] = None,
) -> str:
    """Build LaTeX table with patterns/sizes as rows and algorithms as columns."""
    
    if alg_name_map is None:
        alg_name_map = DEFAULT_ALG_NAME_MAP
    if pattern_name_map is None:
        pattern_name_map = DEFAULT_PATTERN_NAME_MAP

    # Build index for quick lookup
    idx: Dict[Tuple[str, str], Dict[str, float]] = {}
    for _, r in stats.iterrows():
        key = (str(r[row_col]), str(r["algorithm"]))
        idx[key] = {
            "avg_objective": float(r["avg_objective"]),
            "stdev_objective": float(r["stdev_objective"]),
            "avg_runtime": float(r["avg_runtime"]),
            "stdev_runtime": float(r["stdev_runtime"]),
            "avg_compression": float(r.get("avg_compression", 0)),
            "stdev_compression": float(r.get("stdev_compression", 0)),
        }

    # Determine best values for bolding
    best_metric: Dict[str, Set[str]] = {}
    best_time: Dict[str, Set[str]] = {}
    if bold_best:
        for row in rows:
            vals_metric = {}
            vals_time = {}
            for alg in algorithms:
                k = (row, alg)
                if k in idx:
                    if metric == "compression":
                        vals_metric[alg] = idx[k]["avg_compression"]
                    else:
                        vals_metric[alg] = idx[k]["avg_objective"]
                    vals_time[alg] = idx[k]["avg_runtime"]
            
            # For compression: higher is better; for objective: lower is better
            if metric == "compression":
                best_metric[row] = {a for a, v in vals_metric.items() if v == max(vals_metric.values())} if vals_metric else set()
            else:
                best_metric[row] = {a for a, v in vals_metric.items() if v == min(vals_metric.values())} if vals_metric else set()
            
            best_time[row] = {a for a, v in vals_time.items() if v == min(vals_time.values())} if vals_time else set()

    # Build column specification
    colspec_parts = ["l"]
    separator_idx = None
    if separator_after:
        sep_lower = separator_after.lower()
        for i, alg in enumerate(algorithms):
            if alg.lower() == sep_lower:
                separator_idx = i
                break
    for i in range(len(algorithms)):
        colspec_parts.append("r")
        if separator_idx is not None and i == separator_idx:
            colspec_parts.append("!{\\vrule}")
    colspec = "".join(colspec_parts)

    lines: List[str] = []
    if table_env:
        lines += [
            "\\begin{table}",
            "\\centering",
            "\\small",
        ]

    lines += [
        f"\\begin{{tabular*}}{{\\textwidth}}{{@{{\\extracolsep{{\\fill}}}}{colspec}}}",
        "\\toprule",
    ]

    # Header row
    header = ["\\textbf{Pattern}"] + [f"\\texttt{{{latex_escape(get_display_name(a, alg_name_map))}}}" for a in algorithms]
    lines.append(" & ".join(header) + " \\\\")
    lines.append("\\midrule")

    # Data rows
    for row in rows:
        # Get display name for pattern
        if row_col == "pattern":
            display_name = get_display_name(row, pattern_name_map)
        else:
            # For pattern_size, extract pattern and format nicely
            display_name = row
            for pattern, nice_name in pattern_name_map.items():
                if row.startswith(pattern):
                    display_name = row.replace(pattern, nice_name)
                    break
        
        row_cells = [f"\\shortstack{{{latex_escape(display_name)}\\\\~}}"]
        
        for alg in algorithms:
            k = (row, alg)
            if k not in idx:
                row_cells.append("-")
                continue

            d = idx[k]
            bold_metric_line = bold_best and (alg in best_metric.get(row, set()))
            bold_time_line = bold_best and (alg in best_time.get(row, set()))

            # Top line: metric (compression or objective)
            if metric == "compression":
                metric_core = fmt_pm_core(d["avg_compression"], d["stdev_compression"], precision_metric, bold=bold_metric_line)
            else:
                metric_core = fmt_pm_core(d["avg_objective"], d["stdev_objective"], precision_metric, bold=bold_metric_line)

            # Bottom line: runtime
            if time_no_std:
                time_core = fmt_mean_only(d["avg_runtime"], precision_time, bold=bold_time_line)
            else:
                time_core = fmt_pm_core(d["avg_runtime"], d["stdev_runtime"], precision_time, bold=bold_time_line)

            if not metric_core and not time_core:
                row_cells.append("-")
                continue

            cell = (
                "\\shortstack{"
                f"${metric_core}$"
                "\\\\"
                f"$\\left({time_core}\\mathrm{{s}}\\right)$"
                "}"
            )
            row_cells.append(cell)

        lines.append(" & ".join(row_cells) + " \\\\")
    
    lines += [
        "\\bottomrule",
        "\\end{tabular*}",
    ]

    if table_env:
        if metric == "compression":
            metric_desc = "compression ratio (original\\_area / objective\\textsuperscript{2})"
        else:
            metric_desc = "objective value"
        time_note = "runtime is mean only" if time_no_std else "runtime is mean $\\pm$ std"
        lines += [
            f"\\caption{{Comparison of algorithms on structured patterns. Each cell shows {metric_desc} (top) as mean $\\pm$ std and {time_note} (bottom).}}",
            "\\label{tab:structural-results}",
            "\\end{table}",
        ]

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Generate LaTeX table for structured experiment results")
    ap.add_argument("--dir", default="experiment_structural/structured", 
                    help="Path to structured experiment directory (default: experiment_structural/structured)")
    ap.add_argument("--out", default=None, help="Output .tex file (default: print to stdout)")
    
    ap.add_argument("--metric", choices=["compression", "objective"], default="compression",
                    help="Which metric to show on top line: compression ratio or objective value (default: compression)")
    ap.add_argument("--precision-metric", type=int, default=2, help="Decimal places for metric (default: 2)")
    ap.add_argument("--precision-time", type=int, default=3, help="Decimal places for runtime (default: 3)")
    ap.add_argument("--no-table-env", action="store_true", help="Output only tabular (no table environment)")

    ap.add_argument("--exclude-algorithms", default="", help="Comma-separated algorithm names to exclude")
    ap.add_argument("--bold-best", action="store_true", 
                    help="Bold best values (max compression or min objective, min runtime) per row")
    ap.add_argument("--time-no-std", action="store_true", help="Show only mean runtime (no ± stdev)")

    ap.add_argument("--aggregate-by", choices=["pattern", "pattern_size"], default="pattern",
                    help="How to group data: by pattern only or pattern+size (default: pattern)")

    ap.add_argument("--algorithm-order", default=DEFAULT_ALG_ORDER,
                    help=f"Comma-separated algorithm ordering (default: {DEFAULT_ALG_ORDER})")
    ap.add_argument("--pattern-order", default=DEFAULT_PATTERN_ORDER,
                    help=f"Comma-separated pattern ordering (default: {DEFAULT_PATTERN_ORDER})")
    
    ap.add_argument("--algorithm-names", default="",
                    help="Comma-separated key=value pairs for algorithm display names")
    ap.add_argument("--pattern-names", default="",
                    help="Comma-separated key=value pairs for pattern display names")
    
    ap.add_argument("--separator-after", default="",
                    help="Insert vertical line after this algorithm to separate columns")

    args = ap.parse_args()

    # Load data
    base_dir = Path(args.dir)
    if not base_dir.exists():
        raise FileNotFoundError(f"Directory not found: {base_dir}")
    
    df = load_structured_data(base_dir)
    
    # Aggregate based on grouping mode
    if args.aggregate_by == "pattern":
        stats = aggregate_by_pattern(df)
        row_col = "pattern"
    else:
        stats = aggregate_by_pattern_and_size(df)
        row_col = "pattern_size"
    
    # Filter out excluded algorithms
    excluded = parse_exclude_list(args.exclude_algorithms)
    if excluded:
        stats = stats[~stats["algorithm"].astype(str).isin(excluded)].copy()
    
    # Get ordered algorithms
    found_algs = sorted(stats["algorithm"].astype(str).unique().tolist())
    algorithms = order_items(found_algs, args.algorithm_order)
    
    # Get ordered rows (patterns or pattern_sizes)
    found_rows = sorted(stats[row_col].astype(str).unique().tolist())
    if args.aggregate_by == "pattern":
        rows = order_items(found_rows, args.pattern_order)
    else:
        # Sort by pattern first, then by size
        def sort_key(ps: str):
            # Extract pattern and size
            for i, p in enumerate(parse_csv_list(args.pattern_order)):
                if ps.lower().startswith(p.lower()):
                    # Extract size if present
                    size_match = re.search(r'\((\d+)x(\d+)\)', ps)
                    if size_match:
                        return (i, int(size_match.group(1)), int(size_match.group(2)))
                    return (i, 0, 0)
            return (999, ps)
        rows = sorted(found_rows, key=sort_key)
    
    # Parse name maps
    alg_name_map = parse_name_map(args.algorithm_names, DEFAULT_ALG_NAME_MAP)
    pattern_name_map = parse_name_map(args.pattern_names, DEFAULT_PATTERN_NAME_MAP)
    
    # Build table
    latex = build_latex_table(
        stats=stats,
        algorithms=algorithms,
        row_col=row_col,
        rows=rows,
        metric=args.metric,
        precision_metric=args.precision_metric,
        precision_time=args.precision_time,
        table_env=not args.no_table_env,
        bold_best=args.bold_best,
        time_no_std=args.time_no_std,
        alg_name_map=alg_name_map,
        pattern_name_map=pattern_name_map,
        separator_after=args.separator_after or None,
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(latex + "\n")
    else:
        print(latex)


if __name__ == "__main__":
    main()
