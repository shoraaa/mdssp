# Test Case Generator - Usage Guide

The `generate_test_cases.py` script helps you explore and generate test cases from the systematic experiments configuration.

## Quick Examples

### 1. View all test cases for a specific scale
```bash
python3 generate_test_cases.py --scale medium --seed-only
```

### 2. Find a specific test case by seed
```bash
python3 generate_test_cases.py --scale medium --seed-only --filter-seed 542
```

### 3. Find all T=20 test cases
```bash
python3 generate_test_cases.py --scale medium --seed-only --filter-tiles 20
```

### 4. Get JSON output for programmatic use
```bash
python3 generate_test_cases.py --scale medium --seed-only --filter-seed 542 --format json
```

### 5. Export to CSV
```bash
python3 generate_test_cases.py --all --seed-only --format csv > all_test_cases.csv
```

### 6. Generate metadata file for all scales
```bash
python3 generate_test_cases.py --all --output-dir test_cases_metadata
```

### 7. Generate actual dataset JSON files
```bash
python3 generate_test_cases.py --scale small --generate-datasets --output-dir datasets/
```

## Understanding the Output

Each test case includes:
- **scale**: small/medium/large
- **exp_name**: Experiment name (e.g., T20_n3_m3)
- **run**: Run number (1-30 for small/medium, 1-20 for large)
- **seed**: Random seed used (base_seed + run * 100)
- **tiles (T)**: Number of tiles
- **n×m**: Tile dimensions
- **algorithms**: List of algorithms to run
- **objective_type**: 'square' (minimize max(W,H)) or 'area' (minimize W×H)
- **cplex_time_limit**: CPLEX time limit in seconds

## Debugging Specific Cases

For the reported case (T=20, m=3, n=3, seed=542):

```bash
# 1. Find the test case details
python3 generate_test_cases.py --scale medium --seed-only --filter-seed 542 --filter-tiles 20 --format json

# 2. Generate dataset for this case
./mdssp -a greedy -T 20 -n 3 -m 3 -s 542 -o /tmp/test_dataset_542.json

# 3. Test CPLEX with this dataset
./mdssp -a cplex -T 20 -n 3 -m 3 -s 542 -o /tmp/test_cplex_542.json --time-limit 120

# 4. Compare all algorithms
./mdssp -a all -T 20 -n 3 -m 3 -s 542 -o /tmp/test_all_542.json
```

## Summary Statistics

Total test cases by configuration:
- **Small scale**: 3 tile counts × 30 runs = 90 cases
- **Medium scale**: 3 tile counts × 30 runs = 90 cases  
- **Large scale**: 3 tile counts × 20 runs = 60 cases
- **Total**: 240 test cases × 5 algorithms = 1,200 individual runs

Base seed: 42
Seed increment: 100 per run
