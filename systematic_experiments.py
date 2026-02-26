#!/usr/bin/env python3
"""
MDSSP Systematic Experiments - Multi-Scale Testing

This script runs systematic experiments across different problem scales:
- Small scale (T=6-10): With CPLEX as baseline
- Medium scale (T=20-30): Heuristics comparison
- Large scale (T=50-60): Scalability testing

All results are organized in the experiments/ directory.

Objective Types:
- 'square': Minimize max(width, height) - creates square-ish bounding boxes
- 'area': Minimize width × height - creates compact rectangular arrangements

Use --objective-type to override the default objective for all scales.
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
        'tile_size': [(3, 3), (5, 5), (10, 10)],
        'runs': 10,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic'],
        'pop_size': 100,
        'generations': 200,
        'cplex_time_limit': 300,  # CPLEX time limit in seconds
        'objective_type': 'square',  # 'square' or 'area'
        'description': 'Small scale with CPLEX baseline'
    },
    'medium': {
        'tiles': [20, 30, 50],
        'tile_size': [(3, 3), (5, 5), (10, 10)],
        'runs': 10,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic'],
        'pop_size': 150,
        'generations': 300,
        'cplex_time_limit': 2000,  # CPLEX time limit in seconds
        'objective_type': 'square',  # 'square' or 'area'
        'description': 'Medium scale with CPLEX baseline'
    },
    'large': {
        'tiles': [60, 80, 100],
        'tile_size': [(3, 3), (5, 5), (10, 10)],
        'runs': 10,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic'],
        'pop_size': 200,
        'generations': 400,
        'cplex_time_limit': 2000,  # CPLEX time limit in seconds
        'objective_type': 'square',  # 'square' or 'area'
        'description': 'Large scale scalability testing'
    }
}

def run_single_experiment(algorithm, tiles, n, m, seed, output_file, pop_size=None, generations=None, objective_type=None, cplex_time_limit=None):
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
    
    if objective_type:
        cmd.extend(["--objective-type", objective_type])
     
    if algorithm == 'cplex' and cplex_time_limit:
        cmd.extend(["--time-limit", str(cplex_time_limit)])
    
    if algorithm in ['genetic_greedy', 'genetic_stochastic']:
        if pop_size:
            cmd.extend(["--pop-size", str(pop_size)])
        if generations:
            cmd.extend(["--generations", str(generations)])
    
    subprocess_timeout = 10000    # Large timeout to let CPLEX run as long as needed
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=  subprocess_timeout)
        
        # Parse output
        output = result.stdout
        objective = None
        runtime = None
        bbox_width = None
        bbox_height = None
        num_tiles = None
        status = None
        total_crossovers = None
        crossovers_needing_completion = None
        total_tiles_completed = None
        
        for line in output.split('\n'):
            if 'Status:' in line and 'Algorithm Results' not in line:
                try:
                    status = line.split(':')[1].strip()
                except (ValueError, IndexError):
                    pass
            elif 'Objective (L):' in line:
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
                    
                # Check for error status in JSON (like "Model too large")
                if solution_data and 'results' in solution_data:
                    result_obj = solution_data['results'][0]
                    
                    # If there's an error status, return it immediately
                    if 'error' in result_obj or result_obj.get('status') in ['Model too large (too many origin variables)']:
                        error_msg = result_obj.get('error', result_obj.get('status', 'Unknown error'))
                        return {'success': False, 'error': error_msg}
                    
                    # Extract crossover stats from JSON if available
                    if 'total_crossovers' in result_obj:
                        total_crossovers = result_obj['total_crossovers']
                    if 'crossovers_needing_completion' in result_obj:
                        crossovers_needing_completion = result_obj['crossovers_needing_completion']
                    if 'total_tiles_completed' in result_obj:
                        total_tiles_completed = result_obj['total_tiles_completed']
                        
            except Exception as e:
                print(f"    Warning: Could not load solution JSON: {e}")
        
        # Check if we got valid results
        if result.returncode != 0:
            # Command failed, check stderr for error message
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return {'success': False, 'error': f'Command failed with code {result.returncode}: {error_msg}'}
        
        # Even with returncode 0, check if we parsed essential fields
        if objective is None or runtime is None:
            # Try to get error from stderr or stdout
            error_info = result.stderr.strip() if result.stderr else result.stdout[-500:] if result.stdout else "No output"
            return {'success': False, 'error': f'Parse failed: {error_info}'}
        
        return {
            'success': True,
            'status': status,
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
        # Even on timeout, CPLEX might have written a feasible solution to the file
        # Check if the JSON file exists and has valid results
        if Path(output_file).exists():
            try:
                with open(output_file, 'r') as f:
                    solution_data = json.load(f)
                    
                if solution_data and 'results' in solution_data and len(solution_data['results']) > 0:
                    result_obj = solution_data['results'][0]
                    
                    # Check if we have a valid solution (even if just feasible)
                    if 'objective' in result_obj and 'runtime_seconds' in result_obj:
                        return {
                            'success': True,
                            'status': result_obj.get('status', 'timeout'),
                            'objective': result_obj.get('objective'),
                            'runtime': result_obj.get('runtime_seconds'),
                            'bbox_width': result_obj.get('bbox_width'),
                            'bbox_height': result_obj.get('bbox_height'),
                            'num_tiles': result_obj.get('num_tiles_placed'),
                            'total_crossovers': result_obj.get('total_crossovers'),
                            'crossovers_needing_completion': result_obj.get('crossovers_needing_completion'),
                            'total_tiles_completed': result_obj.get('total_tiles_completed'),
                            'solution': solution_data
                        }
            except Exception as e:
                print(f"    Warning: Timeout occurred but couldn't parse output file: {e}")
        
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def is_experiment_completed(output_file):
    """Check if an experiment has already been completed or marked as failed."""
    if not Path(output_file).exists():
        return False
    
    try:
        with open(output_file, 'r') as f:
            data = json.load(f)
            # Check if the JSON file has valid results
            if 'results' in data and len(data['results']) > 0:
                result = data['results'][0]
                # Valid completed run has objective and runtime
                if 'objective' in result and 'runtime_seconds' in result:
                    return True
                # Failed/error marker also counts as "completed" (don't retry)
                if result.get('status') in ['failed', 'parse_failed', 'error']:
                    return True
    except:
        return False
    
    return False

def run_experiment_suite(scale, config, base_seed, output_dir, resume=True):
    """Run all experiments for a given scale."""
    print(f"\n{'='*80}")
    print(f"RUNNING {scale.upper()} SCALE EXPERIMENTS")
    print(f"{'='*80}")
    if 'description' in config:
        print(f"Description: {config['description']}")
    print(f"Tile counts: {config['tiles']}")
    print(f"Tile sizes: {config['tile_size']}")
    print(f"Algorithms: {config['algorithms']}")
    print(f"Objective type: {config.get('objective_type', 'square')} ({'max(H,W)' if config.get('objective_type', 'square') == 'square' else 'H×W'})")
    print(f"Runs per configuration: {config['runs']}")
    if resume:
        print(f"Resume mode: ON (will skip completed experiments)")
    print()
    
    scale_dir = output_dir / scale
    scale_dir.mkdir(exist_ok=True, parents=True)
    
    all_results = []
    best_results = {}
    
    # Load existing results if resuming
    completed_count = 0
    skipped_count = 0
    
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
                    
                    output_file = exp_dir / f"run_{run+1}_{algo}.json"
                    
                    # Check if already completed
                    if resume and is_experiment_completed(output_file):
                        skipped_count += 1
                        
                        # Load the existing result
                        try:
                            with open(output_file, 'r') as f:
                                solution_data = json.load(f)
                                if 'results' in solution_data and len(solution_data['results']) > 0:
                                    result_obj = solution_data['results'][0]
                                    
                                    # Check if this was a failed run
                                    if result_obj.get('status') in ['failed', 'parse_failed', 'error']:
                                        print(f"  [{algo}] ⊙ Previously failed (skipped)", flush=True)
                                        continue
                                    
                                    result_entry = {
                                        'scale': scale,
                                        'tiles': tiles,
                                        'n': n,
                                        'm': m,
                                        'run': run + 1,
                                        'seed': seed,
                                        'algorithm': algo,
                                        'objective_type': config.get('objective_type', 'square'),
                                        'status': result_obj.get('status'),
                                        'objective': result_obj.get('objective'),
                                        'runtime': result_obj.get('runtime_seconds'),
                                        'bbox_width': result_obj.get('bbox_width'),
                                        'bbox_height': result_obj.get('bbox_height'),
                                        'num_tiles': result_obj.get('num_tiles_placed')
                                    }
                                    
                                    # Add genetic algorithm specific stats
                                    if 'total_crossovers' in result_obj:
                                        result_entry['total_crossovers'] = result_obj['total_crossovers']
                                        result_entry['crossovers_needing_completion'] = result_obj.get('crossovers_needing_completion')
                                        result_entry['total_tiles_completed'] = result_obj.get('total_tiles_completed')
                                    
                                    all_results.append(result_entry)
                                    
                                    print(f"  [{algo}] ⊙ Already completed (skipped)", flush=True)
                                    
                                    # Track best result (only if we have a valid objective)
                                    if result_entry['objective'] is not None:
                                        key = f"{exp_name}_{algo}"
                                        if key not in best_results or (best_results[key]['objective'] is not None and result_entry['objective'] < best_results[key]['objective']):
                                            best_results[key] = result_entry.copy()
                                            best_results[key]['solution'] = solution_data
                        except Exception as e:
                            print(f"  [{algo}] ⊙ Previously completed (warning: couldn't load: {e})", flush=True)
                        
                        continue
                    
                    print(f"  [{algo}] ", end='', flush=True)
                    
                    result = run_single_experiment(
                        algo, tiles, n, m, seed, str(output_file),
                        config.get('pop_size'), config.get('generations'),
                        config.get('objective_type'), config.get('cplex_time_limit')
                    )
                    
                    completed_count += 1
                    
                    if result['success']:
                        obj = result['objective']
                        runtime = result['runtime']
                        status = result.get('status')
                        
                        # Check if parsing failed - handle missing output file gracefully
                        if obj is None or runtime is None:
                            if not Path(output_file).exists():
                                print(f"✗ No output file (process may have been killed before completing)")
                                result['success'] = False
                                result['error'] = 'no_output_file'
                            # Otherwise parsing succeeded but got None values - will be handled below
                        
                        if obj is not None and runtime is not None:
                            # Show status indicator for CPLEX feasible (non-optimal) solutions
                            status_marker = "✓"
                            if status == "feasible":
                                status_marker = "≈"  # Approximate/feasible but not optimal
                            
                            print(f"{status_marker} Obj={obj}, Time={runtime:.3f}s", end='')
                            
                            # Add crossover stats if available
                            if result['total_crossovers'] and result['crossovers_needing_completion'] is not None:
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
                                'objective_type': config.get('objective_type', 'square'),
                                'status': status,
                                'objective': obj,
                                'runtime': runtime,
                                'bbox_width': result['bbox_width'],
                                'bbox_height': result['bbox_height'],
                                'num_tiles': result['num_tiles']
                            }
                            
                            # Add genetic algorithm specific stats
                            if result.get('total_crossovers') is not None:
                                result_entry['total_crossovers'] = result['total_crossovers']
                                result_entry['crossovers_needing_completion'] = result.get('crossovers_needing_completion')
                                result_entry['total_tiles_completed'] = result.get('total_tiles_completed')
                            
                            all_results.append(result_entry)
                            
                            # Track best result
                            key = f"{exp_name}_{algo}"
                            if key not in best_results or obj < best_results[key]['objective']:
                                best_results[key] = result_entry.copy()
                                best_results[key]['solution'] = result['solution']
                        else:
                            # This shouldn't happen now with improved error detection
                            print("✗ Parse failed (unexpected)")
                            # Save failure marker so we don't retry this indefinitely
                            failure_data = {
                                'input': {
                                    'T': tiles,
                                    'n': n,
                                    'm': m,
                                    'seed': seed,
                                    'objective_type': config.get('objective_type', 'square')
                                },
                                'results': [{
                                    'algorithm': algo,
                                    'status': 'parse_failed',
                                    'error': 'Failed to parse algorithm output (unexpected)'
                                }]
                            }
                            with open(output_file, 'w') as f:
                                json.dump(failure_data, f, indent=2)
                    else:
                        error_msg = result.get('error', 'unknown error')
                        # Truncate very long error messages for display
                        if len(error_msg) > 200:
                            error_msg = error_msg[:200] + "..."
                        print(f"✗ {error_msg}")
                        # Save failure marker
                        failure_data = {
                            'input': {
                                'T': tiles,
                                'n': n,
                                'm': m,
                                'seed': seed,
                                'objective_type': config.get('objective_type', 'square')
                            },
                            'results': [{
                                'algorithm': algo,
                                'status': 'failed',
                                'error': error_msg
                            }]
                        }
                        with open(output_file, 'w') as f:
                            json.dump(failure_data, f, indent=2)
            
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
    if resume:
        print(f"  New experiments run: {completed_count}")
        print(f"  Skipped (already done): {skipped_count}")
    print(f"  Results saved to: {scale_dir}")
    print(f"  CSV files: all_results.csv, summary_statistics.csv")
    print(f"{'='*80}")
    
    return all_results, best_results, summary

def write_results_to_csv(results, output_file):
    """Write all results to a CSV file."""
    if not results:
        return
    
    # Determine all possible fields
    fieldnames = ['scale', 'tiles', 'n', 'm', 'run', 'seed', 'algorithm', 'objective_type',
                  'status', 'objective', 'runtime', 'bbox_width', 'bbox_height', 'num_tiles',
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
    
    fieldnames = ['algorithm', 'tiles', 'n', 'm', 'num_runs', 'successful_runs',
                  'obj_mean', 'obj_min', 'obj_max', 'obj_std',
                  'runtime_mean', 'runtime_min', 'runtime_max', 'runtime_std',
                  'crossovers_mean', 'completion_rate_mean', 'tiles_completed_mean',
                  'cplex_optimal', 'cplex_feasible', 'cplex_infeasible', 'cplex_timeout', 'cplex_failed']
    
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
                'successful_runs': stats.get('successful_runs', stats['num_runs']),
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
            
            # Add CPLEX status counts
            if 'cplex_status_counts' in stats:
                row['cplex_optimal'] = stats['cplex_status_counts']['optimal']
                row['cplex_feasible'] = stats['cplex_status_counts']['feasible']
                row['cplex_infeasible'] = stats['cplex_status_counts']['infeasible']
                row['cplex_timeout'] = stats['cplex_status_counts']['timeout']
                row['cplex_failed'] = stats['cplex_status_counts']['failed']
            
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
        # Filter out None values from failed experiments
        objectives = [r['objective'] for r in group if r['objective'] is not None]
        runtimes = [r['runtime'] for r in group if r['runtime'] is not None]
        
        # Skip if no valid data
        if not objectives or not runtimes:
            continue
        
        stats = {
            'algorithm': group[0]['algorithm'],
            'tiles': group[0]['tiles'],
            'n': group[0]['n'],
            'm': group[0]['m'],
            'num_runs': len(group),
            'successful_runs': len(objectives),
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
        
        # Add CPLEX-specific status counts
        if group[0]['algorithm'] == 'cplex':
            status_counts = {
                'optimal': sum(1 for r in group if r.get('status') == 'optimal'),
                'feasible': sum(1 for r in group if r.get('status') == 'feasible'),
                'infeasible': sum(1 for r in group if r.get('status') == 'infeasible'),
                'timeout': sum(1 for r in group if r.get('status') == 'timeout'),
                'failed': sum(1 for r in group if r.get('status') in ['failed', 'parse_failed', 'error'])
            }
            stats['cplex_status_counts'] = status_counts
        
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
    parser.add_argument('--objective-type', type=str, choices=['square', 'area'],
                       help='Override objective type for all scales (square=max(H,W), area=H*W)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be run without executing')
    parser.add_argument('--no-resume', action='store_true', 
                       help='Disable resume mode (run all experiments even if already completed)')
    
    args = parser.parse_args()
    
    resume_mode = not args.no_resume
    
    # Determine which scales to run
    if 'all' in args.scales:
        scales_to_run = ['small', 'medium', 'large']
    else:
        scales_to_run = args.scales
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Check if resuming from previous run
    metadata_file = output_dir / 'experiment_metadata.json'
    if resume_mode and metadata_file.exists():
        with open(metadata_file, 'r') as f:
            prev_metadata = json.load(f)
        print(f"\n{'='*80}")
        print(f"RESUMING FROM PREVIOUS RUN")
        print(f"{'='*80}")
        print(f"Previous run started: {prev_metadata.get('timestamp', 'unknown')}")
        print(f"Scales: {prev_metadata.get('scales', [])}")
        print(f"Base seed: {prev_metadata.get('base_seed', 'unknown')}")
        print(f"Resume mode: ENABLED - Will skip completed experiments")
        print(f"{'='*80}\n")
    
    # Save experiment metadata
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'scales': scales_to_run,
        'base_seed': args.seed,
        'resume_mode': resume_mode,
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
        config = EXPERIMENTS[scale].copy()
        # Override objective type if specified
        if args.objective_type:
            config['objective_type'] = args.objective_type
        results, best, summary = run_experiment_suite(scale, config, args.seed, output_dir, resume=resume_mode)
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
