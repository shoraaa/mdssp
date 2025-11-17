#!/usr/bin/env python3
"""
MDSSP Systematic Experiments - Multi-Scale Testing

This script runs systematic experiments across different problem scales:
- Small scale (T=6-10): With CPLEX as baseline
- Medium scale (T=20-30): Heuristics comparison
- Large scale (T=50-60): Scalability testing

All results are organized in the experiments/ directory.
"""

import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import time
import sys
import csv

# Experiment configurations
EXPERIMENTS = {
    'small': {
        'tiles': [6, 8, 10],
        'tile_size': [(3, 3)],
        'runs': 30,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'cplex'],
        'pop_size': 50,
        'generations': 100,
        'description': 'Small scale with CPLEX baseline'
    },
    'medium': {
        'tiles': [20, 30],
        'tile_size': [(3, 3)],
        'runs': 30,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic'],
        'pop_size': 100,
        'generations': 200,
        'description': 'Medium scale without CPLEX'
    },
    'large': {
        'tiles': [50, 60],
        'tile_size': [(3, 3)],
        'runs': 20,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic'],
        'pop_size': 150,
        'generations': 300,
        'description': 'Large scale scalability testing'
    }
}

def run_single_experiment(algorithm, tiles, n, m, seed, output_file, pop_size=None, generations=None):
    """Run a single experiment and return results."""
    cmd = [
        "./mdssp",
        "-a", algorithm,
        "-T", str(tiles),
        "-n", str(n),
        "-m", str(m),
        "-s", str(seed),
        "-o", output_file
    ]
    
    if algorithm in ['genetic_greedy', 'genetic_stochastic']:
        if pop_size:
            cmd.extend(["--pop-size", str(pop_size)])
        if generations:
            cmd.extend(["--generations", str(generations)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        
        # Parse output
        output = result.stdout
        objective = None
        runtime = None
        bbox_width = None
        bbox_height = None
        num_tiles = None
        total_crossovers = None
        crossovers_needing_completion = None
        total_tiles_completed = None
        
        for line in output.split('\n'):
            if 'Objective (L):' in line:
                try:
                    objective = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Runtime:' in line:
                try:
                    runtime = float(line.split(':')[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif 'Bounding Box:' in line:
                try:
                    parts = line.split(':')[1].strip().split('×')
                    bbox_width = int(parts[0].strip())
                    bbox_height = int(parts[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Placements:' in line:
                try:
                    num_tiles = int(line.split(':')[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif 'Total crossovers:' in line:
                try:
                    total_crossovers = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Crossovers needing greedy completion:' in line:
                try:
                    total_crossovers = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Total tiles placed by greedy completion:' in line:
                try:
                    total_tiles_completed = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
        
        # Load JSON solution if available
        solution_data = None
        if Path(output_file).exists():
            try:
                with open(output_file, 'r') as f:
                    solution_data = json.load(f)
                    
                # Extract crossover stats from JSON if available
                if solution_data and 'results' in solution_data:
                    result_obj = solution_data['results'][0]
                    if 'total_crossovers' in result_obj:
                        total_crossovers = result_obj['total_crossovers']
                    if 'crossovers_needing_completion' in result_obj:
                        crossovers_needing_completion = result_obj['crossovers_needing_completion']
                    if 'total_tiles_completed' in result_obj:
                        total_tiles_completed = result_obj['total_tiles_completed']
                        
            except Exception as e:
                print(f"    Warning: Could not load solution JSON: {e}")
        
        return {
            'success': True,
            'objective': objective,
            'runtime': runtime,
            'bbox_width': bbox_width,
            'bbox_height': bbox_height,
            'num_tiles': num_tiles,
            'total_crossovers': total_crossovers,
            'crossovers_needing_completion': crossovers_needing_completion,
            'total_tiles_completed': total_tiles_completed,
            'solution': solution_data
        }
    
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def run_experiment_suite(scale, config, base_seed, output_dir):
    """Run all experiments for a given scale."""
    print(f"\n{'='*80}")
    print(f"RUNNING {scale.upper()} SCALE EXPERIMENTS")
    print(f"{'='*80}")
    print(f"Description: {config['description']}")
    print(f"Tile counts: {config['tiles']}")
    print(f"Tile sizes: {config['tile_size']}")
    print(f"Algorithms: {config['algorithms']}")
    print(f"Runs per configuration: {config['runs']}")
    print(f"{'='*80}\n")
    
    scale_dir = output_dir / scale
    scale_dir.mkdir(exist_ok=True, parents=True)
    
    all_results = []
    best_results = {}
    
    for tiles in config['tiles']:
        for (n, m) in config['tile_size']:
            exp_name = f"T{tiles}_n{n}_m{m}"
            print(f"\n--- Experiment: {exp_name} ---")
            
            exp_dir = scale_dir / exp_name
            exp_dir.mkdir(exist_ok=True)
            
            for run in range(config['runs']):
                seed = base_seed + run * 100
                print(f"\nRun {run + 1}/{config['runs']} (seed={seed})")
                
                for algo in config['algorithms']:
                    algo_name = algo.replace('_', ' ').title()
                    print(f"  [{algo}] ", end='', flush=True)
                    
                    output_file = exp_dir / f"run_{run+1}_{algo}.json"
                    
                    result = run_single_experiment(
                        algo, tiles, n, m, seed, str(output_file),
                        config.get('pop_size'), config.get('generations')
                    )
                    
                    if result['success']:
                        obj = result['objective']
                        runtime = result['runtime']
                        
                        if obj is not None and runtime is not None:
                            print(f"✓ Obj={obj}, Time={runtime:.3f}s", end='')
                            
                            # Add crossover stats if available
                            if result['total_crossovers']:
                                completion_rate = result['crossovers_needing_completion'] / result['total_crossovers'] * 100
                                print(f", Completion={completion_rate:.1f}%", end='')
                            
                            print()
                            
                            # Store result
                            result_entry = {
                                'scale': scale,
                                'tiles': tiles,
                                'n': n,
                                'm': m,
                                'run': run + 1,
                                'seed': seed,
                                'algorithm': algo,
                                'objective': obj,
                                'runtime': runtime,
                                'bbox_width': result['bbox_width'],
                                'bbox_height': result['bbox_height'],
                                'num_tiles': result['num_tiles']
                            }
                            
                            # Add genetic algorithm specific stats
                            if result['total_crossovers']:
                                result_entry['total_crossovers'] = result['total_crossovers']
                                result_entry['crossovers_needing_completion'] = result['crossovers_needing_completion']
                                result_entry['total_tiles_completed'] = result['total_tiles_completed']
                            
                            all_results.append(result_entry)
                            
                            # Track best result
                            key = f"{exp_name}_{algo}"
                            if key not in best_results or obj < best_results[key]['objective']:
                                best_results[key] = result_entry.copy()
                                best_results[key]['solution'] = result['solution']
                        else:
                            print("✗ Parse failed")
                    else:
                        print(f"✗ {result.get('error', 'unknown error')}")
            
            # Save experiment results
            exp_results = [r for r in all_results if r['tiles'] == tiles and r['n'] == n and r['m'] == m]
            with open(exp_dir / 'all_results.json', 'w') as f:
                json.dump(exp_results, f, indent=2)
            
            # Save best solutions for this experiment
            exp_best = {k: v for k, v in best_results.items() if k.startswith(exp_name)}
            for key, result in exp_best.items():
                algo = key.split('_')[-1]
                if result.get('solution'):
                    with open(exp_dir / f'best_{algo}_solution.json', 'w') as f:
                        json.dump(result['solution'], f, indent=2)
    
    # Save scale-wide results
    with open(scale_dir / 'all_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    with open(scale_dir / 'best_results.json', 'w') as f:
        # Remove solution data for summary file
        best_summary = {k: {kk: vv for kk, vv in v.items() if kk != 'solution'} 
                       for k, v in best_results.items()}
        json.dump(best_summary, f, indent=2)
    
    # Write results to CSV
    write_results_to_csv(all_results, scale_dir / 'all_results.csv')
    
    # Calculate summary statistics
    summary = calculate_summary_statistics(all_results)
    with open(scale_dir / 'summary_statistics.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Write summary statistics to CSV
    write_summary_to_csv(summary, scale_dir / 'summary_statistics.csv')
    
    print(f"\n{'='*80}")
    print(f"✓ {scale.upper()} scale experiments completed")
    print(f"  Total runs: {len(all_results)}")
    print(f"  Results saved to: {scale_dir}")
    print(f"  CSV files: all_results.csv, summary_statistics.csv")
    print(f"{'='*80}")
    
    return all_results, best_results, summary

def write_results_to_csv(results, output_file):
    """Write all results to a CSV file."""
    if not results:
        return
    
    # Determine all possible fields
    fieldnames = ['scale', 'tiles', 'n', 'm', 'run', 'seed', 'algorithm', 
                  'objective', 'runtime', 'bbox_width', 'bbox_height', 'num_tiles',
                  'total_crossovers', 'crossovers_needing_completion', 'total_tiles_completed',
                  'completion_rate', 'avg_tiles_per_incomplete']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for result in results:
            row = result.copy()
            # Calculate derived metrics for genetic algorithms
            if result.get('total_crossovers') and result['total_crossovers'] > 0:
                row['completion_rate'] = result['crossovers_needing_completion'] / result['total_crossovers']
                if result['crossovers_needing_completion'] > 0:
                    row['avg_tiles_per_incomplete'] = result['total_tiles_completed'] / result['crossovers_needing_completion']
            writer.writerow(row)

def write_summary_to_csv(summary, output_file):
    """Write summary statistics to a CSV file."""
    if not summary:
        return
    
    fieldnames = ['algorithm', 'tiles', 'n', 'm', 'num_runs',
                  'obj_mean', 'obj_min', 'obj_max', 'obj_std',
                  'runtime_mean', 'runtime_min', 'runtime_max', 'runtime_std',
                  'crossovers_mean', 'completion_rate_mean', 'tiles_completed_mean']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for key, stats in summary.items():
            row = {
                'algorithm': stats['algorithm'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'num_runs': stats['num_runs'],
                'obj_mean': stats['objective']['mean'],
                'obj_min': stats['objective']['min'],
                'obj_max': stats['objective']['max'],
                'obj_std': stats['objective']['std'],
                'runtime_mean': stats['runtime']['mean'],
                'runtime_min': stats['runtime']['min'],
                'runtime_max': stats['runtime']['max'],
                'runtime_std': stats['runtime']['std']
            }
            
            # Add genetic algorithm specific stats
            if 'crossover_stats' in stats:
                row['crossovers_mean'] = stats['crossover_stats']['avg_total_crossovers']
                row['completion_rate_mean'] = stats['crossover_stats']['avg_completion_rate']
                row['tiles_completed_mean'] = stats['crossover_stats']['avg_tiles_completed']
            
            writer.writerow(row)

def calculate_summary_statistics(results):
    """Calculate summary statistics for results."""
    summary = {}
    
    # Group by algorithm and configuration
    groups = {}
    for r in results:
        key = f"{r['algorithm']}_T{r['tiles']}_n{r['n']}_m{r['m']}"
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    
    for key, group in groups.items():
        objectives = [r['objective'] for r in group]
        runtimes = [r['runtime'] for r in group]
        
        stats = {
            'algorithm': group[0]['algorithm'],
            'tiles': group[0]['tiles'],
            'n': group[0]['n'],
            'm': group[0]['m'],
            'num_runs': len(group),
            'objective': {
                'mean': sum(objectives) / len(objectives),
                'min': min(objectives),
                'max': max(objectives),
                'std': (sum((x - sum(objectives)/len(objectives))**2 for x in objectives) / len(objectives))**0.5 if len(objectives) > 1 else 0
            },
            'runtime': {
                'mean': sum(runtimes) / len(runtimes),
                'min': min(runtimes),
                'max': max(runtimes),
                'std': (sum((x - sum(runtimes)/len(runtimes))**2 for x in runtimes) / len(runtimes))**0.5 if len(runtimes) > 1 else 0
            }
        }
        
        # Add genetic algorithm specific stats
        if group[0].get('total_crossovers'):
            crossovers = [r['total_crossovers'] for r in group if r.get('total_crossovers')]
            completions = [r['crossovers_needing_completion'] for r in group if r.get('crossovers_needing_completion')]
            tiles_completed = [r['total_tiles_completed'] for r in group if r.get('total_tiles_completed')]
            
            if crossovers:
                stats['crossover_stats'] = {
                    'avg_total_crossovers': sum(crossovers) / len(crossovers),
                    'avg_completions': sum(completions) / len(completions),
                    'avg_completion_rate': sum(c/t for c, t in zip(completions, crossovers)) / len(crossovers),
                    'avg_tiles_completed': sum(tiles_completed) / len(tiles_completed) if tiles_completed else 0
                }
        
        summary[key] = stats
    
    return summary

def print_final_summary(all_results, output_dir):
    """Print and save final summary across all scales."""
    print(f"\n{'='*80}")
    print("FINAL SUMMARY - ALL SCALES")
    print(f"{'='*80}\n")
    
    # Group by scale and algorithm
    by_scale = {}
    for r in all_results:
        scale = r['scale']
        if scale not in by_scale:
            by_scale[scale] = {}
        algo = r['algorithm']
        if algo not in by_scale[scale]:
            by_scale[scale][algo] = []
        by_scale[scale][algo].append(r)
    
    for scale in sorted(by_scale.keys()):
        print(f"\n{scale.upper()} Scale:")
        print("-" * 60)
        
        for algo in sorted(by_scale[scale].keys()):
            results = by_scale[scale][algo]
            objectives = [r['objective'] for r in results]
            runtimes = [r['runtime'] for r in results]
            
            print(f"  {algo:25s}: Runs={len(results):3d}, "
                  f"Obj={sum(objectives)/len(objectives):.2f}±{(sum((x-sum(objectives)/len(objectives))**2 for x in objectives)/len(objectives))**0.5:.2f}, "
                  f"Time={sum(runtimes)/len(runtimes):.3f}±{(sum((x-sum(runtimes)/len(runtimes))**2 for x in runtimes)/len(runtimes))**0.5:.3f}s")
    
    # Save combined summary
    with open(output_dir / 'combined_summary.json', 'w') as f:
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_experiments': len(all_results),
            'by_scale': {scale: {
                algo: {
                    'num_runs': len(results),
                    'avg_objective': sum(r['objective'] for r in results) / len(results),
                    'avg_runtime': sum(r['runtime'] for r in results) / len(results)
                } for algo, results in algos.items()
            } for scale, algos in by_scale.items()}
        }
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✓ All experiments completed!")
    print(f"  Total experiments: {len(all_results)}")
    print(f"  Results directory: {output_dir.absolute()}")
    print(f"{'='*80}\n")

def main():
    parser = argparse.ArgumentParser(description='Run systematic MDSSP experiments across multiple scales')
    parser.add_argument('--scales', nargs='+', choices=['small', 'medium', 'large', 'all'],
                       default=['all'], help='Which scales to run (default: all)')
    parser.add_argument('--seed', type=int, default=42, help='Base random seed (default: 42)')
    parser.add_argument('--output-dir', type=str, default='experiments',
                       help='Output directory for all results (default: experiments)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be run without executing')
    
    args = parser.parse_args()
    
    # Determine which scales to run
    if 'all' in args.scales:
        scales_to_run = ['small', 'medium', 'large']
    else:
        scales_to_run = args.scales
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Save experiment metadata
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'scales': scales_to_run,
        'base_seed': args.seed,
        'configurations': {scale: EXPERIMENTS[scale] for scale in scales_to_run}
    }
    with open(output_dir / 'experiment_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    if args.dry_run:
        print("DRY RUN - Would execute:")
        for scale in scales_to_run:
            config = EXPERIMENTS[scale]
            print(f"\n{scale.upper()}:")
            for tiles in config['tiles']:
                for (n, m) in config['tile_size']:
                    total = config['runs'] * len(config['algorithms'])
                    print(f"  T={tiles}, n={n}, m={m}: {total} experiments")
        return
    
    # Run experiments for each scale
    all_results = []
    start_time = time.time()
    
    for scale in scales_to_run:
        config = EXPERIMENTS[scale]
        results, best, summary = run_experiment_suite(scale, config, args.seed, output_dir)
        all_results.extend(results)
    
    # Write combined CSV
    if all_results:
        write_results_to_csv(all_results, output_dir / 'combined_all_results.csv')
        print(f"✓ Combined CSV written to: {output_dir / 'combined_all_results.csv'}")
    
    # Print final summary
    total_time = time.time() - start_time
    print_final_summary(all_results, output_dir)
    print(f"Total execution time: {total_time/60:.1f} minutes")

if __name__ == '__main__':
    main()
