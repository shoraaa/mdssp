# MDSSP Experiments

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
