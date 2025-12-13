# CSV Statistics Plotter

A comprehensive Python program to plot different statistics from CSV files containing experimental results.

## Features

The program supports **12 different plot types**:

1. **Objective Comparison** - Bar plot comparing mean objective values with error bars
2. **Runtime Comparison** - Bar plot comparing mean runtime with error bars
3. **Box Plot (Objective)** - Distribution of objective values by algorithm
4. **Box Plot (Runtime)** - Distribution of runtime by algorithm
5. **Violin Plot** - Distribution density visualization
6. **Scatter Plot** - Objective vs Runtime colored by algorithm
7. **Histogram (Objective)** - Distribution histograms for each algorithm
8. **Histogram (Runtime)** - Runtime distribution histograms
9. **Correlation Heatmap** - Correlation matrix of numeric variables
10. **Pareto Front** - Objective vs Runtime showing trade-offs
11. **Objective vs Tiles** - Line plot showing how objective changes with tile count
12. **Runtime vs Tiles** - Line plot showing how runtime scales with tile count

## Installation

The script requires the following Python packages:
- pandas
- matplotlib
- seaborn
- numpy
- scipy

If using `uv`, these dependencies should already be available in your project.

## Usage

### Basic Usage

```bash
# Generate all plots (default behavior)
uv run python plot_csv_statistics.py data.csv

# Generate all plots explicitly
uv run python plot_csv_statistics.py data.csv --all

# Save plots to a directory
uv run python plot_csv_statistics.py data.csv --all --output-dir plots/
```

### Generate Specific Plots

```bash
# Objective comparison only
uv run python plot_csv_statistics.py data.csv --objective

# Runtime comparison
uv run python plot_csv_statistics.py data.csv --runtime

# Box plot
uv run python plot_csv_statistics.py data.csv --boxplot

# Violin plot
uv run python plot_csv_statistics.py data.csv --violin

# Scatter plot
uv run python plot_csv_statistics.py data.csv --scatter

# Histogram
uv run python plot_csv_statistics.py data.csv --histogram

# Correlation heatmap
uv run python plot_csv_statistics.py data.csv --heatmap

# Tiles analysis
uv run python plot_csv_statistics.py data.csv --tiles

# Pareto front
uv run python plot_csv_statistics.py data.csv --pareto
```

### Combine Multiple Plots

```bash
# Generate objective, runtime, and box plots
uv run python plot_csv_statistics.py data.csv --objective --runtime --boxplot

# Generate statistical plots with output directory
uv run python plot_csv_statistics.py data.csv --boxplot --violin --histogram --output-dir results/
```

### Custom Metrics

```bash
# Plot runtime in box plot format
uv run python plot_csv_statistics.py data.csv --boxplot --metric runtime

# Plot bbox_width in violin plot
uv run python plot_csv_statistics.py data.csv --violin --metric bbox_width

# Analyze tiles with runtime metric
uv run python plot_csv_statistics.py data.csv --tiles --metric runtime
```

## Example with Your Data

```bash
# Analyze small experiment results
uv run python plot_csv_statistics.py experiment_area/small/all_results.csv --all --output-dir experiment_area/small/plots

# Analyze medium experiment results
uv run python plot_csv_statistics.py experiment_area/medium/all_results.csv --all --output-dir experiment_area/medium/plots

# Quick objective and runtime comparison
uv run python plot_csv_statistics.py experiment_area/large/all_results.csv --objective --runtime --scatter
```

## Command-Line Options

| Option | Description |
|--------|-------------|
| `csv_file` | Path to the CSV file (required) |
| `--all` | Generate all available plots |
| `--objective` | Plot objective value comparison |
| `--runtime` | Plot runtime comparison |
| `--boxplot` | Generate box plot |
| `--violin` | Generate violin plot |
| `--scatter` | Generate scatter plot (objective vs runtime) |
| `--histogram` | Generate histogram |
| `--heatmap` | Generate correlation heatmap |
| `--tiles` | Plot metrics vs number of tiles |
| `--pareto` | Plot Pareto front |
| `--metric METRIC` | Specify metric to plot (default: objective) |
| `--output-dir DIR` | Directory to save plots |

## CSV Data Format

The script expects CSV files with at least these columns:
- `algorithm` - Name of the algorithm
- `objective` - Objective value (e.g., area, perimeter)
- `runtime` - Execution time in seconds

Optional columns that enable additional features:
- `tiles` - Number of tiles (enables tile analysis plots)
- Other numeric columns for correlation analysis

Example:
```csv
scale,tiles,n,m,run,seed,algorithm,objective_type,status,objective,runtime
small,6,3,3,1,42,greedy,area,success,44,0.003833
small,6,3,3,1,42,genetic_greedy,area,success,44,0.108045
```

## Output

- **Interactive Mode**: If no `--output-dir` is specified, plots are displayed interactively
- **Save Mode**: If `--output-dir` is provided, plots are saved as high-resolution PNG files (300 DPI)
- **File Naming**: Plots are automatically named based on their type (e.g., `objective_comparison.png`, `boxplot_runtime.png`)

## Plot Descriptions

### 1. Objective/Runtime Comparison
Bar charts showing mean values with standard error bars for each algorithm. Useful for quick comparison of algorithm performance.

### 2. Box Plots
Shows distribution quartiles, outliers, and median values. The notch indicates confidence interval around the median.

### 3. Violin Plots
Combines box plot with density estimation, showing the full distribution shape of the data.

### 4. Scatter Plots
Shows individual data points, revealing patterns and correlations between variables.

### 5. Histograms
Shows frequency distribution of values for each algorithm separately, including mean and median lines.

### 6. Correlation Heatmap
Displays pairwise correlations between all numeric variables, helping identify relationships.

### 7. Pareto Front
Shows trade-offs between objective value and runtime, with algorithm means highlighted as stars.

### 8. Tiles Analysis
Line plots showing how metrics change with different tile configurations, useful for scalability analysis.

## Tips

1. **Start with `--all`** to get a comprehensive overview of your data
2. **Use `--output-dir`** to save plots for reports and presentations
3. **Combine flags** to generate only the plots you need
4. **Use `--metric`** to analyze different aspects of your data
5. **Check correlations** with `--heatmap` to understand variable relationships

## Notes

- The script automatically handles missing data and calculates appropriate statistics
- Error bars represent standard error of the mean
- All plots use consistent color schemes for better comparison
- High-resolution outputs (300 DPI) are suitable for publications
