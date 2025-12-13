#!/usr/bin/env python3
"""
Plot different statistics from CSV results.
Supports various plot types including bar charts, box plots, violin plots, 
scatter plots, and line plots for comparing algorithm performance.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path
import argparse
from scipy import stats

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 10


def load_csv(csv_path):
    """Load CSV file and return DataFrame."""
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from {csv_path}")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Algorithms: {df['algorithm'].unique().tolist()}")
    return df


def plot_objective_comparison(df, output_dir=None):
    """Bar plot comparing mean objective values with error bars, grouped by tiles."""
    if 'tiles' not in df.columns:
        print("No 'tiles' column found, skipping grouped plot")
        return
    
    tiles_list = sorted(df['tiles'].unique())
    n_tiles = len(tiles_list)
    
    fig, axes = plt.subplots(1, n_tiles, figsize=(6*n_tiles, 6), squeeze=False)
    axes = axes.flatten()
    
    for idx, tiles in enumerate(tiles_list):
        ax = axes[idx]
        tile_df = df[df['tiles'] == tiles]
        
        # Calculate mean and std for each algorithm
        stats_df = tile_df.groupby('algorithm')['objective'].agg(['mean', 'std', 'count']).reset_index()
        stats_df['stderr'] = stats_df['std'] / np.sqrt(stats_df['count'])
        
        # Create bar plot
        bars = ax.bar(stats_df['algorithm'], stats_df['mean'], 
                       yerr=stats_df['stderr'], capsize=5, alpha=0.7)
        
        # Color bars
        colors = plt.cm.Set3(np.linspace(0, 1, len(stats_df)))
        for bar, color in zip(bars, colors):
            bar.set_color(color)
        
        # Start y-axis from slightly below minimum to show differences better
        y_min = stats_df['mean'].min() - stats_df['stderr'].max()
        y_max = stats_df['mean'].max() + stats_df['stderr'].max()
        margin = (y_max - y_min) * 0.1
        ax.set_ylim(y_min - margin, y_max + margin)
        
        ax.set_xlabel('Algorithm', fontsize=11, fontweight='bold')
        ax.set_ylabel('Mean Objective Value', fontsize=11, fontweight='bold')
        ax.set_title(f'Tiles={tiles}: Objective Comparison', 
                     fontsize=12, fontweight='bold')
        ax.tick_params(axis='x', rotation=45, labelsize=9)
        ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / 'objective_comparison_by_tiles.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/objective_comparison_by_tiles.png")
    plt.show()


def plot_boxplot(df, metric='objective', output_dir=None):
    """Box plot showing distribution of values for each algorithm, grouped by tiles."""
    if 'tiles' not in df.columns:
        print("No 'tiles' column found, skipping grouped plot")
        return
    
    tiles_list = sorted(df['tiles'].unique())
    n_tiles = len(tiles_list)
    
    fig, axes = plt.subplots(1, n_tiles, figsize=(6*n_tiles, 6), squeeze=False)
    axes = axes.flatten()
    
    for idx, tiles in enumerate(tiles_list):
        ax = axes[idx]
        tile_df = df[df['tiles'] == tiles]
        
        algorithms = sorted(tile_df['algorithm'].unique())
        data = [tile_df[tile_df['algorithm'] == algo][metric].values for algo in algorithms]
        
        bp = ax.boxplot(data, tick_labels=algorithms, patch_artist=True, 
                        notch=True, showmeans=True)
        
        # Color the boxes
        colors = plt.cm.Set3(np.linspace(0, 1, len(algorithms)))
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        # Adjust y-axis to show differences better for objective
        if metric == 'objective':
            all_data = np.concatenate(data)
            y_min, y_max = all_data.min(), all_data.max()
            margin = (y_max - y_min) * 0.1
            ax.set_ylim(y_min - margin, y_max + margin)
        
        ax.set_xlabel('Algorithm', fontsize=11, fontweight='bold')
        ax.set_ylabel(metric.replace('_', ' ').title(), fontsize=11, fontweight='bold')
        ax.set_title(f'Tiles={tiles}: {metric.replace("_", " ").title()} Distribution', 
                     fontsize=12, fontweight='bold')
        ax.tick_params(axis='x', rotation=45, labelsize=9)
        ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / f'boxplot_{metric}_by_tiles.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/boxplot_{metric}_by_tiles.png")
    plt.show()


def plot_violin(df, metric='objective', output_dir=None):
    """Violin plot showing distribution density for each algorithm, grouped by tiles."""
    if 'tiles' not in df.columns:
        print("No 'tiles' column found, skipping grouped plot")
        return
    
    tiles_list = sorted(df['tiles'].unique())
    n_tiles = len(tiles_list)
    
    fig, axes = plt.subplots(1, n_tiles, figsize=(6*n_tiles, 6), squeeze=False)
    axes = axes.flatten()
    
    for idx, tiles in enumerate(tiles_list):
        ax = axes[idx]
        tile_df = df[df['tiles'] == tiles]
        
        sns.violinplot(data=tile_df, x='algorithm', y=metric, ax=ax, 
                      hue='algorithm', palette='Set3', legend=False)
        
        # Adjust y-axis to show differences better for objective
        if metric == 'objective':
            y_min, y_max = tile_df[metric].min(), tile_df[metric].max()
            margin = (y_max - y_min) * 0.1
            ax.set_ylim(y_min - margin, y_max + margin)
        
        ax.set_xlabel('Algorithm', fontsize=11, fontweight='bold')
        ax.set_ylabel(metric.replace('_', ' ').title(), fontsize=11, fontweight='bold')
        ax.set_title(f'Tiles={tiles}: {metric.replace("_", " ").title()} Density', 
                     fontsize=12, fontweight='bold')
        ax.tick_params(axis='x', rotation=45, labelsize=9)
        ax.grid(axis='y', alpha=0.3)
    
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / f'violin_{metric}_by_tiles.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/violin_{metric}_by_tiles.png")
    plt.show()


def plot_scatter_objective_vs_runtime(df, output_dir=None):
    """Scatter plot of objective vs runtime colored by algorithm."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    algorithms = sorted(df['algorithm'].unique())
    colors = plt.cm.Set3(np.linspace(0, 1, len(algorithms)))
    
    for algo, color in zip(algorithms, colors):
        algo_df = df[df['algorithm'] == algo]
        ax.scatter(algo_df['runtime'], algo_df['objective'], 
                  label=algo, alpha=0.6, s=50, color=color)
    
    ax.set_xlabel('Runtime (seconds)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Objective Value', fontsize=12, fontweight='bold')
    ax.set_title('Objective Value vs Runtime by Algorithm', 
                 fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / 'scatter_objective_runtime.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/scatter_objective_runtime.png")
    plt.show()


def plot_runtime_comparison(df, output_dir=None):
    """Bar plot comparing mean runtime with error bars."""
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Calculate mean and std for each algorithm
    stats_df = df.groupby('algorithm')['runtime'].agg(['mean', 'std', 'count']).reset_index()
    stats_df['stderr'] = stats_df['std'] / np.sqrt(stats_df['count'])
    
    # Create bar plot
    bars = ax.bar(stats_df['algorithm'], stats_df['mean'], 
                   yerr=stats_df['stderr'], capsize=5, alpha=0.7)
    
    # Color bars
    colors = plt.cm.Set3(np.linspace(0, 1, len(stats_df)))
    for bar, color in zip(bars, colors):
        bar.set_color(color)
    
    ax.set_xlabel('Algorithm', fontsize=12, fontweight='bold')
    ax.set_ylabel('Mean Runtime (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('Algorithm Performance: Mean Runtime with Standard Error', 
                 fontsize=14, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / 'runtime_comparison.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/runtime_comparison.png")
    plt.show()


def plot_heatmap_correlation(df, output_dir=None):
    """Heatmap showing correlation between numeric variables."""
    # Select numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # Remove irrelevant columns
    exclude_cols = ['run', 'seed']
    numeric_cols = [col for col in numeric_cols if col not in exclude_cols]
    
    if len(numeric_cols) < 2:
        print("Not enough numeric columns for correlation heatmap")
        return
    
    fig, ax = plt.subplots(figsize=(10, 8))
    
    corr_matrix = df[numeric_cols].corr()
    
    sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm', 
                center=0, ax=ax, square=True, linewidths=1)
    
    ax.set_title('Correlation Heatmap of Numeric Variables', 
                 fontsize=14, fontweight='bold')
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / 'heatmap_correlation.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/heatmap_correlation.png")
    plt.show()


def plot_by_tiles(df, metric='objective', output_dir=None):
    """Line plot showing how metric changes with different tile configurations."""
    if 'tiles' not in df.columns:
        print("No 'tiles' column found in data")
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    algorithms = sorted(df['algorithm'].unique())
    colors = plt.cm.Set3(np.linspace(0, 1, len(algorithms)))
    
    for algo, color in zip(algorithms, colors):
        algo_df = df[df['algorithm'] == algo]
        grouped = algo_df.groupby('tiles')[metric].agg(['mean', 'std', 'count']).reset_index()
        grouped['stderr'] = grouped['std'] / np.sqrt(grouped['count'])
        
        ax.plot(grouped['tiles'], grouped['mean'], marker='o', 
                label=algo, color=color, linewidth=2)
        ax.fill_between(grouped['tiles'], 
                        grouped['mean'] - grouped['stderr'],
                        grouped['mean'] + grouped['stderr'],
                        alpha=0.2, color=color)
    
    ax.set_xlabel('Number of Tiles', fontsize=12, fontweight='bold')
    ax.set_ylabel(f'Mean {metric.replace("_", " ").title()}', fontsize=12, fontweight='bold')
    ax.set_title(f'{metric.replace("_", " ").title()} vs Number of Tiles', 
                 fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / f'tiles_{metric}.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/tiles_{metric}.png")
    plt.show()


def plot_histogram(df, metric='objective', output_dir=None):
    """Histogram showing distribution of values for each algorithm, grouped by tiles."""
    if 'tiles' not in df.columns:
        print("No 'tiles' column found, skipping grouped plot")
        return
    
    tiles_list = sorted(df['tiles'].unique())
    algorithms = sorted(df['algorithm'].unique())
    
    fig, axes = plt.subplots(len(algorithms), len(tiles_list), 
                            figsize=(6*len(tiles_list), 4*len(algorithms)))
    if len(algorithms) == 1:
        axes = axes.reshape(1, -1)
    if len(tiles_list) == 1:
        axes = axes.reshape(-1, 1)
    
    colors = plt.cm.Set3(np.linspace(0, 1, len(algorithms)))
    
    for row_idx, (algo, color) in enumerate(zip(algorithms, colors)):
        for col_idx, tiles in enumerate(tiles_list):
            ax = axes[row_idx, col_idx]
            tile_df = df[(df['algorithm'] == algo) & (df['tiles'] == tiles)]
            
            if len(tile_df) > 0:
                data = tile_df[metric].values
                
                ax.hist(data, bins=15, alpha=0.7, color=color, edgecolor='black')
                ax.axvline(np.mean(data), color='red', linestyle='--', 
                           linewidth=2, label=f'Mean: {np.mean(data):.2f}')
                ax.axvline(np.median(data), color='blue', linestyle='--', 
                           linewidth=2, label=f'Median: {np.median(data):.2f}')
                
                ax.set_xlabel(metric.replace('_', ' ').title(), fontsize=10, fontweight='bold')
                ax.set_ylabel('Frequency', fontsize=10, fontweight='bold')
                ax.set_title(f'{algo} | Tiles={tiles}', fontsize=11, fontweight='bold')
                ax.legend(fontsize=8)
                ax.grid(True, alpha=0.3)
            else:
                ax.text(0.5, 0.5, 'No Data', ha='center', va='center', 
                       transform=ax.transAxes)
                ax.set_title(f'{algo} | Tiles={tiles}', fontsize=11, fontweight='bold')
    
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / f'histogram_{metric}_by_tiles.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/histogram_{metric}_by_tiles.png")
    plt.show()


def plot_pareto_front(df, output_dir=None):
    """Scatter plot showing objective vs runtime (Pareto front)."""
    fig, ax = plt.subplots(figsize=(12, 8))
    
    algorithms = sorted(df['algorithm'].unique())
    colors = plt.cm.Set3(np.linspace(0, 1, len(algorithms)))
    
    for algo, color in zip(algorithms, colors):
        algo_df = df[df['algorithm'] == algo]
        # Calculate mean objective and runtime for each algorithm
        mean_obj = algo_df['objective'].mean()
        mean_runtime = algo_df['runtime'].mean()
        
        # Scatter all points
        ax.scatter(algo_df['runtime'], algo_df['objective'], 
                  alpha=0.3, s=30, color=color)
        # Highlight mean
        ax.scatter(mean_runtime, mean_obj, 
                  s=200, color=color, marker='*', 
                  edgecolors='black', linewidths=2, 
                  label=f'{algo} (mean)', zorder=5)
    
    ax.set_xlabel('Runtime (seconds)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Objective Value', fontsize=12, fontweight='bold')
    ax.set_title('Pareto Front: Objective vs Runtime\n(Stars = algorithm means)', 
                 fontsize=14, fontweight='bold')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / 'pareto_front.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/pareto_front.png")
    plt.show()


def plot_percentage_improvement(df, output_dir=None):
    """Bar plot showing percentage improvement relative to baseline, grouped by tiles."""
    if 'tiles' not in df.columns:
        print("No 'tiles' column found, skipping grouped plot")
        return
    
    tiles_list = sorted(df['tiles'].unique())
    n_tiles = len(tiles_list)
    
    fig, axes = plt.subplots(1, n_tiles, figsize=(6*n_tiles, 6), squeeze=False)
    axes = axes.flatten()
    
    for idx, tiles in enumerate(tiles_list):
        ax = axes[idx]
        tile_df = df[df['tiles'] == tiles]
        
        # Calculate mean for each algorithm
        algo_means = tile_df.groupby('algorithm')['objective'].mean().sort_values()
        
        # Use the worst (highest for minimization) as baseline
        baseline = algo_means.max()
        
        # Calculate percentage improvement
        improvements = ((baseline - algo_means) / baseline * 100).sort_values(ascending=False)
        
        # Create bar plot
        bars = ax.bar(range(len(improvements)), improvements.values, alpha=0.7)
        
        # Color bars
        colors = plt.cm.RdYlGn(np.linspace(0.3, 0.9, len(improvements)))
        for bar, color in zip(bars, colors):
            bar.set_color(color)
        
        # Add value labels on bars
        for i, (algo, val) in enumerate(improvements.items()):
            ax.text(i, val + 0.5, f'{val:.1f}%', ha='center', va='bottom', 
                   fontsize=9, fontweight='bold')
        
        ax.set_xticks(range(len(improvements)))
        ax.set_xticklabels(improvements.index, rotation=45, ha='right', fontsize=9)
        ax.set_ylabel('Improvement over Worst (%)', fontsize=11, fontweight='bold')
        ax.set_title(f'Tiles={tiles}: Objective Improvement', 
                     fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    
    plt.tight_layout()
    
    if output_dir:
        plt.savefig(Path(output_dir) / 'percentage_improvement_by_tiles.png', dpi=300, bbox_inches='tight')
        print(f"Saved: {output_dir}/percentage_improvement_by_tiles.png")
    plt.show()


def plot_all(df, output_dir=None):
    """Generate all plots."""
    print("\n" + "="*80)
    print("GENERATING ALL PLOTS")
    print("="*80 + "\n")
    
    print("1. Objective Comparison...")
    plot_objective_comparison(df, output_dir)
    
    print("\n2. Runtime Comparison...")
    plot_runtime_comparison(df, output_dir)
    
    print("\n3. Box Plot (Objective)...")
    plot_boxplot(df, 'objective', output_dir)
    
    print("\n4. Box Plot (Runtime)...")
    plot_boxplot(df, 'runtime', output_dir)
    
    print("\n5. Violin Plot (Objective)...")
    plot_violin(df, 'objective', output_dir)
    
    print("\n6. Scatter: Objective vs Runtime...")
    plot_scatter_objective_vs_runtime(df, output_dir)
    
    print("\n7. Histogram (Objective)...")
    plot_histogram(df, 'objective', output_dir)
    
    print("\n8. Histogram (Runtime)...")
    plot_histogram(df, 'runtime', output_dir)
    
    print("\n9. Correlation Heatmap...")
    plot_heatmap_correlation(df, output_dir)
    
    print("\n10. Pareto Front...")
    plot_pareto_front(df, output_dir)
    
    print("\n11. Percentage Improvement...")
    plot_percentage_improvement(df, output_dir)
    
    if 'tiles' in df.columns and df['tiles'].nunique() > 1:
        print("\n12. Objective vs Tiles...")
        plot_by_tiles(df, 'objective', output_dir)
        
        print("\n13. Runtime vs Tiles...")
        plot_by_tiles(df, 'runtime', output_dir)
    
    print("\n" + "="*80)
    print("ALL PLOTS GENERATED SUCCESSFULLY!")
    print("="*80)


def main():
    parser = argparse.ArgumentParser(
        description='Plot statistics from CSV results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all plots
  python plot_csv_statistics.py data.csv --all
  
  # Generate specific plots
  python plot_csv_statistics.py data.csv --objective --runtime --boxplot
  
  # Save plots to directory
  python plot_csv_statistics.py data.csv --all --output-dir plots/
  
  # Plot specific metric in boxplot
  python plot_csv_statistics.py data.csv --boxplot --metric objective
        """
    )
    
    parser.add_argument('csv_file', type=str, help='Path to CSV file')
    parser.add_argument('--all', action='store_true', 
                       help='Generate all available plots')
    parser.add_argument('--objective', action='store_true', 
                       help='Plot objective comparison')
    parser.add_argument('--runtime', action='store_true', 
                       help='Plot runtime comparison')
    parser.add_argument('--boxplot', action='store_true', 
                       help='Generate box plot')
    parser.add_argument('--violin', action='store_true', 
                       help='Generate violin plot')
    parser.add_argument('--scatter', action='store_true', 
                       help='Generate scatter plot (objective vs runtime)')
    parser.add_argument('--histogram', action='store_true', 
                       help='Generate histogram')
    parser.add_argument('--heatmap', action='store_true', 
                       help='Generate correlation heatmap')
    parser.add_argument('--tiles', action='store_true', 
                       help='Plot metrics vs number of tiles')
    parser.add_argument('--pareto', action='store_true', 
                       help='Plot Pareto front')
    parser.add_argument('--metric', type=str, default='objective',
                       help='Metric to plot (default: objective)')
    parser.add_argument('--output-dir', type=str, 
                       help='Directory to save plots')
    
    args = parser.parse_args()
    
    # Validate CSV file exists
    csv_path = Path(args.csv_file)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)
    
    # Create output directory if specified
    if args.output_dir:
        output_path = Path(args.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {output_path}")
    
    # Load data
    df = load_csv(csv_path)
    
    # If no specific plot is requested, default to --all
    no_plots_specified = not any([
        args.all, args.objective, args.runtime, args.boxplot,
        args.violin, args.scatter, args.histogram, args.heatmap,
        args.tiles, args.pareto
    ])
    
    if args.all or no_plots_specified:
        plot_all(df, args.output_dir)
    else:
        if args.objective:
            plot_objective_comparison(df, args.output_dir)
        if args.runtime:
            plot_runtime_comparison(df, args.output_dir)
        if args.boxplot:
            plot_boxplot(df, args.metric, args.output_dir)
        if args.violin:
            plot_violin(df, args.metric, args.output_dir)
        if args.scatter:
            plot_scatter_objective_vs_runtime(df, args.output_dir)
        if args.histogram:
            plot_histogram(df, args.metric, args.output_dir)
        if args.heatmap:
            plot_heatmap_correlation(df, args.output_dir)
        if args.tiles:
            plot_by_tiles(df, args.metric, args.output_dir)
        if args.pareto:
            plot_pareto_front(df, args.output_dir)


if __name__ == '__main__':
    main()
