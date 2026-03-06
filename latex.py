#!/usr/bin/env python3
"""
Generate a LaTeX table from experiment CSV.

Rows: dataset config (e.g., T20_n3_m3)
Cols: algorithms (1 col each)
Cell: two lines via \\shortstack:
  line 1: objective mean ± stdev
  line 2: (runtime mean ± stdev) s   [or mean only if --time-no-std]

We filter to ONE objective_type (default: area). The objective is indicated in caption.

Options:
- --exclude-algorithms: comma-separated algorithm names to exclude (exact match).
- --bold-best: bold best (minimum) mean objective and best (minimum) mean runtime per row across algorithms.
- --time-no-std: show only mean time (no ± stdev).

Config filtering (baseline presence):
- --config-mode:
    - no_baseline (default): only configs that do NOT have cplex OR merge_greedy_py result
    - with_cplex: only configs that HAVE cplex result
    - with_merge_greedy_py: only configs that HAVE merge_greedy_py result
    - all: all configs

Column ordering
- --algorithm-order: comma-separated ordering. Defaults to:
    cplex, merge_greedy_py, greedy, greedy_stochastic, genetic_greedy, genetic_stochastic
Algorithms not in the list are appended alphabetically.
Matching for ordering is case-insensitive.
"""

from __future__ import annotations
import argparse
import math
import re
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


def pick_first_existing_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def make_config_col(df: pd.DataFrame) -> pd.Series:
    for c in ["config", "dataset_config", "test_config", "instance", "name"]:
        if c in df.columns:
            return df[c].astype(str)

    needed = ["tiles", "n", "m"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(
            f"Cannot build dataset config. Missing columns: {missing}. "
            f"Provide one of config/dataset_config/test_config/instance/name, "
            f"or include tiles,n,m."
        )

    return df.apply(lambda r: f"T{int(r['tiles'])}_n{int(r['n'])}_m{int(r['m'])}", axis=1)


def is_aggregated(df: pd.DataFrame) -> bool:
    return all(c in df.columns for c in ["avg_objective", "stdev_objective", "avg_runtime", "stdev_runtime"])


def aggregate(df: pd.DataFrame) -> pd.DataFrame:
    """
    Output columns:
      config, objective_type, algorithm,
      avg_objective, stdev_objective, avg_runtime, stdev_runtime
    """
    df = df.copy()

    if "algorithm" not in df.columns:
        raise ValueError("CSV must contain an 'algorithm' column.")
    if "objective_type" not in df.columns:
        df["objective_type"] = "area"  # default

    df["config"] = make_config_col(df)
    df["objective_type"] = df["objective_type"].astype(str).str.lower()

    if is_aggregated(df):
        keep = [
            "config", "objective_type", "algorithm",
            "avg_objective", "stdev_objective", "avg_runtime", "stdev_runtime"
        ]
        return df[keep].copy()

    # Raw-mode
    cost_col = pick_first_existing_col(df, ["objective", "cost", "objective_value", "obj", "value"])
    time_col = pick_first_existing_col(df, ["runtime", "time", "walltime", "elapsed", "seconds"])

    if cost_col is None or time_col is None:
        raise ValueError(
            "Raw CSV mode detected (no avg_/stdev_ columns), but couldn't find cost/runtime columns.\n"
            "Need one of cost columns: objective/cost/objective_value/obj/value and "
            "one of runtime columns: runtime/time/walltime/elapsed/seconds.\n"
            f"Columns found: {list(df.columns)}"
        )

    df[cost_col] = pd.to_numeric(df[cost_col], errors="coerce")
    df[time_col] = pd.to_numeric(df[time_col], errors="coerce")

    gcols = ["config", "objective_type", "algorithm"]
    agg = df.groupby(gcols, dropna=False).agg(
        avg_objective=(cost_col, "mean"),
        stdev_objective=(cost_col, lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0),
        avg_runtime=(time_col, "mean"),
        stdev_runtime=(time_col, lambda x: float(x.std(ddof=1)) if len(x) > 1 else 0.0),
    ).reset_index()

    return agg


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
      mean\\pmstd
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


def order_algorithms(found_algs: List[str], order_csv: str) -> List[str]:
    preferred = [x.lower() for x in parse_csv_list(order_csv)]
    low_to_orig: Dict[str, str] = {}
    for a in found_algs:
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


def filter_configs_by_baselines(stats_obj: pd.DataFrame, config_mode: str) -> pd.DataFrame:
    df = stats_obj.copy()
    alg_l = df["algorithm"].astype(str).str.lower()
    with_cplex = set(df.loc[alg_l == "cplex", "config"].astype(str))
    with_merge = set(df.loc[alg_l == "merge_greedy", "config"].astype(str))
    all_cfgs = set(df["config"].astype(str).unique().tolist())

    if config_mode == "no_baseline":
        allowed = all_cfgs - (with_cplex | with_merge)
        # Only include greedy and GA algorithms
        no_baseline_algs = {"greedy", "stochastic_greedy", "genetic_greedy", "genetic_stochastic"}
        df = df[alg_l.isin(no_baseline_algs)].copy()
    elif config_mode == "with_cplex":
        allowed = with_cplex
    elif config_mode == "with_merge_greedy_py":
        allowed = with_merge
    elif config_mode == "with_merge_greedy":
        # Compare against only merge_greedy (exclude cplex)
        allowed = with_merge
        df = df[alg_l != "cplex"].copy()
    elif config_mode == "all":
        allowed = all_cfgs
    else:
        raise ValueError(f"Unknown config_mode: {config_mode}")

        

    return df[df["config"].astype(str).isin(allowed)].copy()


def parse_algorithm_name_map(s: str) -> Dict[str, str]:
    """Parse comma-separated key=value pairs into a dict."""
    result = DEFAULT_ALG_NAME_MAP.copy()
    if not s:
        return result
    for pair in s.split(","):
        pair = pair.strip()
        if "=" in pair:
            k, v = pair.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def get_display_name(alg: str, name_map: Dict[str, str]) -> str:
    """Get display name for algorithm, falling back to original if not mapped."""
    return name_map.get(alg, alg)


def build_latex_table(
    stats: pd.DataFrame,
    algorithms: List[str],
    objective_type: str,
    precision_cost: int,
    precision_time: int,
    table_env: bool = True,
    bold_best: bool = False,
    time_no_std: bool = False,
    alg_name_map: Optional[Dict[str, str]] = None,
    separator_after: Optional[str] = None,
) -> str:
    def sort_key(cfg: str):
        m = re.match(r"T(\d+)_n(\d+)_m(\d+)", cfg)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return (10**9, cfg)

    configs = sorted(stats["config"].unique().tolist(), key=sort_key)

    idx: Dict[Tuple[str, str], Dict[str, float]] = {}
    for _, r in stats.iterrows():
        idx[(str(r["config"]), str(r["algorithm"]))] = {
            "avg_objective": float(r["avg_objective"]),
            "stdev_objective": float(r["stdev_objective"]),
            "avg_runtime": float(r["avg_runtime"]),
            "stdev_runtime": float(r["stdev_runtime"]),
        }

    best_obj: Dict[str, Set[str]] = {}
    best_time: Dict[str, Set[str]] = {}
    if bold_best:
        for cfg in configs:
            vals_obj = {}
            vals_time = {}
            for alg in algorithms:
                k = (cfg, alg)
                if k in idx:
                    vals_obj[alg] = idx[k]["avg_objective"]
                    vals_time[alg] = idx[k]["avg_runtime"]
            best_obj[cfg] = {a for a, v in vals_obj.items() if v == min(vals_obj.values())} if vals_obj else set()
            best_time[cfg] = {a for a, v in vals_time.items() if v == min(vals_time.values())} if vals_time else set()

    total_cols = 1 + len(algorithms)
    # Build colspec with optional vertical separator
    # Use !{\vrule} instead of | for proper spacing with tabular* and \extracolsep{\fill}
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

    def col_range(start_col_1based: int, width: int) -> Tuple[int, int]:
        return (start_col_1based, start_col_1based + width - 1)

    lines: List[str] = []
    if table_env:
        lines += [
            "\\begin{table}",
            "\\centering",
            "\\small",
            # "\\setlength{\\tabcolsep}{2pt}",
            # "\\renewcommand{\\arraystretch}{1.15}",
        ]

    lines += [
        f"\\begin{{tabular*}}{{\\textwidth}}{{@{{\\extracolsep{{\\fill}}}}{colspec}}}",
        "\\toprule",
    ]

    if alg_name_map is None:
        alg_name_map = DEFAULT_ALG_NAME_MAP
    header = ["\\textbf{Config}"] + [f"\\texttt{{{latex_escape(get_display_name(a, alg_name_map))}}}" for a in algorithms]
    lines.append(" & ".join(header) + " \\\\")

    # cmid = []
    # col_cursor = 2
    # for _ in algorithms:
    #     a, b = col_range(col_cursor, 1)
    #     cmid.append(f"\\cmidrule(lr){{{a}-{b}}}")
    #     col_cursor += 1
    # lines.append("".join(cmid))
    lines.append("\\midrule")

    for cfg in configs:
        row = [f"\\shortstack{{{latex_escape(cfg)}\\\\~}}"]
        for alg in algorithms:
            k = (cfg, alg)
            if k not in idx:
                row.append("-")
                continue

            d = idx[k]
            bold_obj_line = bold_best and (alg in best_obj.get(cfg, set()))
            bold_time_line = bold_best and (alg in best_time.get(cfg, set()))

            obj_core = fmt_pm_core(d["avg_objective"], d["stdev_objective"], precision_cost, bold=bold_obj_line)

            if time_no_std:
                time_core = fmt_mean_only(d["avg_runtime"], precision_time, bold=bold_time_line)
            else:
                time_core = fmt_pm_core(d["avg_runtime"], d["stdev_runtime"], precision_time, bold=bold_time_line)

            if not obj_core and not time_core:
                row.append("-")
                continue

            cell = (
                "\\shortstack{"
                f"${obj_core}$"
                "\\\\"
                f"$\\left({time_core}\\mathrm{{s}}\\right)$"
                "}"
            )
            row.append(cell)

        lines.append(" & ".join(row) + " \\\\")
    lines += [
        "\\bottomrule",
        "\\end{tabular*}",
    ]

    if table_env:
        obj_tex = latex_escape(objective_type)
        time_note = "runtime is mean only" if time_no_std else "runtime is mean $\\pm$ std"
        lines += [
            f"\\caption{{Objective type: \\texttt{{{obj_tex}}}. Each cell shows objective (top) as mean $\\pm$ std and {time_note} (bottom).}}",
            "\\label{tab:results-summary}",
            "\\end{table}",
        ]

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to CSV file")
    ap.add_argument("--out", default=None, help="Output .tex file (default: print to stdout)")
    ap.add_argument("--precision-cost", type=int, default=2, help="Decimal places for objective (cost)")
    ap.add_argument("--precision-time", type=int, default=3, help="Decimal places for runtime")
    ap.add_argument("--no-table-env", action="store_true", help="Output only tabular (no table environment)")

    ap.add_argument("--objective-type", default="area", help="Which objective_type to include (default: area).")
    ap.add_argument("--exclude-algorithms", default="", help="Comma-separated algorithm names to exclude (exact match).")
    ap.add_argument("--bold-best", action="store_true", help="Bold best mean objective and best mean runtime per row.")

    ap.add_argument(
        "--config-mode",
        choices=["no_baseline", "with_cplex", "with_merge_greedy_py", "with_merge_greedy", "all"],
        default="no_baseline",
        help=(
            "Which configs to include based on baseline availability. "
            "no_baseline (default): configs WITHOUT cplex OR merge_greedy_py. "
            "with_cplex: ONLY configs WITH cplex. "
            "with_merge_greedy_py: ONLY configs WITH merge_greedy_py. "
            "with_merge_greedy: configs WITH merge_greedy_py, but exclude cplex. "
            "all: no filtering."
        ),
    )

    ap.add_argument(
        "--algorithm-names",
        default="",
        help=(
            "Comma-separated key=value pairs for algorithm display names. "
            "E.g., 'greedy=Greedy,genetic_greedy=GA-Greedy'. "
            "Overrides defaults."
        ),
    )

    ap.add_argument(
        "--algorithm-order",
        default=DEFAULT_ALG_ORDER,
        help=("Comma-separated algorithm ordering (preferred first). Default: " + DEFAULT_ALG_ORDER),
    )

    # NEW:
    ap.add_argument(
        "--time-no-std",
        action="store_true",
        help="Show only mean runtime (no ± stdev) on the 2nd line.",
    )

    ap.add_argument(
        "--separator-after",
        default="",
        help=(
            "Insert a vertical line after this algorithm to visually separate columns. "
            "E.g., '--separator-after merge_greedy_py' separates baselines from proposed methods."
        ),
    )

    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    stats = aggregate(df)

    obj_type = str(args.objective_type).lower()
    stats = stats[stats["objective_type"].astype(str).str.lower() == obj_type].copy()

    stats = filter_configs_by_baselines(stats, args.config_mode)

    excluded = parse_exclude_list(args.exclude_algorithms)
    if excluded:
        stats = stats[~stats["algorithm"].astype(str).isin(excluded)].copy()

    found_algs = sorted(stats["algorithm"].astype(str).unique().tolist())
    algorithms = order_algorithms(found_algs, args.algorithm_order)

    alg_name_map = parse_algorithm_name_map(args.algorithm_names)

    latex = build_latex_table(
        stats=stats,
        algorithms=algorithms,
        objective_type=obj_type,
        precision_cost=args.precision_cost,
        precision_time=args.precision_time,
        table_env=not args.no_table_env,
        bold_best=args.bold_best,
        time_no_std=args.time_no_std,
        alg_name_map=alg_name_map,
        separator_after=args.separator_after or None,
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(latex + "\n")
    else:
        print(latex)


if __name__ == "__main__":
    main()
