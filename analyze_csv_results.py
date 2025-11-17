#!/usr/bin/env python3
"""
Comprehensive statistical analysis of CSV results from systematic experiments.
Calculates mean, standard deviation, standard error, confidence intervals, etc.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys
from scipy import stats

def calculate_statistics(series):
    """Calculate comprehensive statistics for a series."""
    n = len(series)
    mean = series.mean()
    std = series.std(ddof=1)  # Sample standard deviation
    stderr = std / np.sqrt(n)  # Standard error of the mean
    
    # 95% confidence interval
    confidence = 0.95
    df = n - 1
    t_critical = stats.t.ppf((1 + confidence) / 2, df)
    margin_error = t_critical * stderr
    ci_lower = mean - margin_error
    ci_upper = mean + margin_error
    
    return {
        'count': n,
        'mean': mean,
        'std': std,
        'stderr': stderr,
        'min': series.min(),
        'max': series.max(),
        'median': series.median(),
        'q25': series.quantile(0.25),
        'q75': series.quantile(0.75),
        'ci_lower': ci_lower,
        'ci_upper': ci_upper
    }

def analyze_results(csv_path):
    """Analyze results from a CSV file with comprehensive statistics."""
    df = pd.read_csv(csv_path)
    
    print(f"\n{'='*80}")
    print(f"STATISTICAL ANALYSIS: {csv_path}")
    print(f"{'='*80}\n")
    
    print(f"Total experiments: {len(df)}")
    print(f"Algorithms: {df['algorithm'].unique().tolist()}")
    print(f"Tiles configurations: {df['tiles'].unique().tolist()}")
    print(f"Number of runs per algorithm: {df.groupby('algorithm').size().to_dict()}")
    
    # Create summary statistics table
    print(f"\n{'='*80}")
    print("OBJECTIVE STATISTICS BY ALGORITHM")
    print(f"{'='*80}\n")
    
    summary_data = []
    
    for algo in sorted(df['algorithm'].unique()):
        algo_df = df[df['algorithm'] == algo]
        obj_stats = calculate_statistics(algo_df['objective'])
        runtime_stats = calculate_statistics(algo_df['runtime'])
        
        summary_data.append({
            'Algorithm': algo,
            'N': obj_stats['count'],
            'Obj_Mean': obj_stats['mean'],
            'Obj_StdDev': obj_stats['std'],
            'Obj_StdErr': obj_stats['stderr'],
            'Obj_CI95_Lower': obj_stats['ci_lower'],
            'Obj_CI95_Upper': obj_stats['ci_upper'],
            'Obj_Min': obj_stats['min'],
            'Obj_Median': obj_stats['median'],
            'Obj_Max': obj_stats['max'],
            'Runtime_Mean': runtime_stats['mean'],
            'Runtime_StdDev': runtime_stats['std'],
            'Runtime_StdErr': runtime_stats['stderr']
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    # Print formatted table
    print("Algorithm Performance Summary:")
    print("-" * 80)
    for _, row in summary_df.iterrows():
        print(f"\n{row['Algorithm']}:")
        print(f"  Sample size: {int(row['N'])}")
        print(f"  Objective:")
        print(f"    Mean ± StdDev: {row['Obj_Mean']:.3f} ± {row['Obj_StdDev']:.3f}")
        print(f"    Std Error: {row['Obj_StdErr']:.3f}")
        print(f"    95% CI: [{row['Obj_CI95_Lower']:.3f}, {row['Obj_CI95_Upper']:.3f}]")
        print(f"    Range: [{row['Obj_Min']:.1f}, {row['Obj_Max']:.1f}]")
        print(f"    Median: {row['Obj_Median']:.3f}")
        print(f"  Runtime:")
        print(f"    Mean ± StdDev: {row['Runtime_Mean']:.4f} ± {row['Runtime_StdDev']:.4f} seconds")
        print(f"    Std Error: {row['Runtime_StdErr']:.4f} seconds")
    
    # Crossover statistics for genetic algorithms
    print(f"\n{'='*80}")
    print("GENETIC ALGORITHM CROSSOVER STATISTICS")
    print(f"{'='*80}\n")
    
    genetic_algos = [algo for algo in df['algorithm'].unique() if 'genetic' in algo.lower()]
    
    if genetic_algos and 'total_crossovers' in df.columns:
        for algo in sorted(genetic_algos):
            algo_df = df[df['algorithm'] == algo]
            
            if algo_df['total_crossovers'].notna().any():
                crossover_df = algo_df[algo_df['total_crossovers'].notna()]
                
                if len(crossover_df) > 0:
                    print(f"{algo}:")
                    
                    # Total crossovers
                    xo_stats = calculate_statistics(crossover_df['total_crossovers'])
                    print(f"  Total Crossovers:")
                    print(f"    Mean ± StdDev: {xo_stats['mean']:.1f} ± {xo_stats['std']:.1f}")
                    print(f"    Range: [{xo_stats['min']:.0f}, {xo_stats['max']:.0f}]")
                    
                    # Completion rate
                    if 'completion_rate' in crossover_df.columns:
                        comp_stats = calculate_statistics(crossover_df['completion_rate'] * 100)
                        print(f"  Completion Rate (% needing greedy):")
                        print(f"    Mean ± StdDev: {comp_stats['mean']:.2f}% ± {comp_stats['std']:.2f}%")
                        print(f"    95% CI: [{comp_stats['ci_lower']:.2f}%, {comp_stats['ci_upper']:.2f}%]")
                        print(f"    Range: [{comp_stats['min']:.2f}%, {comp_stats['max']:.2f}%]")
                    
                    # Tiles per incomplete crossover
                    if 'avg_tiles_per_incomplete' in crossover_df.columns:
                        tiles_stats = calculate_statistics(crossover_df['avg_tiles_per_incomplete'])
                        print(f"  Avg Tiles Completed per Incomplete Crossover:")
                        print(f"    Mean ± StdDev: {tiles_stats['mean']:.3f} ± {tiles_stats['std']:.3f}")
                        print(f"    95% CI: [{tiles_stats['ci_lower']:.3f}, {tiles_stats['ci_upper']:.3f}]")
                    
                    print()
    
    # Statistical comparisons (pairwise t-tests)
    if len(df['algorithm'].unique()) > 1:
        print(f"\n{'='*80}")
        print("PAIRWISE STATISTICAL COMPARISONS (Two-Sample t-tests)")
        print(f"{'='*80}\n")
        
        algos = sorted(df['algorithm'].unique())
        print("Objective comparison (lower is better):")
        print("-" * 80)
        
        for i, algo1 in enumerate(algos):
            for algo2 in algos[i+1:]:
                obj1 = df[df['algorithm'] == algo1]['objective']
                obj2 = df[df['algorithm'] == algo2]['objective']
                
                t_stat, p_value = stats.ttest_ind(obj1, obj2)
                
                mean_diff = obj1.mean() - obj2.mean()
                
                significance = ""
                if p_value < 0.001:
                    significance = "***"
                elif p_value < 0.01:
                    significance = "**"
                elif p_value < 0.05:
                    significance = "*"
                else:
                    significance = "ns"
                
                print(f"{algo1} vs {algo2}:")
                print(f"  Mean difference: {mean_diff:.3f} (t={t_stat:.3f}, p={p_value:.4f}) {significance}")
                if significance != "ns":
                    winner = algo1 if mean_diff < 0 else algo2
                    print(f"  → {winner} is significantly better")
                print()
        
        print("\nSignificance levels: *** p<0.001, ** p<0.01, * p<0.05, ns = not significant")
    
    # Save summary statistics to CSV
    output_path = Path(csv_path).parent / "statistics_summary.csv"
    summary_df.to_csv(output_path, index=False)
    print(f"\n{'='*80}")
    print(f"Summary statistics saved to: {output_path}")
    print(f"{'='*80}\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 analyze_csv_results.py <path_to_csv>")
        print("\nExample:")
        print("  python3 analyze_csv_results.py experiments/csv_test_systematic/small_test/all_results.csv")
        return
    
    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"Error: File not found: {csv_path}")
        return
    
    analyze_results(csv_path)

if __name__ == '__main__':
    main()
