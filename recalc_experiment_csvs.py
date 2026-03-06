#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ---------- Entropy calculation ----------

def calculate_entropy(dataset_path: Path) -> float | None:
    """
    Calculate Shannon entropy of the tiles in a dataset JSON file.
    Returns entropy in bits, or None if the file cannot be read.
    """
    try:
        data = json.loads(dataset_path.read_text())
        tiles = data.get('tiles', [])
        if not tiles:
            return None
        
        # Flatten all tile values
        all_values = []
        for tile in tiles:
            for row in tile:
                all_values.extend(row)
        
        if not all_values:
            return None
        
        # Count occurrences
        value_counts = {}
        for val in all_values:
            value_counts[val] = value_counts.get(val, 0) + 1
        
        # Calculate Shannon entropy
        total = len(all_values)
        entropy = 0.0
        for count in value_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        return entropy
    except Exception:
        return None


# ---------- CSV writers (same schema as your main script) ----------

def write_results_to_csv(results: List[Dict[str, Any]], output_file: Path) -> None:
    if not results:
        return

    fieldnames = [
        'scale', 'tiles', 'n', 'm', 'run', 'seed', 'algorithm', 'objective_type',
        'status', 'objective', 'runtime', 'bbox_width', 'bbox_height', 'num_tiles',
        'total_crossovers', 'crossovers_needing_completion', 'total_tiles_completed',
        'completion_rate', 'avg_tiles_per_incomplete', 'entropy'
    ]

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for r in results:
            row = dict(r)

            tc = row.get('total_crossovers')
            cnc = row.get('crossovers_needing_completion')
            tcomp = row.get('total_tiles_completed')

            if tc and tc > 0 and cnc is not None:
                row['completion_rate'] = cnc / tc
                if cnc > 0 and tcomp is not None:
                    row['avg_tiles_per_incomplete'] = tcomp / cnc

            writer.writerow(row)


def calculate_summary_statistics(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}

    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        obj_type = r.get('objective_type', 'square') or 'square'
        key = f"{r['algorithm']}_T{r['tiles']}_n{r['n']}_m{r['m']}_{obj_type}"
        groups.setdefault(key, []).append(r)

    for key, group in groups.items():
        objectives = [r['objective'] for r in group if r.get('objective') is not None]
        runtimes = [r['runtime'] for r in group if r.get('runtime') is not None]
        if not objectives or not runtimes:
            continue

        obj_mean = sum(objectives) / len(objectives)
        rt_mean = sum(runtimes) / len(runtimes)
        
        # Get entropy (should be the same for all runs in a group)
        entropy = group[0].get('entropy')

        stats: Dict[str, Any] = {
            'algorithm': group[0]['algorithm'],
            'tiles': group[0]['tiles'],
            'n': group[0]['n'],
            'm': group[0]['m'],
            'objective_type': group[0].get('objective_type', 'square') or 'square',
            'num_runs': len(group),
            'successful_runs': len(objectives),
            'entropy': entropy,
            'objective': {
                'mean': obj_mean,
                'min': min(objectives),
                'max': max(objectives),
                'std': (sum((x - obj_mean) ** 2 for x in objectives) / len(objectives)) ** 0.5 if len(objectives) > 1 else 0.0,
            },
            'runtime': {
                'mean': rt_mean,
                'min': min(runtimes),
                'max': max(runtimes),
                'std': (sum((x - rt_mean) ** 2 for x in runtimes) / len(runtimes)) ** 0.5 if len(runtimes) > 1 else 0.0,
            },
        }

        # CPLEX status counts (if present)
        if group[0]['algorithm'] == 'cplex':
            status_counts = {
                'optimal': sum(1 for r in group if r.get('status') == 'optimal'),
                'feasible': sum(1 for r in group if r.get('status') == 'feasible'),
                'infeasible': sum(1 for r in group if r.get('status') == 'infeasible'),
                'timeout': sum(1 for r in group if r.get('status') == 'timeout'),
                'failed': sum(1 for r in group if r.get('status') in ['failed', 'parse_failed', 'error']),
            }
            stats['cplex_status_counts'] = status_counts

        # Genetic crossover stats (optional)
        crossovers = [r.get('total_crossovers') for r in group if r.get('total_crossovers') is not None]
        completions = [r.get('crossovers_needing_completion') for r in group if r.get('crossovers_needing_completion') is not None]
        tiles_completed = [r.get('total_tiles_completed') for r in group if r.get('total_tiles_completed') is not None]

        if crossovers:
            # Use only pairs where both exist
            paired = [
                (c, t) for (c, t) in zip(completions, crossovers)
                if (c is not None and t is not None and t > 0)
            ]
            avg_completion_rate = (sum(c / t for c, t in paired) / len(paired)) if paired else 0.0
            stats['crossover_stats'] = {
                'avg_total_crossovers': sum(crossovers) / len(crossovers),
                'avg_completions': (sum(completions) / len(completions)) if completions else 0.0,
                'avg_completion_rate': avg_completion_rate,
                'avg_tiles_completed': (sum(tiles_completed) / len(tiles_completed)) if tiles_completed else 0.0,
            }

        summary[key] = stats

    return summary


def write_summary_to_csv(summary: Dict[str, Any], output_file: Path) -> None:
    if not summary:
        return

    fieldnames = [
        'algorithm', 'tiles', 'n', 'm', 'num_runs', 'successful_runs',
        'obj_mean', 'obj_min', 'obj_max', 'obj_std',
        'runtime_mean', 'runtime_min', 'runtime_max', 'runtime_std',
        'crossovers_mean', 'completion_rate_mean', 'tiles_completed_mean',
        'cplex_optimal', 'cplex_feasible', 'cplex_infeasible', 'cplex_timeout', 'cplex_failed',
        'entropy'
    ]

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()

        for _, stats in summary.items():
            row = {
                'algorithm': stats['algorithm'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'num_runs': stats['num_runs'],
                'successful_runs': stats.get('successful_runs', stats['num_runs']),
                'obj_mean': stats['objective']['mean'],
                'obj_min': stats['objective']['min'],
                'obj_max': stats['objective']['max'],
                'obj_std': stats['objective']['std'],
                'runtime_mean': stats['runtime']['mean'],
                'runtime_min': stats['runtime']['min'],
                'runtime_max': stats['runtime']['max'],
                'runtime_std': stats['runtime']['std'],
            }

            if 'crossover_stats' in stats:
                row['crossovers_mean'] = stats['crossover_stats']['avg_total_crossovers']
                row['completion_rate_mean'] = stats['crossover_stats']['avg_completion_rate']
                row['tiles_completed_mean'] = stats['crossover_stats']['avg_tiles_completed']

            if 'cplex_status_counts' in stats:
                row['cplex_optimal'] = stats['cplex_status_counts']['optimal']
                row['cplex_feasible'] = stats['cplex_status_counts']['feasible']
                row['cplex_infeasible'] = stats['cplex_status_counts']['infeasible']
                row['cplex_timeout'] = stats['cplex_status_counts']['timeout']
                row['cplex_failed'] = stats['cplex_status_counts']['failed']
            
            if 'entropy' in stats:
                row['entropy'] = stats['entropy']

            writer.writerow(row)


def write_aggregated_stats_csv(results: List[Dict[str, Any]], output_file: Path) -> None:
    """Write aggregated statistics (avg and stdev) for each configuration to CSV."""
    if not results:
        return
    
    # Calculate summary statistics
    summary = calculate_summary_statistics(results)
    
    fieldnames = ['algorithm', 'tiles', 'n', 'm', 'objective_type', 
                  'avg_objective', 'stdev_objective', 
                  'avg_runtime', 'stdev_runtime', 'entropy']
    
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with output_file.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for key, stats in sorted(summary.items()):
            row = {
                'algorithm': stats['algorithm'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'objective_type': stats.get('objective_type', 'square'),
                'avg_objective': round(stats['objective']['mean'], 2),
                'stdev_objective': round(stats['objective']['std'], 2),
                'avg_runtime': round(stats['runtime']['mean'], 4),
                'stdev_runtime': round(stats['runtime']['std'], 4),
                'entropy': stats.get('entropy')
            }
            
            writer.writerow(row)


# ---------- directory scan + parsing ----------

def parse_run_file(path: Path, scale: str) -> Dict[str, Any] | None:
    """
    Parse a single run_*.json file into one row for CSV.
    Returns None if it's a failure marker with no objective/runtime.
    """
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None

    if not isinstance(data, dict) or 'results' not in data or not data['results']:
        return None

    r0 = data['results'][0]
    inp = data.get('input', {})

    # If it was a failure marker, skip (you can change this if you want to keep failures)
    if r0.get('status') in ['failed', 'parse_failed', 'error']:
        return None

    objective = r0.get('objective')
    runtime = r0.get('runtime_seconds')
    if objective is None or runtime is None:
        return None

    # Algorithm: prefer JSON field; fallback to filename "run_{k}_{algo}.json"
    algo = r0.get('algorithm')
    if (algo == 'simulated_annealing'):
        return None
    if not algo:
        name = path.stem  # run_3_genetic_stochastic
        prefix = f"run_"
        if name.startswith(prefix):
            # strip "run_{k}_"
            parts = name.split("_", 2)
            algo = parts[2] if len(parts) == 3 else name
        else:
            algo = name

    # Run index from filename
    run_idx = None
    try:
        # run_3_xxx.json
        run_idx = int(path.stem.split("_", 2)[1])
    except Exception:
        run_idx = None

    # Try to calculate entropy from the dataset file
    entropy = None
    dataset_file = inp.get('dataset_file')
    if dataset_file:
        # Dataset file path is stored in input
        dataset_path = Path(dataset_file)
        if dataset_path.exists():
            entropy = calculate_entropy(dataset_path)
    else:
        # Look for dataset file in the same directory as the run file
        # Pattern: dataset_run{k}.json or dataset_run{k}_a{alphabet}.json
        if run_idx is not None:
            parent_dir = path.parent
            for pattern in [f"dataset_run{run_idx}.json", f"dataset_run{run_idx}_a*.json"]:
                for dataset_path in parent_dir.glob(pattern):
                    entropy = calculate_entropy(dataset_path)
                    break
            if entropy is None:
                # Try dataset.json in the parent directory
                dataset_path = parent_dir / "dataset.json"
                if dataset_path.exists():
                    entropy = calculate_entropy(dataset_path)
    
    row = {
        'scale': scale,
        'tiles': inp.get('T'),
        'n': inp.get('n'),
        'm': inp.get('m'),
        'run': run_idx,
        'seed': inp.get('seed'),
        'algorithm': algo,
        'objective_type': inp.get('objective_type'),
        'status': r0.get('status'),
        'objective': objective,
        'runtime': runtime,
        'bbox_width': r0.get('bbox_width'),
        'bbox_height': r0.get('bbox_height'),
        'num_tiles': r0.get('num_tiles_placed'),
        'total_crossovers': r0.get('total_crossovers'),
        'crossovers_needing_completion': r0.get('crossovers_needing_completion'),
        'total_tiles_completed': r0.get('total_tiles_completed'),
        'entropy': entropy,
    }

    return row


def collect_all_results(root: Path, cli_objective_type: str = None) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Returns:
      - combined list of all results
      - dict: scale -> list of results
    """
    all_rows: List[Dict[str, Any]] = []
    by_scale: Dict[str, List[Dict[str, Any]]] = {}

    # Try to load objective_type from experiment_metadata.json
    default_objective_type = cli_objective_type  # CLI arg takes precedence
    
    if not default_objective_type:
        metadata_file = root / 'experiment_metadata.json'
        if metadata_file.exists():
            try:
                metadata = json.loads(metadata_file.read_text())
                # Check configurations for objective_type
                configs = metadata.get('configurations', {})
                # Use the first scale's objective_type as default
                for scale_cfg in configs.values():
                    if 'objective_type' in scale_cfg:
                        default_objective_type = scale_cfg['objective_type']
                        break
            except Exception:
                pass
    
    if default_objective_type:
        print(f"Using default objective_type: {default_objective_type}")

    # Expect structure: root/<scale>/T*_n*_m*/run_*.json
    for scale_dir in root.iterdir():
        if not scale_dir.is_dir():
            continue
        scale = scale_dir.name
        by_scale.setdefault(scale, [])

        for run_file in scale_dir.rglob("run_*.json"):
            row = parse_run_file(run_file, scale)
            if row is None:
                continue
            # Fill in objective_type if missing
            if not row.get('objective_type') and default_objective_type:
                row['objective_type'] = default_objective_type
            by_scale[scale].append(row)
            all_rows.append(row)

    return all_rows, by_scale


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=str, default="experiments", help="Experiments root directory")
    ap.add_argument("--write-json", action="store_true", help="Also rewrite all_results.json + summary_statistics.json")
    ap.add_argument("--objective-type", type=str, default=None, 
                    help="Default objective_type to use if not found in JSON files (e.g., 'area' or 'square')")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Root directory not found: {root}")

    all_rows, by_scale = collect_all_results(root, args.objective_type)

    # Combined CSV
    write_results_to_csv(all_rows, root / "combined_all_results.csv")
    print(f"✓ wrote {root / 'combined_all_results.csv'}  ({len(all_rows)} rows)")

    # Combined aggregated statistics CSV
    write_aggregated_stats_csv(all_rows, root / "aggregated_statistics.csv")
    print(f"✓ wrote {root / 'aggregated_statistics.csv'}")

    # Per-scale CSVs + summaries
    for scale, rows in sorted(by_scale.items()):
        if not rows:
            continue
        scale_dir = root / scale
        write_results_to_csv(rows, scale_dir / "all_results.csv")
        print(f"✓ wrote {scale_dir / 'all_results.csv'}  ({len(rows)} rows)")

        summary = calculate_summary_statistics(rows)
        write_summary_to_csv(summary, scale_dir / "summary_statistics.csv")
        print(f"✓ wrote {scale_dir / 'summary_statistics.csv'}  ({len(summary)} groups)")

        write_aggregated_stats_csv(rows, scale_dir / "aggregated_statistics.csv")
        print(f"✓ wrote {scale_dir / 'aggregated_statistics.csv'}")

        if args.write_json:
            (scale_dir / "all_results.json").write_text(json.dumps(rows, indent=2))
            (scale_dir / "summary_statistics.json").write_text(json.dumps(summary, indent=2))
            print(f"✓ wrote {scale_dir / 'all_results.json'} and summary_statistics.json")

    print("Done.")


if __name__ == "__main__":
    main()
