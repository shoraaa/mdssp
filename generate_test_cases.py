#!/usr/bin/env python3
"""
Generate all test case configurations from systematic_experiments.py

This script generates JSON dataset files for each test case that would be run
in the systematic experiments, allowing you to test individual cases or debug
specific seed/configuration combinations.

Usage:
    python generate_test_cases.py --scale medium --output-dir test_cases/
    python generate_test_cases.py --all --output-dir test_cases/
    python generate_test_cases.py --scale medium --seed-only  # Just print seeds
"""

import json
import subprocess
import argparse
from pathlib import Path

# Import experiment configurations from systematic_experiments
EXPERIMENTS = {
    'small': {
        'tiles': [6, 8, 10],
        'tile_size': [(3, 3)],
        'runs': 30,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'cplex'],
        'pop_size': 100,
        'generations': 200,
        'cplex_time_limit': 2000,
        'objective_type': 'square',
        'description': 'Small scale with CPLEX baseline'
    },
    'medium': {
        'tiles': [20, 30, 50],
        'tile_size': [(3, 3)],
        'runs': 30,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'cplex'],
        'pop_size': 150,
        'generations': 300,
        'cplex_time_limit': 2000,
        'objective_type': 'square',
        'description': 'Medium scale with CPLEX baseline'
    },
    'large': {
        'tiles': [60, 80, 100],
        'tile_size': [(3, 3)],
        'runs': 20,
        'algorithms': ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'cplex'],
        'pop_size': 200,
        'generations': 400,
        'cplex_time_limit': 2000,
        'objective_type': 'square',
        'description': 'Large scale scalability testing'
    }
}

BASE_SEED = 42

def generate_dataset(tiles, n, m, seed, output_file):
    """Generate a dataset file using the mdssp binary."""
    cmd = [
        "./mdssp",
        "-a", "greedy",  # Use greedy just to generate the dataset
        "-T", str(tiles),
        "-n", str(n),
        "-m", str(m),
        "-s", str(seed),
        "-o", str(output_file)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, None
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def list_test_cases(scale, config, base_seed):
    """List all test cases for a given scale."""
    cases = []
    
    for tiles in config['tiles']:
        for (n, m) in config['tile_size']:
            for run in range(config['runs']):
                seed = base_seed + run * 100
                
                case = {
                    'scale': scale,
                    'tiles': tiles,
                    'n': n,
                    'm': m,
                    'run': run + 1,
                    'seed': seed,
                    'exp_name': f"T{tiles}_n{n}_m{m}",
                    'algorithms': config['algorithms'],
                    'pop_size': config.get('pop_size'),
                    'generations': config.get('generations'),
                    'cplex_time_limit': config.get('cplex_time_limit'),
                    'objective_type': config.get('objective_type', 'square')
                }
                cases.append(case)
    
    return cases

def main():
    parser = argparse.ArgumentParser(
        description='Generate test case configurations from systematic_experiments'
    )
    parser.add_argument(
        '--scale',
        choices=['small', 'medium', 'large'],
        help='Scale to generate test cases for'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Generate test cases for all scales'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='test_cases',
        help='Output directory for generated datasets (default: test_cases/)'
    )
    parser.add_argument(
        '--seed-only',
        action='store_true',
        help='Only print seed information without generating datasets'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'csv', 'table'],
        default='table',
        help='Output format for seed information (default: table)'
    )
    parser.add_argument(
        '--filter-seed',
        type=int,
        help='Filter to show only specific seed'
    )
    parser.add_argument(
        '--filter-tiles',
        type=int,
        help='Filter to show only specific tile count'
    )
    parser.add_argument(
        '--generate-datasets',
        action='store_true',
        help='Generate actual dataset JSON files (requires mdssp binary)'
    )
    
    args = parser.parse_args()
    
    if not args.scale and not args.all:
        parser.error('Must specify either --scale or --all')
    
    scales = ['small', 'medium', 'large'] if args.all else [args.scale]
    
    all_cases = []
    for scale in scales:
        config = EXPERIMENTS[scale]
        cases = list_test_cases(scale, config, BASE_SEED)
        all_cases.extend(cases)
    
    # Apply filters
    if args.filter_seed:
        all_cases = [c for c in all_cases if c['seed'] == args.filter_seed]
    if args.filter_tiles:
        all_cases = [c for c in all_cases if c['tiles'] == args.filter_tiles]
    
    if args.seed_only:
        # Just print seed information
        if args.format == 'json':
            print(json.dumps(all_cases, indent=2))
        elif args.format == 'csv':
            import csv
            import sys
            writer = csv.DictWriter(
                sys.stdout,
                fieldnames=['scale', 'exp_name', 'run', 'seed', 'tiles', 'n', 'm', 'objective_type']
            )
            writer.writeheader()
            for case in all_cases:
                writer.writerow({
                    'scale': case['scale'],
                    'exp_name': case['exp_name'],
                    'run': case['run'],
                    'seed': case['seed'],
                    'tiles': case['tiles'],
                    'n': case['n'],
                    'm': case['m'],
                    'objective_type': case['objective_type']
                })
        else:  # table format
            print(f"\n{'='*100}")
            print(f"Test Cases Summary ({len(all_cases)} total)")
            print(f"{'='*100}")
            print(f"{'Scale':<8} {'Exp Name':<15} {'Run':<5} {'Seed':<8} {'T':<4} {'n×m':<6} {'Algorithms':<40} {'Objective':<10}")
            print(f"{'-'*100}")
            
            for case in all_cases:
                algos = ', '.join(case['algorithms'][:3])
                if len(case['algorithms']) > 3:
                    algos += f" +{len(case['algorithms'])-3}"
                
                print(f"{case['scale']:<8} {case['exp_name']:<15} {case['run']:<5} "
                      f"{case['seed']:<8} {case['tiles']:<4} {case['n']}×{case['m']:<4} "
                      f"{algos:<40} {case['objective_type']:<10}")
            
            print(f"{'-'*100}")
            print(f"\nBreakdown by scale:")
            for scale in scales:
                count = len([c for c in all_cases if c['scale'] == scale])
                print(f"  {scale}: {count} test cases")
    
    elif args.generate_datasets:
        # Generate actual dataset files
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*80}")
        print(f"Generating {len(all_cases)} dataset files")
        print(f"Output directory: {output_dir}")
        print(f"{'='*80}\n")
        
        success_count = 0
        fail_count = 0
        
        for i, case in enumerate(all_cases, 1):
            scale_dir = output_dir / case['scale'] / case['exp_name']
            scale_dir.mkdir(parents=True, exist_ok=True)
            
            output_file = scale_dir / f"dataset_run{case['run']}_seed{case['seed']}.json"
            
            print(f"[{i}/{len(all_cases)}] Generating {case['scale']}/{case['exp_name']}/run{case['run']} (seed={case['seed']})...", end=' ', flush=True)
            
            success, error = generate_dataset(
                case['tiles'], case['n'], case['m'], case['seed'], output_file
            )
            
            if success:
                print("✓")
                success_count += 1
            else:
                print(f"✗ ({error})")
                fail_count += 1
        
        print(f"\n{'='*80}")
        print(f"Summary: {success_count} successful, {fail_count} failed")
        print(f"{'='*80}")
    
    else:
        # Generate test case metadata only
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save all test cases to a JSON file
        metadata_file = output_dir / 'test_cases_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump({
                'generated_at': str(Path.cwd()),
                'base_seed': BASE_SEED,
                'total_cases': len(all_cases),
                'scales': scales,
                'test_cases': all_cases
            }, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"Generated metadata for {len(all_cases)} test cases")
        print(f"Saved to: {metadata_file}")
        print(f"{'='*80}\n")
        
        # Print summary
        print("Breakdown by scale:")
        for scale in scales:
            count = len([c for c in all_cases if c['scale'] == scale])
            print(f"  {scale}: {count} test cases")
        
        print(f"\nTo view details, run:")
        print(f"  python {__file__} --scale {scales[0]} --seed-only")
        print(f"\nTo generate actual datasets, run:")
        print(f"  python {__file__} --scale {scales[0]} --generate-datasets")

if __name__ == '__main__':
    main()
