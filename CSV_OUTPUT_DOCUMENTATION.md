# CSV Output Documentation

## Overview

The systematic experiments script generates CSV files alongside JSON outputs for easier data analysis and visualization. CSV files are generated at multiple levels:

1. **Individual experiment CSVs**: Per scale/configuration
2. **Scale-wide CSVs**: Aggregated per scale (small/medium/large)
3. **Combined CSVs**: All scales together

## File Structure

```
experiments/
├── combined_all_results.csv          # All results across all scales
├── small/
│   ├── all_results.csv              # All small scale results
│   ├── summary_statistics.csv       # Summary stats for small scale
│   └── T6_n3_m3/
│       └── all_results.csv          # Results for specific configuration
├── medium/
│   ├── all_results.csv
│   ├── summary_statistics.csv
│   └── ...
└── large/
    ├── all_results.csv
    ├── summary_statistics.csv
    └── ...
```

## CSV Formats

### all_results.csv (Detailed Results)

Contains one row per experiment run.

**Columns:**
- `scale`: Experiment scale (small/medium/large)
- `tiles`: Number of tiles (T)
- `n`: Tile height
- `m`: Tile width
- `run`: Run number (1 to N)
- `seed`: Random seed used
- `algorithm`: Algorithm name (greedy, genetic_greedy, genetic_stochastic, cplex)
- `objective`: Objective value (L∞ of bounding box)
- `runtime`: Execution time in seconds
- `bbox_width`: Width of bounding box
- `bbox_height`: Height of bounding box
- `num_tiles`: Number of tiles placed

**For genetic algorithms only:**
- `total_crossovers`: Total number of crossover operations performed
- `crossovers_needing_completion`: Number of crossovers that needed greedy completion
- `total_tiles_completed`: Total tiles placed by greedy completion
- `completion_rate`: Fraction of crossovers needing completion (0.0-1.0)
- `avg_tiles_per_incomplete`: Average tiles completed per incomplete crossover

**Example:**
```csv
scale,tiles,n,m,run,seed,algorithm,objective,runtime,bbox_width,bbox_height,num_tiles,total_crossovers,crossovers_needing_completion,total_tiles_completed,completion_rate,avg_tiles_per_incomplete
small,6,3,3,1,42,greedy,8,0.318,8,8,6,,,,,
small,6,3,3,1,42,genetic_greedy,7,0.242,7,7,6,31,6,13,0.194,2.17
```

### summary_statistics.csv (Aggregated Statistics)

Contains one row per algorithm-configuration combination with statistics across all runs.

**Columns:**
- `algorithm`: Algorithm name
- `tiles`: Number of tiles
- `n`: Tile height
- `m`: Tile width
- `num_runs`: Number of runs averaged
- `obj_mean`: Mean objective value
- `obj_min`: Minimum objective value
- `obj_max`: Maximum objective value
- `obj_std`: Standard deviation of objective
- `runtime_mean`: Mean runtime in seconds
- `runtime_min`: Minimum runtime
- `runtime_max`: Maximum runtime
- `runtime_std`: Standard deviation of runtime

**For genetic algorithms only:**
- `crossovers_mean`: Average number of crossovers
- `completion_rate_mean`: Average completion rate
- `tiles_completed_mean`: Average tiles completed by greedy

**Example:**
```csv
algorithm,tiles,n,m,num_runs,obj_mean,obj_min,obj_max,obj_std,runtime_mean,runtime_min,runtime_max,runtime_std,crossovers_mean,completion_rate_mean,tiles_completed_mean
greedy,6,3,3,30,8.2,7,10,0.8,0.305,0.250,0.380,0.035,,,
genetic_greedy,6,3,3,30,7.1,6,8,0.5,0.245,0.210,0.290,0.022,32.5,0.285,17.3
```

## Usage Examples

### Python (pandas)

```python
import pandas as pd

# Load results
df = pd.read_csv('experiments/combined_all_results.csv')

# Filter genetic algorithm results
genetic_df = df[df['algorithm'].str.contains('genetic')]

# Calculate average completion rate by scale
completion_by_scale = genetic_df.groupby('scale')['completion_rate'].mean()
print(completion_by_scale)

# Compare algorithms
summary = df.groupby('algorithm')['objective'].agg(['mean', 'std', 'min', 'max'])
print(summary)
```

### R

```r
# Load results
results <- read.csv('experiments/combined_all_results.csv')

# Summary by algorithm
library(dplyr)
summary <- results %>%
  group_by(algorithm) %>%
  summarise(
    mean_obj = mean(objective),
    sd_obj = sd(objective),
    mean_time = mean(runtime)
  )

# Plot completion rates
library(ggplot2)
genetic <- results[grepl('genetic', results$algorithm),]
ggplot(genetic, aes(x=algorithm, y=completion_rate)) +
  geom_boxplot() +
  labs(title='Crossover Completion Rates by Algorithm')
```

### Excel

1. Open CSV file in Excel
2. Data → Text to Columns → Delimited → Comma
3. Create pivot tables for analysis
4. Use conditional formatting for completion_rate column

## Data Analysis Tips

1. **Filter by scale**: Compare algorithm performance across problem sizes
2. **Track completion rates**: Monitor how often greedy completion is needed
3. **Identify trends**: Look for patterns in completion_rate vs. problem size
4. **Performance comparison**: Use obj_mean and runtime_mean from summary CSVs
5. **Statistical significance**: Use obj_std to assess result stability

## Crossover Completion Insights

The crossover statistics reveal how well the tree-based genetic algorithm maintains complete solutions:

- **Low completion_rate** (~0-20%): Most crossovers produce complete solutions
- **Medium completion_rate** (~20-50%): Greedy completion frequently needed
- **High completion_rate** (~50%+): Many crossovers produce incomplete solutions

The `avg_tiles_per_incomplete` metric shows the average difficulty of completing an incomplete crossover - higher values indicate more tiles need to be greedily placed.

## Notes

- Empty cells in genetic algorithm columns for non-genetic algorithms is expected
- All times are in seconds
- Objective values are L∞ metric (max of width and height)
- completion_rate is a fraction (0.0-1.0), multiply by 100 for percentage
