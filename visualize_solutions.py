#!/usr/bin/env python3
"""
Gradio Web Interface for MDSSP Solution Visualization

This application allows you to:
- Browse test cases from systematic experiments
- View tile sets for each test case
- Compare solutions from different algorithms
- Visualize solution canvases side-by-side
"""

import gradio as gr
import json
from pathlib import Path
import pandas as pd
from typing import Dict, List, Tuple, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Configuration
EXPERIMENTS_DIR = Path("experiment_square")
TEST_DATASETS_DIR = Path("test_datasets")
BASE_SEED = 42

# Algorithm names mapping
ALGORITHM_NAMES = {
    'greedy': 'Greedy',
    'stochastic_greedy': 'Stochastic Greedy',
    'genetic_greedy': 'Genetic + Greedy',
    'genetic_stochastic': 'Genetic + Stochastic',
    'cplex': 'CPLEX'
}


def get_available_scales() -> List[str]:
    """Get list of available experiment scales."""
    if not EXPERIMENTS_DIR.exists():
        return []
    return sorted([d.name for d in EXPERIMENTS_DIR.iterdir() if d.is_dir()])


def get_experiments_for_scale(scale: str) -> List[str]:
    """Get list of experiment configurations for a scale."""
    scale_dir = EXPERIMENTS_DIR / scale
    if not scale_dir.exists():
        return []
    
    experiments = []
    for exp_dir in sorted(scale_dir.iterdir()):
        if exp_dir.is_dir() and exp_dir.name.startswith('T'):
            experiments.append(exp_dir.name)
    return experiments


def get_runs_for_experiment(scale: str, experiment: str) -> List[int]:
    """Get list of available runs for an experiment."""
    exp_dir = EXPERIMENTS_DIR / scale / experiment
    if not exp_dir.exists():
        return []
    
    runs = set()
    for file in exp_dir.glob("run_*_*.json"):
        # Extract run number from filename like "run_1_greedy.json"
        parts = file.stem.split('_')
        if len(parts) >= 2:
            try:
                runs.add(int(parts[1]))
            except ValueError:
                pass
    
    return sorted(list(runs))


def seed_from_run(run: int) -> int:
    """Calculate seed from run number."""
    return BASE_SEED + (run - 1) * 100


def load_tile_dataset(scale: str, experiment: str, run: int) -> Optional[Dict]:
    """Load tile dataset for a test case."""
    seed = seed_from_run(run)
    dataset_file = TEST_DATASETS_DIR / scale / experiment / f"dataset_run{run}_seed{seed}.json"
    
    if not dataset_file.exists():
        return None
    
    try:
        with open(dataset_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return None


def load_solution(scale: str, experiment: str, run: int, algorithm: str) -> Optional[Dict]:
    """Load solution for a specific algorithm."""
    exp_dir = EXPERIMENTS_DIR / scale / experiment
    solution_file = exp_dir / f"run_{run}_{algorithm}.json"
    
    if not solution_file.exists():
        return None
    
    try:
        with open(solution_file, 'r') as f:
            data = json.load(f)
            if 'results' in data and len(data['results']) > 0:
                return data['results'][0]
            return None
    except Exception as e:
        print(f"Error loading solution for {algorithm}: {e}")
        return None


def render_tile_matrix(tile_matrix: List[List[int]]) -> str:
    """Render a single tile as ASCII art."""
    if not tile_matrix:
        return "Empty tile"
    
    lines = []
    for row in tile_matrix:
        line = " ".join("█" if cell == 1 else "·" for cell in row)
        lines.append(line)
    
    return "\n".join(lines)


def render_all_tiles(tiles: List[List[List[int]]]) -> str:
    """Render all tiles in a grid layout."""
    if not tiles:
        return "No tiles available"
    
    result = []
    result.append(f"Total Tiles: {len(tiles)}\n")
    result.append("=" * 60)
    
    # Render tiles in rows of 4
    tiles_per_row = 4
    for i in range(0, len(tiles), tiles_per_row):
        row_tiles = tiles[i:i + tiles_per_row]
        
        # Get tile labels
        labels = [f"Tile {i+j+1:2d}" for j in range(len(row_tiles))]
        result.append("  ".join(f"{label:^{len(render_tile_matrix(row_tiles[0]).split(chr(10))[0])}}" for label in labels))
        
        # Render tiles side by side
        tile_renders = [render_tile_matrix(tile).split('\n') for tile in row_tiles]
        max_height = max(len(tr) for tr in tile_renders)
        
        for line_idx in range(max_height):
            line_parts = []
            for tr in tile_renders:
                if line_idx < len(tr):
                    line_parts.append(tr[line_idx])
                else:
                    line_parts.append(" " * len(tr[0]))
            result.append("  ".join(line_parts))
        
        result.append("")  # Empty line between rows
    
    return "\n".join(result)


def render_tiles_image(tiles: List[List[List[int]]], cell_size: int = 35) -> Image.Image:
    """Render 2D strings as binary patterns."""
    if not tiles:
        # Create empty image
        img = Image.new('RGB', (600, 150), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 60), "No 2D strings available", fill='black')
        return img
    
    num_tiles = len(tiles)
    tiles_per_row = 5
    num_rows = (num_tiles + tiles_per_row - 1) // tiles_per_row
    
    tile_height = len(tiles[0])
    tile_width = len(tiles[0][0])
    
    # Calculate image dimensions
    tile_img_width = tile_width * cell_size
    tile_img_height = tile_height * cell_size
    spacing = 30
    label_height = 30
    
    img_width = tiles_per_row * tile_img_width + (tiles_per_row + 1) * spacing
    img_height = num_rows * (tile_img_height + label_height + spacing) + spacing
    
    # Create image
    img = Image.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Define colors
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
        '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A8E6CF'
    ]
    
    for idx, tile in enumerate(tiles):
        row = idx // tiles_per_row
        col = idx % tiles_per_row
        
        x_offset = col * (tile_img_width + spacing) + spacing
        y_offset = row * (tile_img_height + label_height + spacing) + spacing
        
        # Draw 2D string label with color indicator
        color = colors[idx % len(colors)]
        label = f"String {idx + 1}"
        # Draw colored box next to label
        draw.rectangle([x_offset, y_offset, x_offset + 20, y_offset + 15], fill=color, outline='black', width=1)
        draw.text((x_offset + 25, y_offset), label, fill='black')
        
        # Draw 2D string pattern
        tile_y_start = y_offset + label_height
        
        for i, row_data in enumerate(tile):
            for j, cell in enumerate(row_data):
                x1 = x_offset + j * cell_size
                y1 = tile_y_start + i * cell_size
                
                # Draw binary digit (no background, no grid)
                text = str(cell)
                bbox = draw.textbbox((0, 0), text)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                text_x = x1 + (cell_size - text_width) // 2
                text_y = y1 + (cell_size - text_height) // 2
                
                draw.text((text_x, text_y), text, fill='black')
    
    return img


def render_placement_image(tiles: List[List[List[int]]], placements: List[Dict], cell_size: int = 25) -> Image.Image:
    """Render the 2D string canvas with rounded bounding boxes for substrings."""
    if not placements:
        # Create empty image
        img = Image.new('RGB', (600, 150), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 60), "No placement available", fill='black')
        return img
    
    # Find bounding box
    min_x, max_x = float('inf'), float('-inf')
    min_y, max_y = float('inf'), float('-inf')
    
    for placement in placements:
        tile_id = placement['tile_id']
        ox, oy = placement['x'], placement['y']
        tile = tiles[tile_id]
        
        for i, row in enumerate(tile):
            for j, cell in enumerate(row):
                if cell == 1:
                    px = ox + j
                    py = oy + i
                    min_x = min(min_x, px)
                    max_x = max(max_x, px)
                    min_y = min(min_y, py)
                    max_y = max(max_y, py)
    
    # Calculate image dimensions
    width = max_x - min_x + 1
    height = max_y - min_y + 1
    
    img_width = width * cell_size + 150  # Add padding for labels
    img_height = height * cell_size + 150
    
    # Create image
    img = Image.new('RGB', (img_width, img_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw title
    title = f"2D String Canvas: {width}×{height}"
    draw.text((10, 10), title, fill='black')
    
    # Offset for centering
    x_offset = 50
    y_offset = 50
    
    # Define colors (same as tiles)
    colors = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
        '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A8E6CF'
    ]
    
    # Build the complete 2D string canvas
    canvas = [['-' for _ in range(width)] for _ in range(height)]
    
    for placement in placements:
        tile_id = placement['tile_id']
        ox, oy = placement['x'], placement['y']
        tile = tiles[tile_id]
        
        for i, row in enumerate(tile):
            for j, cell in enumerate(row):
                px = ox + j - min_x
                py = oy + i - min_y
                # Only write if within bounds
                if 0 <= py < height and 0 <= px < width:
                    if cell == 1:
                        canvas[py][px] = '1'
                    else:
                        canvas[py][px] = '0'
    
    # Draw the 2D string canvas
    for y in range(height):
        for x in range(width):
            x1 = x_offset + x * cell_size
            y1 = y_offset + y * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size
            
            # Draw binary digit (no background, no grid)
            text = canvas[y][x]
            bbox = draw.textbbox((0, 0), text)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = x1 + (cell_size - text_width) // 2
            text_y = y1 + (cell_size - text_height) // 2
            
            draw.text((text_x, text_y), text, fill='black')
    
    # Store substring info for drawing rounded bounding boxes
    substring_info = []
    
    for placement in placements:
        tile_id = placement['tile_id']
        ox, oy = placement['x'], placement['y']
        tile = tiles[tile_id]
        color = colors[tile_id % len(colors)]
        
        # Get full tile dimensions (m x n)
        tile_height = len(tile)
        tile_width = len(tile[0]) if tile else 0
        
        # Calculate bounding box using full tile dimensions (m x n)
        tile_top_left_x = ox - min_x
        tile_top_left_y = oy - min_y
        
        bbox_x1 = x_offset + tile_top_left_x * cell_size - 1
        bbox_y1 = y_offset + tile_top_left_y * cell_size - 1
        bbox_x2 = x_offset + (tile_top_left_x + tile_width) * cell_size + 1
        bbox_y2 = y_offset + (tile_top_left_y + tile_height) * cell_size + 1
        substring_info.append((tile_id, color, bbox_x1, bbox_y1, bbox_x2, bbox_y2))
    
    # Draw rounded bounding boxes for substrings (no labels)
    radius = 6
    for tile_id, color, x1, y1, x2, y2 in substring_info:
        # Draw rounded rectangle using arcs
        draw.arc([x1, y1, x1 + radius * 2, y1 + radius * 2], 180, 270, fill=color, width=3)
        draw.arc([x2 - radius * 2, y1, x2, y1 + radius * 2], 270, 360, fill=color, width=3)
        draw.arc([x1, y2 - radius * 2, x1 + radius * 2, y2], 90, 180, fill=color, width=3)
        draw.arc([x2 - radius * 2, y2 - radius * 2, x2, y2], 0, 90, fill=color, width=3)
        
        # Draw straight lines
        draw.line([x1 + radius, y1, x2 - radius, y1], fill=color, width=3)
        draw.line([x2, y1 + radius, x2, y2 - radius], fill=color, width=3)
        draw.line([x1 + radius, y2, x2 - radius, y2], fill=color, width=3)
        draw.line([x1, y1 + radius, x1, y2 - radius], fill=color, width=3)
    
    # Draw axis labels
    draw.text((5, y_offset + height * cell_size // 2), f"H={height}", fill='black')
    draw.text((x_offset + width * cell_size // 2, img_height - 20), f"W={width}", fill='black')
    
    return img


def format_canvas(canvas_str: str) -> str:
    """Format canvas string for better readability."""
    if not canvas_str:
        return "No canvas available"
    
    # Replace dots with unicode characters for better visibility
    canvas_str = canvas_str.replace('.', '·')
    
    return canvas_str


def create_solution_summary(solution: Dict, algorithm: str) -> str:
    """Create a summary text for a solution."""
    if not solution:
        return f"No solution available for {ALGORITHM_NAMES.get(algorithm, algorithm)}"
    
    lines = []
    lines.append(f"Algorithm: {ALGORITHM_NAMES.get(algorithm, algorithm)}")
    lines.append("=" * 50)
    lines.append(f"Status: {solution.get('status', 'unknown')}")
    
    if solution.get('status') in ['success', 'optimal', 'feasible']:
        lines.append(f"Objective (L): {solution.get('objective', 'N/A')}")
        lines.append(f"Bounding Box: {solution.get('bbox_width', '?')} × {solution.get('bbox_height', '?')}")
        lines.append(f"Area: {solution.get('bbox_area', 'N/A')}")
        lines.append(f"Runtime: {solution.get('runtime_seconds', 0):.3f} seconds")
        lines.append(f"Tiles Placed: {solution.get('num_tiles_placed', 'N/A')}")
        
        # Add genetic algorithm stats if available
        if 'total_crossovers' in solution:
            lines.append(f"Total Crossovers: {solution.get('total_crossovers', 0)}")
            if 'crossovers_needing_completion' in solution:
                completion = solution.get('crossovers_needing_completion', 0)
                total = solution.get('total_crossovers', 1)
                rate = (completion / total * 100) if total > 0 else 0
                lines.append(f"Completion Rate: {rate:.1f}%")
    else:
        lines.append(f"Error: {solution.get('error', 'Unknown error')}")
    
    return "\n".join(lines)


def compare_solutions(solutions: Dict[str, Dict]) -> str:
    """Create a comparison table of all solutions."""
    if not solutions:
        return "No solutions to compare"
    
    # Filter valid solutions
    valid_solutions = {alg: sol for alg, sol in solutions.items() 
                      if sol and sol.get('status') in ['success', 'optimal', 'feasible']}
    
    if not valid_solutions:
        return "No valid solutions found"
    
    # Create comparison data
    data = []
    for alg, sol in sorted(valid_solutions.items()):
        data.append({
            'Algorithm': ALGORITHM_NAMES.get(alg, alg),
            'Objective': sol.get('objective', 'N/A'),
            'BBox': f"{sol.get('bbox_width', '?')}×{sol.get('bbox_height', '?')}",
            'Area': sol.get('bbox_area', 'N/A'),
            'Runtime (s)': f"{sol.get('runtime_seconds', 0):.3f}"
        })
    
    df = pd.DataFrame(data)
    
    # Find best objective
    objectives = [d['Objective'] for d in data if isinstance(d['Objective'], (int, float))]
    if objectives:
        best_obj = min(objectives)
        result = "SOLUTION COMPARISON\n"
        result += "=" * 70 + "\n\n"
        result += df.to_string(index=False)
        result += f"\n\n🏆 Best Objective: {best_obj}"
        
        # Find which algorithms achieved best
        best_algs = [d['Algorithm'] for d in data if d['Objective'] == best_obj]
        if best_algs:
            result += f" (achieved by: {', '.join(best_algs)})"
        
        return result
    
    return df.to_string(index=False)


def visualize_test_case(scale: str, experiment: str, run: int) -> Tuple:
    """Main function to visualize a test case and all solutions."""
    
    if not scale or not experiment or not run:
        empty_img = Image.new('RGB', (400, 100), color='white')
        return ("Please select a test case", "", "", empty_img, "", "", "", "", "", empty_img, empty_img, empty_img, empty_img, empty_img)
    
    seed = seed_from_run(run)
    
    # Load dataset
    dataset = load_tile_dataset(scale, experiment, run)
    if not dataset:
        empty_img = Image.new('RGB', (400, 100), color='white')
        return (f"Dataset not found for {scale}/{experiment}/run {run}", "", "", empty_img, "", "", "", "", "", empty_img, empty_img, empty_img, empty_img, empty_img)
    
    # Render tiles
    tiles = dataset.get('input', {}).get('tiles', [])
    tiles_display = render_all_tiles(tiles)
    tiles_image = render_tiles_image(tiles)
    
    # Test case info
    info = f"Test Case: {experiment} (Run {run})\n"
    info += f"Scale: {scale.upper()}\n"
    info += f"Seed: {seed}\n"
    info += f"Number of Tiles: {len(tiles)}\n"
    info += f"Tile Size: {dataset.get('input', {}).get('n', '?')}×{dataset.get('input', {}).get('m', '?')}"
    
    # Load all solutions
    algorithms = ['greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'cplex']
    solutions = {}
    for alg in algorithms:
        solutions[alg] = load_solution(scale, experiment, run, alg)
    
    # Create comparison
    comparison = compare_solutions(solutions)
    
    # Get individual solution displays and images
    sol_displays = {}
    sol_images = {}
    for alg in algorithms:
        sol = solutions.get(alg)
        summary = create_solution_summary(sol, alg)
        
        if sol and 'canvas' in sol:
            canvas = format_canvas(sol['canvas'])
            sol_displays[alg] = f"{summary}\n\nCanvas:\n{canvas}"
            
            # Create placement image
            if 'placements' in sol:
                sol_images[alg] = render_placement_image(tiles, sol['placements'])
            else:
                sol_images[alg] = Image.new('RGB', (400, 100), color='white')
        else:
            sol_displays[alg] = summary
            sol_images[alg] = Image.new('RGB', (400, 100), color='white')
    
    return (
        info,
        tiles_display,
        comparison,
        tiles_image,
        sol_displays.get('greedy', ''),
        sol_displays.get('stochastic_greedy', ''),
        sol_displays.get('genetic_greedy', ''),
        sol_displays.get('genetic_stochastic', ''),
        sol_displays.get('cplex', ''),
        sol_images.get('greedy'),
        sol_images.get('stochastic_greedy'),
        sol_images.get('genetic_greedy'),
        sol_images.get('genetic_stochastic'),
        sol_images.get('cplex')
    )


def update_experiments(scale: str) -> gr.Dropdown:
    """Update experiment dropdown based on selected scale."""
    experiments = get_experiments_for_scale(scale)
    return gr.Dropdown(choices=experiments, value=experiments[0] if experiments else None)


def update_runs(scale: str, experiment: str) -> gr.Dropdown:
    """Update runs dropdown based on selected scale and experiment."""
    runs = get_runs_for_experiment(scale, experiment)
    return gr.Dropdown(choices=runs, value=runs[0] if runs else None)


# Create Gradio interface
with gr.Blocks(title="MDSSP Solution Visualizer") as app:
    gr.Markdown("# MDSSP Solution Visualizer")
    gr.Markdown("Compare algorithm solutions for Multi-Dimensional Symbol Structure Placement problems")
    
    with gr.Row():
        with gr.Column(scale=1):
            scale_dropdown = gr.Dropdown(
                choices=get_available_scales(),
                label="Scale",
                value="medium"
            )
            
            experiment_dropdown = gr.Dropdown(
                choices=[],
                label="Experiment (Tile Count)",
                value=None
            )
            
            run_dropdown = gr.Dropdown(
                choices=[],
                label="Run Number",
                value=None
            )
            
            visualize_btn = gr.Button("Load Test Case", variant="primary")
        
        with gr.Column(scale=2):
            info_display = gr.Textbox(
                label="Test Case Information",
                lines=5,
                max_lines=10
            )
    
    with gr.Row():
        with gr.Column():
            tiles_display = gr.Textbox(
                label="Tile Set (ASCII)",
                lines=20,
                max_lines=30,
                elem_classes=["monospace"]
            )
        with gr.Column():
            tiles_image = gr.Image(
                label="Tile Set (Visual)",
                type="pil"
            )
    
    gr.Markdown("## Solution Comparison")
    
    comparison_display = gr.Textbox(
        label="Algorithm Comparison",
        lines=8,
        max_lines=15
    )
    
    gr.Markdown("## Individual Solutions")
    
    with gr.Tabs():
        with gr.Tab("Greedy"):
            with gr.Row():
                with gr.Column():
                    greedy_display = gr.Textbox(
                        label="Greedy Solution (ASCII)",
                        lines=25,
                        max_lines=40,
                        elem_classes=["monospace"]
                    )
                with gr.Column():
                    greedy_image = gr.Image(
                        label="Greedy Placement (Visual)",
                        type="pil"
                    )
        
        with gr.Tab("Stochastic Greedy"):
            with gr.Row():
                with gr.Column():
                    stochastic_display = gr.Textbox(
                        label="Stochastic Greedy Solution (ASCII)",
                        lines=25,
                        max_lines=40,
                        elem_classes=["monospace"]
                    )
                with gr.Column():
                    stochastic_image = gr.Image(
                        label="Stochastic Greedy Placement (Visual)",
                        type="pil"
                    )
        
        with gr.Tab("Genetic + Greedy"):
            with gr.Row():
                with gr.Column():
                    genetic_greedy_display = gr.Textbox(
                        label="Genetic + Greedy Solution (ASCII)",
                        lines=25,
                        max_lines=40,
                        elem_classes=["monospace"]
                    )
                with gr.Column():
                    genetic_greedy_image = gr.Image(
                        label="Genetic + Greedy Placement (Visual)",
                        type="pil"
                    )
        
        with gr.Tab("Genetic + Stochastic"):
            with gr.Row():
                with gr.Column():
                    genetic_stochastic_display = gr.Textbox(
                        label="Genetic + Stochastic Solution (ASCII)",
                        lines=25,
                        max_lines=40,
                        elem_classes=["monospace"]
                    )
                with gr.Column():
                    genetic_stochastic_image = gr.Image(
                        label="Genetic + Stochastic Placement (Visual)",
                        type="pil"
                    )
        
        with gr.Tab("CPLEX"):
            with gr.Row():
                with gr.Column():
                    cplex_display = gr.Textbox(
                        label="CPLEX Solution (ASCII)",
                        lines=25,
                        max_lines=40,
                        elem_classes=["monospace"]
                    )
                with gr.Column():
                    cplex_image = gr.Image(
                        label="CPLEX Placement (Visual)",
                        type="pil"
                    )
    
    # Set up event handlers
    scale_dropdown.change(
        fn=update_experiments,
        inputs=[scale_dropdown],
        outputs=[experiment_dropdown]
    ).then(
        fn=update_runs,
        inputs=[scale_dropdown, experiment_dropdown],
        outputs=[run_dropdown]
    )
    
    experiment_dropdown.change(
        fn=update_runs,
        inputs=[scale_dropdown, experiment_dropdown],
        outputs=[run_dropdown]
    )
    
    visualize_btn.click(
        fn=visualize_test_case,
        inputs=[scale_dropdown, experiment_dropdown, run_dropdown],
        outputs=[
            info_display,
            tiles_display,
            comparison_display,
            tiles_image,
            greedy_display,
            stochastic_display,
            genetic_greedy_display,
            genetic_stochastic_display,
            cplex_display,
            greedy_image,
            stochastic_image,
            genetic_greedy_image,
            genetic_stochastic_image,
            cplex_image
        ]
    )
    
    # Initialize dropdowns on load
    app.load(
        fn=update_experiments,
        inputs=[scale_dropdown],
        outputs=[experiment_dropdown]
    ).then(
        fn=update_runs,
        inputs=[scale_dropdown, experiment_dropdown],
        outputs=[run_dropdown]
    )
    
    gr.Markdown("""
    ---
    ### Instructions
    1. Select a scale (small/medium/large)
    2. Choose an experiment configuration (e.g., T20_n3_m3)
    3. Pick a run number
    4. Click "Load Test Case" to visualize
    
    The visualization shows:
    - Test case information and tile set
    - Comparison table of all algorithm results
    - Individual solution canvases for each algorithm
    """)


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )
