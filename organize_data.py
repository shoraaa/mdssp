#!/usr/bin/env python3
"""
Organize existing experiment data into the new experiments/ directory structure.
"""

import shutil
from pathlib import Path
import json

def organize_existing_data():
    """Move existing result directories into experiments/ with proper naming."""
    
    base_dir = Path('.')
    exp_dir = Path('experiments/legacy')
    exp_dir.mkdir(parents=True, exist_ok=True)
    
    # Directories to migrate
    migrations = [
        ('all10', 'legacy/all10'),
        ('all60', 'legacy/all60'),
        ('tiles30', 'legacy/tiles30'),
        ('tiles60', 'legacy/tiles60'),
        ('test_ga_comparison', 'legacy/test_ga_comparison'),
        ('results', 'legacy/results_old'),
    ]
    
    print("Organizing existing data into experiments/ directory...\n")
    
    for old_name, new_path in migrations:
        old_path = base_dir / old_name
        if old_path.exists() and old_path.is_dir():
            new_full_path = Path('experiments') / new_path
            new_full_path.parent.mkdir(parents=True, exist_ok=True)
            
            print(f"Moving {old_name}/ -> experiments/{new_path}/")
            try:
                if new_full_path.exists():
                    print(f"  Warning: {new_full_path} already exists, skipping...")
                else:
                    shutil.move(str(old_path), str(new_full_path))
                    print(f"  ✓ Moved successfully")
            except Exception as e:
                print(f"  ✗ Error: {e}")
    
    # Move standalone result files
    result_files = [
        'algorithm_comparison_results.csv',
        'algorithm_comparison_summary.txt',
        'results.json',
        'solution.json',
        'cplex_solution.json',
        'test_cplex.json',
        'test_all_output.json',
        'test_all_output2.json',
        'test_no_bnb.json',
        'test_stats.json'
    ]
    
    legacy_files_dir = Path('experiments/legacy/standalone_files')
    legacy_files_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\nMoving standalone result files to experiments/legacy/standalone_files/")
    for filename in result_files:
        filepath = base_dir / filename
        if filepath.exists():
            dest = legacy_files_dir / filename
            if dest.exists():
                print(f"  {filename}: already exists, skipping...")
            else:
                try:
                    shutil.copy2(str(filepath), str(dest))
                    print(f"  ✓ {filename}")
                except Exception as e:
                    print(f"  ✗ {filename}: {e}")
    
    # Create README for legacy data
    readme_content = """# Legacy Experiment Data

This directory contains experiment data from previous runs before the systematic
organization was established.

## Directory Structure

- `all10/`: Results for 10-tile experiments
- `all60/`: Results for 60-tile experiments  
- `tiles30/`: Results for 30-tile experiments
- `tiles60/`: Results for 60-tile experiments
- `test_ga_comparison/`: Genetic algorithm comparison tests
- `results_old/`: Old results directory
- `standalone_files/`: Individual result files from various tests

## Notes

- These results were generated before the systematic experiment framework
- File formats and naming conventions may differ from current experiments
- Refer to the main experiments/ directory for new systematically generated data
"""
    
    with open(exp_dir / 'README.md', 'w') as f:
        f.write(readme_content)
    
    print(f"\n✓ Created README at experiments/legacy/README.md")
    
    # Create main experiments README
    main_readme = """# MDSSP Experiments

This directory contains all experimental results for the MDSSP solver.

## Directory Structure

```
experiments/
├── small/          # Small-scale instances (T=6-10) with CPLEX baseline
├── medium/         # Medium-scale instances (T=20-30)
├── large/          # Large-scale instances (T=50-60)
├── legacy/         # Previous experiment data (pre-organization)
└── experiment_metadata.json  # Metadata for systematic experiments
```

## Running Experiments

Use the systematic experiment runner:

```bash
# Run all scales
python systematic_experiments.py

# Run specific scales
python systematic_experiments.py --scales small medium

# Dry run to see what would be executed
python systematic_experiments.py --dry-run
```

## Result Files

Each experiment directory contains:
- `all_results.json`: All experimental runs with full data
- `best_results.json`: Best solution found for each algorithm
- `summary_statistics.json`: Statistical summary (mean, std, min, max)
- `best_*_solution.json`: Best solution files for each algorithm

## Algorithms Tested

- **Greedy**: Fast constructive heuristic
- **Stochastic Greedy**: Randomized greedy with multiple starts
- **Genetic (Greedy Init)**: Tree-based GA with greedy initialization
- **Genetic (Stochastic Init)**: Tree-based GA with stochastic initialization
- **CPLEX**: MIP solver (small instances only)

## Genetic Algorithm Statistics

For genetic algorithm runs, additional statistics are tracked:
- `total_crossovers`: Number of crossover operations
- `crossovers_needing_completion`: Crossovers requiring greedy completion
- `total_tiles_completed`: Tiles placed by greedy completion
- `completion_rate`: Percentage of crossovers needing completion

This helps analyze how often the structure-preserving crossover can maintain
complete solutions vs. requiring greedy repair.
"""
    
    with open(Path('experiments/README.md'), 'w') as f:
        f.write(main_readme)
    
    print(f"✓ Created README at experiments/README.md")
    print(f"\n{'='*80}")
    print("Data organization complete!")
    print(f"{'='*80}")

if __name__ == '__main__':
    organize_existing_data()
