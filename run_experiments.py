#!/usr/bin/env python3
"""
MDSSP Algorithm Comparison - Experiment Runner

This script runs multiple experiments for different algorithms and saves results
to files that can be visualized by the Jupyter notebook.

Usage:
    python run_experiments.py [--tiles TILES] [--n N] [--m M] [--runs RUNS] [--seed SEED]
"""

import json
import subprocess
import argparse
from pathlib import Path
from collections import defaultdict
import sys

def get_actual_bbox(solution, tiles_data):
    """Calculate actual bounding box from solution placements."""
    if solution is None or 'results' not in solution:
        return None, None
    
    result = solution['results'][0]
    placements = result['placements']
    
    xs, ys = [], []
    for placement in placements:
        tile_id = placement['tile_id']
        dx, dy = placement['x'], placement['y']
        tile_shape = tiles_data[tile_id]
        
        for y, row in enumerate(tile_shape):
            for x, cell in enumerate(row):
                if cell == 1:
                    xs.append(x + dx)
                    ys.append(y + dy)
    
    if not xs:
        return None, None
    
    width = max(xs) - min(xs) + 1
    height = max(ys) - min(ys) + 1
    return width, height

def run_algorithm(algorithm, tiles, n, m, seed, tiles_data, pop_size=None, generations=None, 
                  time_limit=None, init_mode=None, output_file="temp_solution.json"):
    """Run MDSSP algorithm and return results."""
    cmd = [
        "./mdssp",
        "-a", algorithm,
        "-T", str(tiles),
        "-n", str(n),
        "-m", str(m),
        "-s", str(seed),
        "-o", output_file
    ]
    
    if algorithm == "genetic":
        if pop_size:
            cmd.extend(["--pop-size", str(pop_size)])
        if generations:
            cmd.extend(["--generations", str(generations)])
        if init_mode:
            cmd.extend(["--init-mode", init_mode])
    
    if algorithm == "bnb":
        if time_limit:
            cmd.extend(["--time-limit", str(time_limit)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Parse output to extract objective and runtime
    output = result.stdout
    objective = None
    runtime = None
    bbox_width = None
    bbox_height = None
    nodes_explored = None
    nodes_pruned = None
    
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
        elif 'Nodes explored:' in line:
            try:
                nodes_explored = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
        elif 'Nodes pruned:' in line:
            try:
                nodes_pruned = int(line.split(':')[1].strip())
            except (ValueError, IndexError):
                pass
    
    # Load solution if it exists
    solution = None
    if Path(output_file).exists():
        try:
            with open(output_file, 'r') as f:
                solution = json.load(f)
            Path(output_file).unlink()  # Clean up
        except Exception:
            pass
    
    # Recalculate bounding box from actual solution
    if solution:
        width, height = get_actual_bbox(solution, tiles_data)
        if width and height:
            bbox_width = width
            bbox_height = height
            objective = max(width, height)
    
    # ALWAYS recalculate objective from bbox dimensions to ensure consistency
    if bbox_width is not None and bbox_height is not None:
        objective = max(bbox_width, bbox_height)
    
    return {
        'objective': objective,
        'runtime': runtime,
        'bbox_width': bbox_width,
        'bbox_height': bbox_height,
        'nodes_explored': nodes_explored,
        'nodes_pruned': nodes_pruned,
        'solution': solution
    }

def main():
    parser = argparse.ArgumentParser(description='Run MDSSP algorithm comparison experiments')
    parser.add_argument('--tiles', type=int, default=6, help='Number of tiles (default: 6)')
    parser.add_argument('--n', type=int, default=3, help='Tile height (default: 3)')
    parser.add_argument('--m', type=int, default=3, help='Tile width (default: 3)')
    parser.add_argument('--runs', type=int, default=30, help='Number of runs per algorithm (default: 30)')
    parser.add_argument('--seed', type=int, default=42, help='Base random seed (default: 42)')
    parser.add_argument('--pop-size', type=int, default=128, help='Genetic algorithm population size (default: 20)')
    parser.add_argument('--generations', type=int, default=64, help='Genetic algorithm generations (default: 10)')
    parser.add_argument('--bnb-time-limit', type=int, default=10, help='Branch & Bound time limit in seconds (default: 10)')
    parser.add_argument('--output-dir', type=str, default='results', help='Output directory for results (default: results)')
    parser.add_argument('--algorithms', type=str, nargs='+', 
                        default=['greedy', 'stochastic_greedy', 'genetic', 'genetic_greedy', 'genetic_stochastic', 'cplex'],
                        help='Algorithms to run (default: greedy stochastic_greedy genetic genetic_greedy genetic_stochastic cplex)')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print("="*80)
    print("MDSSP Algorithm Comparison - Experiment Runner")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  Tiles: {args.tiles}")
    print(f"  Tile size: {args.n} × {args.m}")
    print(f"  Number of runs: {args.runs}")
    print(f"  Base seed: {args.seed}")
    print(f"  Algorithms: {', '.join(args.algorithms)}")
    print(f"  Output directory: {output_dir}")
    print()
    
    # Load tile data
    with open('dataset.json', 'r') as f:
        dataset = json.load(f)
    tiles_data = dataset['tiles']
    
    results_data = []
    best_results = {}
    
    for run in range(args.runs):
        seed = args.seed + run * 100
        print(f"Run {run + 1}/{args.runs} (seed={seed})")
        
        # Greedy
        if 'greedy' in args.algorithms:
            print("  - Greedy...", end=' ', flush=True)
            try:
                greedy_res = run_algorithm("greedy", args.tiles, args.n, args.m, seed, tiles_data,
                                          output_file=f"temp_greedy_{run}.json")
                if greedy_res['objective'] is not None and greedy_res['runtime'] is not None:
                    results_data.append({
                        'run': run + 1,
                        'algorithm': 'Greedy',
                        'seed': seed,
                        'objective': greedy_res['objective'],
                        'runtime': greedy_res['runtime'],
                        'bbox_width': greedy_res['bbox_width'],
                        'bbox_height': greedy_res['bbox_height']
                    })
                    print(f"Obj: {greedy_res['objective']}, Time: {greedy_res['runtime']:.3f}s")
                    
                    if 'Greedy' not in best_results or greedy_res['objective'] < best_results['Greedy']['objective']:
                        best_results['Greedy'] = {
                            'objective': greedy_res['objective'],
                            'runtime': greedy_res['runtime'],
                            'bbox_width': greedy_res['bbox_width'],
                            'bbox_height': greedy_res['bbox_height'],
                            'run': run + 1,
                            'seed': seed
                        }
                        # Save best solution
                        if greedy_res['solution']:
                            with open(output_dir / 'best_greedy_solution.json', 'w') as f:
                                json.dump(greedy_res['solution'], f, indent=2)
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
        
        # Stochastic Greedy
        if 'stochastic_greedy' in args.algorithms:
            print("  - Stochastic Greedy...", end=' ', flush=True)
            try:
                stoch_res = run_algorithm("greedy", args.tiles, args.n, args.m, seed + 1, tiles_data,
                                         output_file=f"temp_stoch_{run}.json")
                if stoch_res['objective'] is not None and stoch_res['runtime'] is not None:
                    results_data.append({
                        'run': run + 1,
                        'algorithm': 'Stochastic Greedy',
                        'seed': seed + 1,
                        'objective': stoch_res['objective'],
                        'runtime': stoch_res['runtime'],
                        'bbox_width': stoch_res['bbox_width'],
                        'bbox_height': stoch_res['bbox_height']
                    })
                    print(f"Obj: {stoch_res['objective']}, Time: {stoch_res['runtime']:.3f}s")
                    
                    if 'Stochastic Greedy' not in best_results or stoch_res['objective'] < best_results['Stochastic Greedy']['objective']:
                        best_results['Stochastic Greedy'] = {
                            'objective': stoch_res['objective'],
                            'runtime': stoch_res['runtime'],
                            'bbox_width': stoch_res['bbox_width'],
                            'bbox_height': stoch_res['bbox_height'],
                            'run': run + 1,
                            'seed': seed + 1
                        }
                        if stoch_res['solution']:
                            with open(output_dir / 'best_stochastic_greedy_solution.json', 'w') as f:
                                json.dump(stoch_res['solution'], f, indent=2)
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
        
        # Genetic
        if 'genetic' in args.algorithms:
            print("  - Genetic...", end=' ', flush=True)
            try:
                gen_res = run_algorithm("genetic", args.tiles, args.n, args.m, seed, tiles_data,
                                       args.pop_size, args.generations, 
                                       output_file=f"temp_genetic_{run}.json")
                if gen_res['objective'] is not None and gen_res['runtime'] is not None:
                    results_data.append({
                        'run': run + 1,
                        'algorithm': 'Genetic',
                        'seed': seed,
                        'objective': gen_res['objective'],
                        'runtime': gen_res['runtime'],
                        'bbox_width': gen_res['bbox_width'],
                        'bbox_height': gen_res['bbox_height']
                    })
                    print(f"Obj: {gen_res['objective']}, Time: {gen_res['runtime']:.3f}s")
                    
                    if 'Genetic' not in best_results or gen_res['objective'] < best_results['Genetic']['objective']:
                        best_results['Genetic'] = {
                            'objective': gen_res['objective'],
                            'runtime': gen_res['runtime'],
                            'bbox_width': gen_res['bbox_width'],
                            'bbox_height': gen_res['bbox_height'],
                            'run': run + 1,
                            'seed': seed
                        }
                        if gen_res['solution']:
                            with open(output_dir / 'best_genetic_solution.json', 'w') as f:
                                json.dump(gen_res['solution'], f, indent=2)
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
        
        # Genetic with Greedy Initialization
        if 'genetic_greedy' in args.algorithms:
            print("  - Genetic (Greedy Init)...", end=' ', flush=True)
            try:
                gen_greedy_res = run_algorithm("genetic", args.tiles, args.n, args.m, seed, tiles_data,
                                               args.pop_size, args.generations, 
                                               init_mode="greedy",
                                               output_file=f"temp_genetic_greedy_{run}.json")
                if gen_greedy_res['objective'] is not None and gen_greedy_res['runtime'] is not None:
                    results_data.append({
                        'run': run + 1,
                        'algorithm': 'GA (Greedy Init)',
                        'seed': seed,
                        'objective': gen_greedy_res['objective'],
                        'runtime': gen_greedy_res['runtime'],
                        'bbox_width': gen_greedy_res['bbox_width'],
                        'bbox_height': gen_greedy_res['bbox_height']
                    })
                    print(f"Obj: {gen_greedy_res['objective']}, Time: {gen_greedy_res['runtime']:.3f}s")
                    
                    if 'GA (Greedy Init)' not in best_results or gen_greedy_res['objective'] < best_results['GA (Greedy Init)']['objective']:
                        best_results['GA (Greedy Init)'] = {
                            'objective': gen_greedy_res['objective'],
                            'runtime': gen_greedy_res['runtime'],
                            'bbox_width': gen_greedy_res['bbox_width'],
                            'bbox_height': gen_greedy_res['bbox_height'],
                            'run': run + 1,
                            'seed': seed
                        }
                        if gen_greedy_res['solution']:
                            with open(output_dir / 'best_genetic_greedy_solution.json', 'w') as f:
                                json.dump(gen_greedy_res['solution'], f, indent=2)
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
        
        # Genetic with Stochastic Greedy Initialization
        if 'genetic_stochastic' in args.algorithms:
            print("  - Genetic (Stochastic Init)...", end=' ', flush=True)
            try:
                gen_stoch_res = run_algorithm("genetic", args.tiles, args.n, args.m, seed, tiles_data,
                                              args.pop_size, args.generations, 
                                              init_mode="stochastic",
                                              output_file=f"temp_genetic_stoch_{run}.json")
                if gen_stoch_res['objective'] is not None and gen_stoch_res['runtime'] is not None:
                    results_data.append({
                        'run': run + 1,
                        'algorithm': 'GA (Stochastic Init)',
                        'seed': seed,
                        'objective': gen_stoch_res['objective'],
                        'runtime': gen_stoch_res['runtime'],
                        'bbox_width': gen_stoch_res['bbox_width'],
                        'bbox_height': gen_stoch_res['bbox_height']
                    })
                    print(f"Obj: {gen_stoch_res['objective']}, Time: {gen_stoch_res['runtime']:.3f}s")
                    
                    if 'GA (Stochastic Init)' not in best_results or gen_stoch_res['objective'] < best_results['GA (Stochastic Init)']['objective']:
                        best_results['GA (Stochastic Init)'] = {
                            'objective': gen_stoch_res['objective'],
                            'runtime': gen_stoch_res['runtime'],
                            'bbox_width': gen_stoch_res['bbox_width'],
                            'bbox_height': gen_stoch_res['bbox_height'],
                            'run': run + 1,
                            'seed': seed
                        }
                        if gen_stoch_res['solution']:
                            with open(output_dir / 'best_genetic_stochastic_solution.json', 'w') as f:
                                json.dump(gen_stoch_res['solution'], f, indent=2)
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
        
        # CPLEX
        if 'cplex' in args.algorithms:
            print("  - CPLEX...", end=' ', flush=True)
            try:
                cplex_res = run_algorithm("cplex", args.tiles, args.n, args.m, seed, tiles_data,
                                         output_file=f"temp_cplex_{run}.json")
                if cplex_res['objective'] is not None and cplex_res['runtime'] is not None:
                    results_data.append({
                        'run': run + 1,
                        'algorithm': 'CPLEX',
                        'seed': seed,
                        'objective': cplex_res['objective'],
                        'runtime': cplex_res['runtime'],
                        'bbox_width': cplex_res['bbox_width'],
                        'bbox_height': cplex_res['bbox_height']
                    })
                    print(f"Obj: {cplex_res['objective']}, Time: {cplex_res['runtime']:.3f}s")
                    
                    if 'CPLEX' not in best_results or cplex_res['objective'] < best_results['CPLEX']['objective']:
                        best_results['CPLEX'] = {
                            'objective': cplex_res['objective'],
                            'runtime': cplex_res['runtime'],
                            'bbox_width': cplex_res['bbox_width'],
                            'bbox_height': cplex_res['bbox_height'],
                            'run': run + 1,
                            'seed': seed
                        }
                        if cplex_res['solution']:
                            with open(output_dir / 'best_cplex_solution.json', 'w') as f:
                                json.dump(cplex_res['solution'], f, indent=2)
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
        
        # Branch and Bound
        if 'bnb' in args.algorithms:
            print("  - Branch & Bound...", end=' ', flush=True)
            try:
                bnb_res = run_algorithm("bnb", args.tiles, args.n, args.m, seed, tiles_data,
                                       time_limit=args.bnb_time_limit,
                                       output_file=f"temp_bnb_{run}.json")
                if bnb_res['objective'] is not None and bnb_res['runtime'] is not None:
                    results_data.append({
                        'run': run + 1,
                        'algorithm': 'Branch & Bound',
                        'seed': seed,
                        'objective': bnb_res['objective'],
                        'runtime': bnb_res['runtime'],
                        'bbox_width': bnb_res['bbox_width'],
                        'bbox_height': bnb_res['bbox_height'],
                        'nodes_explored': bnb_res['nodes_explored'],
                        'nodes_pruned': bnb_res['nodes_pruned']
                    })
                    print(f"Obj: {bnb_res['objective']}, Time: {bnb_res['runtime']:.3f}s, Nodes: {bnb_res['nodes_explored']}")
                    
                    if 'Branch & Bound' not in best_results or bnb_res['objective'] < best_results['Branch & Bound']['objective']:
                        best_results['Branch & Bound'] = {
                            'objective': bnb_res['objective'],
                            'runtime': bnb_res['runtime'],
                            'bbox_width': bnb_res['bbox_width'],
                            'bbox_height': bnb_res['bbox_height'],
                            'nodes_explored': bnb_res['nodes_explored'],
                            'nodes_pruned': bnb_res['nodes_pruned'],
                            'run': run + 1,
                            'seed': seed
                        }
                        if bnb_res['solution']:
                            with open(output_dir / 'best_bnb_solution.json', 'w') as f:
                                json.dump(bnb_res['solution'], f, indent=2)
                else:
                    print("FAILED")
            except Exception as e:
                print(f"ERROR: {e}")
        
        print()
    
    # Save all results
    print("\n" + "="*80)
    print("SAVING RESULTS")
    print("="*80)
    
    # Save raw results data
    with open(output_dir / 'all_results.json', 'w') as f:
        json.dump(results_data, f, indent=2)
    print(f"✓ Saved all results to {output_dir / 'all_results.json'}")
    
    # Save best results
    with open(output_dir / 'best_results.json', 'w') as f:
        json.dump(best_results, f, indent=2)
    print(f"✓ Saved best results to {output_dir / 'best_results.json'}")
    
    # Calculate and save summary statistics
    summary = {}
    for algo in set(r['algorithm'] for r in results_data):
        algo_results = [r for r in results_data if r['algorithm'] == algo]
        objectives = [r['objective'] for r in algo_results]
        runtimes = [r['runtime'] for r in algo_results]
        widths = [r['bbox_width'] for r in algo_results]
        heights = [r['bbox_height'] for r in algo_results]
        
        summary[algo] = {
            'num_runs': len(algo_results),
            'objective': {
                'mean': sum(objectives) / len(objectives),
                'min': min(objectives),
                'max': max(objectives),
                'std': (sum((x - sum(objectives)/len(objectives))**2 for x in objectives) / len(objectives))**0.5
            },
            'runtime': {
                'mean': sum(runtimes) / len(runtimes),
                'min': min(runtimes),
                'max': max(runtimes),
                'std': (sum((x - sum(runtimes)/len(runtimes))**2 for x in runtimes) / len(runtimes))**0.5
            },
            'bbox_width': {
                'mean': sum(widths) / len(widths),
                'std': (sum((x - sum(widths)/len(widths))**2 for x in widths) / len(widths))**0.5
            },
            'bbox_height': {
                'mean': sum(heights) / len(heights),
                'std': (sum((x - sum(heights)/len(heights))**2 for x in heights) / len(heights))**0.5
            }
        }
    
    with open(output_dir / 'summary_statistics.json', 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"✓ Saved summary statistics to {output_dir / 'summary_statistics.json'}")
    
    # Save experiment configuration
    config = {
        'tiles': args.tiles,
        'n': args.n,
        'm': args.m,
        'runs': args.runs,
        'seed': args.seed,
        'algorithms': args.algorithms,
        'pop_size': args.pop_size,
        'generations': args.generations,
        'bnb_time_limit': args.bnb_time_limit
    }
    with open(output_dir / 'experiment_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✓ Saved experiment configuration to {output_dir / 'experiment_config.json'}")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"\nTotal experiments completed: {len(results_data)}")
    print("\nBest results:")
    for algo, result in best_results.items():
        print(f"  {algo:20s}: Obj={result['objective']}, BBox={result['bbox_width']}×{result['bbox_height']}, Time={result['runtime']:.3f}s (run {result['run']})")
    
    print("\n✓ All results saved to:", output_dir.absolute())
    print("="*80)

if __name__ == '__main__':
    main()
