# MDSSP Solution Visualizer - Gradio Web Interface

A web-based interface for visualizing and comparing MDSSP algorithm solutions.

## Features

- **Browse Test Cases**: Select from different scales (small/medium/large) and experiment configurations
- **View Tile Sets**: Visualize the input tiles for each test case in ASCII art
- **Compare Solutions**: Side-by-side comparison of all algorithm results
- **Individual Solution Views**: Detailed view of each algorithm's solution including:
  - Solution status and metrics (objective, runtime, bounding box)
  - Visual canvas representation
  - Genetic algorithm statistics (when applicable)

## Installation

The required packages are:
- `gradio` - Web interface framework
- `pandas` - Data manipulation for comparison tables

Install using uv:
```bash
uv pip install gradio pandas
```

## Usage

### Start the Web Interface

```bash
cd /home/shora/Research/mdssp
uv run visualize_solutions.py
```

The application will start on `http://0.0.0.0:7860`

Access it in your browser at:
- Local: `http://localhost:7860`
- Network: `http://<your-ip>:7860`

### Using the Interface

1. **Select Scale**: Choose from small, medium, or large
2. **Choose Experiment**: Select tile count (e.g., T20_n3_m3)
3. **Pick Run**: Select run number (1-30 for small/medium, 1-20 for large)
4. **Load**: Click "Load Test Case" to visualize

The interface displays:
- Test case information (scale, seed, tile count)
- All tiles in the test set
- Comparison table showing best objective
- Individual tabs for each algorithm's solution

## Data Sources

The visualizer reads from:
- `experiment_square/` - Algorithm solutions from systematic experiments
- `test_datasets/` - Input tile sets for each test case

## Algorithms Compared

- **Greedy**: Fast deterministic placement
- **Stochastic Greedy**: Randomized greedy with exploration
- **Genetic + Greedy**: Hybrid evolutionary approach
- **Genetic + Stochastic**: Evolutionary with stochastic completion
- **CPLEX**: Optimal MIP solver (with time limits)

## Example Use Cases

### Debug a Specific Test Case
1. Navigate to the problematic case (e.g., T=20, seed=542 → Run 6)
2. View the tile set to understand the problem structure
3. Compare all algorithm solutions
4. Examine individual solution canvases

### Compare Algorithm Performance
1. Load different test cases
2. Review the comparison table to see which algorithms perform best
3. Check runtime vs. solution quality trade-offs

### Verify Solutions
1. Load a test case
2. Check if all algorithms found valid solutions
3. Compare objective values to identify discrepancies
4. Examine canvases for visual verification

## Troubleshooting

### Port Already in Use
If port 7860 is occupied, modify `visualize_solutions.py`:
```python
app.launch(
    server_name="0.0.0.0",
    server_port=7861,  # Change port
    share=False
)
```

### Missing Data
Ensure you have:
- Generated datasets: `python3 generate_test_cases.py --all --generate-datasets`
- Run experiments in `experiment_square/` directory

### Slow Loading
Large test cases (T=60-100) may take a few seconds to render. This is normal.

## Development

To modify the interface:
1. Edit `visualize_solutions.py`
2. Restart the server (Ctrl+C, then re-run)
3. Refresh your browser

The code is organized into:
- Data loading functions (`load_tile_dataset`, `load_solution`)
- Rendering functions (`render_all_tiles`, `format_canvas`)
- Gradio UI components and event handlers

## Notes

- Solutions are loaded from JSON files in `experiment_square/`
- Tile datasets are loaded from `test_datasets/`
- The visualizer uses ASCII art for tile and canvas rendering
- All comparisons highlight the best objective value
