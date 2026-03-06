#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

def escape_latex(s: str) -> str:
    return "".join(LATEX_SPECIALS.get(ch, ch) for ch in s)

def grid_from_text(text: str) -> List[List[str]]:
    lines = [ln.rstrip("\n") for ln in text.strip("\n").splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Empty grid.")
    grid: List[List[str]] = []
    for ln in lines:
        ln = ln.strip()
        if " " in ln:
            row = [tok for tok in ln.split() if tok]
        else:
            row = list(ln)
        grid.append(row)
    w = len(grid[0])
    if any(len(r) != w for r in grid):
        raise ValueError("All rows must have the same length.")
    return grid

def _validate_supergrid(supergrid: List[List[str]]) -> None:
    for r, row in enumerate(supergrid):
        for c, v in enumerate(row):
            if v not in ("0", "1", "*"):
                raise ValueError(f"Supergrid must use 0/1/* only. Found {v!r} at ({r},{c}).")

def _validate_subgrid(subgrid: List[List[str]]) -> None:
    for r, row in enumerate(subgrid):
        for c, v in enumerate(row):
            if v not in ("0", "1"):
                raise ValueError(f"Subgrid must be binary 0/1 only. Found {v!r} at ({r},{c}).")

def find_2d_occurrences_super_wildcard(
    supergrid: List[List[str]],
    subgrid: List[List[str]],
) -> List[Tuple[int, int]]:
    H, W = len(supergrid), len(supergrid[0])
    h, w = len(subgrid), len(subgrid[0])
    if h > H or w > W:
        return []
    matches: List[Tuple[int, int]] = []
    for r0 in range(H - h + 1):
        for c0 in range(W - w + 1):
            ok = True
            for r in range(h):
                for c in range(w):
                    s = supergrid[r0 + r][c0 + c]
                    p = subgrid[r][c]
                    if s != "*" and s != p:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                matches.append((r0, c0))
    return matches

@dataclass(frozen=True)
class Rect:
    r1: int
    c1: int
    r2: int
    c2: int
    color: str
    opacity: float

def latex_tikz_2d_rectangles_only(
    supergrid: List[List[str]],
    substrings: List[List[List[str]]],
    colors: Optional[List[str]] = None,
    min_opacity: float = 0.25,
    max_opacity: float = 0.95,
    line_thickness: str = "thick",
    cell_min_size: str = "5.2mm",
    font_cmd: str = r"\footnotesize",
    caption: str = "2D superstring with substring occurrences highlighted.",
    label: str = "fig:2d-occ",
    render_star_as_blank: bool = False,
    shrink: str = "0.6pt",   # <<< NEW: inset amount to reduce rectangle size
) -> str:
    """
    Rectangles only (outlines), no grid lines.
    Each rectangle is shrunk by `shrink` from all sides to avoid overlap.
    Each occurrence is drawn only once (duplicates are removed).
    """
    _validate_supergrid(supergrid)
    if not substrings:
        raise ValueError("Provide at least one substring.")
    for sub in substrings:
        _validate_subgrid(sub)

    if colors is None:
        colors = [
            "red", "blue", "green!60!black", "orange", "purple", "cyan!60!black", 
            "magenta", "teal", "brown", "lime", "pink", "olive", "violet", 
            "gray", "yellow!80!red", "blue!50!cyan", "red!70!black", 
            "green!50!yellow", "purple!70!blue", "orange!80!red"
        ]

    k = len(substrings)
    def opacity_for(i: int) -> float:
        if k == 1:
            return max_opacity
        t = i / (k - 1)
        return max(0.0, min(1.0, min_opacity + t * (max_opacity - min_opacity)))

    H, W = len(supergrid), len(supergrid[0])

    rects: List[Rect] = []
    seen_rects = set()  # Track (r1, c1, r2, c2) to avoid duplicates
    for i, sub in enumerate(substrings):
        h, w = len(sub), len(sub[0])
        col = colors[i % len(colors)]
        op = opacity_for(i)
        for (r0, c0) in find_2d_occurrences_super_wildcard(supergrid, sub):
            rect_key = (r0 + 1, c0 + 1, r0 + h, c0 + w)
            if rect_key not in seen_rects:
                seen_rects.add(rect_key)
                rects.append(Rect(r1=r0 + 1, c1=c0 + 1, r2=r0 + h, c2=c0 + w, color=col, opacity=op))

    def cell_text(v: str) -> str:
        if render_star_as_blank and v == "*":
            return ""
        return escape_latex(v)

    matrix_rows = []
    for r in range(H):
        row = " & ".join(cell_text(supergrid[r][c]) for c in range(W))
        matrix_rows.append(row + r" \\")
    matrix_body = "\n".join(matrix_rows)

    nodes_style = (
        f"nodes={{"
        f"minimum width={cell_min_size}, minimum height={cell_min_size},"
        f"inner sep=0pt, outer sep=0pt,"
        f"font={font_cmd}"
        f"}}"
    )

    # <<< NEW: shrink corners inward by `shrink`
    # NW corner moves ( +x, -y ), SE corner moves ( -x, +y )
    rect_lines: List[str] = []
    if rects:
        for rr in rects:
            nw = rf"([xshift={shrink},yshift=-{shrink}]m-{rr.r1}-{rr.c1}.north west)"
            se = rf"([xshift=-{shrink},yshift={shrink}]m-{rr.r2}-{rr.c2}.south east)"
            rect_lines.append(
                rf"\draw[{rr.color},{line_thickness},opacity={rr.opacity:.3f}] {nw} rectangle {se};"
            )
    else:
        rect_lines.append("% (no matches found)")

    rect_code = "\n".join(rect_lines)

    return rf"""\begin{{figure}}
\centering
\begin{{tikzpicture}}[baseline=(m.center)]
\matrix (m) [matrix of nodes,
row sep=0pt, column sep=0pt,
{nodes_style}] {{
{matrix_body}
}};
{rect_code}
\end{{tikzpicture}}
\caption{{{escape_latex(caption)}}}
\label{{{escape_latex(label)}}}
\end{{figure}}"""


# -------------------- Experiment Data Loading --------------------

def load_experiment_json(filepath: str) -> Tuple[Dict[str, Any], str]:
    """Load a single experiment result JSON file.
    
    Returns:
        Tuple of (experiment_data, filepath) - filepath is useful for resolving relative dataset paths
    """
    with open(filepath, 'r') as f:
        return json.load(f), filepath


def load_tiles_from_input(input_data: Dict[str, Any], experiment_filepath: Optional[str] = None) -> List[List[List[int]]]:
    """
    Load tiles from input data, handling both inline tiles and referenced dataset files.
    
    Args:
        input_data: The 'input' section from experiment JSON
        experiment_filepath: Path to the experiment result file (for resolving relative dataset paths)
    
    Returns:
        List of tiles (2D int arrays)
    """
    tiles_data = input_data.get('tiles', [])
    
    if tiles_data:
        return tiles_data
    
    # Check if tiles are in a referenced dataset file
    if input_data.get('source') == 'dataset' and input_data.get('dataset_file'):
        dataset_file = input_data['dataset_file']
        
        # Try multiple possible paths for the dataset file
        paths_to_try = [Path(dataset_file)]
        
        # If experiment filepath is provided, try relative to its directory
        if experiment_filepath:
            exp_dir = Path(experiment_filepath).parent
            paths_to_try.append(exp_dir / Path(dataset_file).name)
            paths_to_try.append(exp_dir / dataset_file)
        
        for dataset_path in paths_to_try:
            try:
                if dataset_path.exists():
                    with open(dataset_path, 'r') as f:
                        dataset = json.load(f)
                        tiles_data = dataset.get('tiles', [])
                        if tiles_data:
                            # Also copy structured_metadata if present
                            if 'structured_metadata' in dataset and 'structured_metadata' not in input_data:
                                input_data['structured_metadata'] = dataset['structured_metadata']
                            return tiles_data
            except Exception:
                continue
    
    return tiles_data


def parse_canvas_string(canvas_str: str) -> List[List[str]]:
    """
    Parse canvas string from experiment results.
    Format: "0 1 . 1\n1 0 1 .\n..."
    '.' represents empty/wildcard cells.
    """
    lines = canvas_str.strip().split('\n')
    grid: List[List[str]] = []
    for line in lines:
        row = line.split()
        # Convert '.' to '*' for wildcard representation
        row = ['*' if cell == '.' else cell for cell in row]
        grid.append(row)
    return grid


# -------------------- Source Bitmap Generation (for structured experiments) --------------------

def regenerate_source_bitmap(height: int, width: int, seed: int, pattern: str = 'random') -> List[List[int]]:
    """
    Regenerate the source bitmap used for structured experiments.
    This must match the generate_source_bitmap function in systematic_experiments.py.
    
    Args:
        height: Height of the bitmap
        width: Width of the bitmap
        seed: Random seed for reproducibility
        pattern: Pattern name ('random', 'checkerboard', 'qrcode', etc.)
    
    Returns:
        2D list of 0/1 values
    """
    rng = random.Random(seed)
    
    if pattern == 'random':
        return [[rng.randint(0, 1) for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'checkerboard':
        return [[(i + j) % 2 for j in range(width)] for i in range(height)]
    
    elif pattern == 'stripes_h':
        return [[i % 2 for _ in range(width)] for i in range(height)]
    
    elif pattern == 'stripes_v':
        return [[j % 2 for j in range(width)] for _ in range(height)]
    
    elif pattern == 'diagonal':
        return [[1 if (i + j) % 4 < 2 else 0 for j in range(width)] for i in range(height)]
    
    elif pattern == 'blocks':
        block_size = 4
        return [[1 if ((i // block_size) + (j // block_size)) % 2 == 0 else 0 
                 for j in range(width)] for i in range(height)]
    
    elif pattern == 'gradient':
        return [[1 if rng.random() < 1 - (i + j) / (height + width) else 0 
                 for j in range(width)] for i in range(height)]
    
    elif pattern == 'sparse':
        return [[1 if rng.random() < 0.25 else 0 for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'dense':
        return [[1 if rng.random() < 0.75 else 0 for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'qrcode':
        bitmap = [[0 for _ in range(width)] for _ in range(height)]
        
        def draw_finder(r0, c0):
            for i in range(7):
                for j in range(7):
                    if r0 + i < height and c0 + j < width:
                        if i == 0 or i == 6 or j == 0 or j == 6:
                            bitmap[r0 + i][c0 + j] = 1
                        elif i == 1 or i == 5 or j == 1 or j == 5:
                            bitmap[r0 + i][c0 + j] = 0
                        else:
                            bitmap[r0 + i][c0 + j] = 1
        
        draw_finder(0, 0)
        draw_finder(0, width - 7)
        draw_finder(height - 7, 0)
        
        if height > 6:
            for j in range(8, width - 8):
                bitmap[6][j] = j % 2
        
        if width > 6:
            for i in range(8, height - 8):
                bitmap[i][6] = i % 2
        
        for i in range(height):
            for j in range(width):
                in_finder = ((i < 8 and j < 8) or
                            (i < 8 and j >= width - 8) or
                            (i >= height - 8 and j < 8))
                in_timing = (i == 6 and 8 <= j < width - 8) or (j == 6 and 8 <= i < height - 8)
                
                if not in_finder and not in_timing:
                    bitmap[i][j] = rng.randint(0, 1)
        
        return bitmap
    
    else:
        return [[rng.randint(0, 1) for _ in range(width)] for _ in range(height)]


def latex_source_bitmap(
    bitmap: List[List[int]],
    cell_min_size: str = "3.5mm",
    font_cmd: str = r"\tiny",
    caption: str = "Original source bitmap",
    label: str = "fig:source-bitmap",
    show_values: bool = False,
) -> str:
    """
    Generate LaTeX TikZ figure for the original source bitmap (structured experiments).
    
    Args:
        bitmap: 2D list of 0/1 values
        cell_min_size: Minimum cell size
        font_cmd: LaTeX font command
        caption: Figure caption
        label: Figure label
        show_values: If True, show 0/1 values; if False, use filled/empty cells
    """
    H = len(bitmap)
    W = len(bitmap[0]) if H else 0
    
    if show_values:
        # Show 0/1 values in cells
        matrix_rows = []
        for r in range(H):
            row = " & ".join(str(bitmap[r][c]) for c in range(W))
            matrix_rows.append(row + r" \\")
        matrix_body = "\n".join(matrix_rows)
        
        nodes_style = (
            f"nodes={{minimum width={cell_min_size}, minimum height={cell_min_size},"
            f"inner sep=0pt, outer sep=0pt, font={font_cmd}}}"
        )
        
        return rf"""\begin{{figure}}
\centering
\begin{{tikzpicture}}[baseline=(m.center)]
\matrix (m) [matrix of nodes,
row sep=0pt, column sep=0pt,
{nodes_style}] {{
{matrix_body}
}};
\end{{tikzpicture}}
\caption{{{escape_latex(caption)}}}
\label{{{escape_latex(label)}}}
\end{{figure}}"""
    else:
        # Use filled rectangles for 1s, empty for 0s (more compact visualization)
        fill_commands = []
        for r in range(H):
            for c in range(W):
                if bitmap[r][c] == 1:
                    # Fill cell at (c, H-1-r) - TikZ uses bottom-left origin
                    fill_commands.append(f"\\fill[black] ({c},{H-1-r}) rectangle ({c+1},{H-r});")
        
        fill_code = "\n".join(fill_commands)
        
        return rf"""\begin{{figure}}
\centering
\begin{{tikzpicture}}[x={cell_min_size}, y={cell_min_size}]
\draw[step=1, gray!50, very thin] (0,0) grid ({W},{H});
{fill_code}
\draw[black, thick] (0,0) rectangle ({W},{H});
\end{{tikzpicture}}
\caption{{{escape_latex(caption)}}}
\label{{{escape_latex(label)}}}
\end{{figure}}"""


def tiles_from_experiment(tiles_data: List[List[List[int]]]) -> List[List[List[str]]]:
    """
    Convert tiles from experiment format (list of 2D int arrays) 
    to our format (list of 2D string arrays).
    """
    result: List[List[List[str]]] = []
    for tile in tiles_data:
        str_tile: List[List[str]] = []
        for row in tile:
            str_tile.append([str(v) for v in row])
        result.append(str_tile)
    return result


def find_experiment_files(experiment_path: str, pattern: Optional[str] = None) -> List[str]:
    """
    Find experiment JSON files in a directory.
    If pattern is provided, filter by pattern (e.g., 'best_cplex', 'run_1_greedy').
    """
    path = Path(experiment_path)
    if path.is_file():
        return [str(path)]
    
    json_files = list(path.glob('*.json'))
    
    if pattern:
        json_files = [f for f in json_files if pattern in f.name]
    else:
        # Exclude summary files, prefer solution files
        exclude_patterns = ['all_results', 'summary', 'metadata']
        json_files = [f for f in json_files 
                      if not any(ex in f.name for ex in exclude_patterns)]
    
    return sorted([str(f) for f in json_files])


def latex_from_experiment(
    experiment_data: Dict[str, Any],
    result_index: int = 0,
    colors: Optional[List[str]] = None,
    min_opacity: float = 0.25,
    max_opacity: float = 0.95,
    line_thickness: str = "thick",
    cell_min_size: str = "5.2mm",
    font_cmd: str = r"\footnotesize",
    caption: Optional[str] = None,
    label: Optional[str] = None,
    render_star_as_blank: bool = False,
    shrink: str = "0.6pt",
    experiment_filepath: Optional[str] = None,
) -> str:
    """
    Generate LaTeX from experiment data.
    
    Args:
        experiment_data: Loaded JSON data from experiment file
        result_index: Which result to use if multiple results exist
        colors: List of colors for tile rectangles
        experiment_filepath: Path to the experiment file (for resolving relative dataset paths)
        ... (other formatting options)
    """
    input_data = experiment_data.get('input', {})
    results = experiment_data.get('results', [])
    
    if not results:
        raise ValueError("No results found in experiment data")
    
    if result_index >= len(results):
        raise ValueError(f"Result index {result_index} out of range (only {len(results)} results)")
    
    result = results[result_index]
    
    # Parse the canvas
    canvas_str = result.get('canvas', '')
    if not canvas_str:
        raise ValueError("No canvas found in result")
    
    supergrid = parse_canvas_string(canvas_str)
    
    # Get tiles from input (either directly or from referenced dataset file)
    tiles_data = load_tiles_from_input(input_data, experiment_filepath)
    
    if not tiles_data:
        raise ValueError("No tiles found in input data (check if dataset file exists)")
    
    substrings = tiles_from_experiment(tiles_data)
    
    # Generate caption if not provided
    if caption is None:
        algorithm = result.get('algorithm', 'unknown')
        objective = result.get('objective', '?')
        bbox_w = result.get('bbox_width', '?')
        bbox_h = result.get('bbox_height', '?')
        num_tiles = len(tiles_data)
        
        # Check for structured experiment metadata
        structured_meta = input_data.get('structured_metadata', {})
        if structured_meta:
            optimal_area = structured_meta.get('optimal_area', '?')
            src_h = structured_meta.get('source_height', '?')
            src_w = structured_meta.get('source_width', '?')
            pattern = structured_meta.get('pattern', 'random')
            if objective != '?' and optimal_area != '?':
                compression = optimal_area / objective if objective > 0 else 0
                caption = f"{algorithm.upper()}: {num_tiles} tiles from {src_h}x{src_w} ({pattern}), area={objective} (optimal={optimal_area}, ratio={compression:.2f})"
            else:
                caption = f"{algorithm.upper()}: {num_tiles} tiles from {src_h}x{src_w} ({pattern}), area={objective}, bbox={bbox_w}x{bbox_h}"
        else:
            caption = f"{algorithm.upper()}: {num_tiles} tiles, objective={objective}, bbox={bbox_w}x{bbox_h}"
    
    # Generate label if not provided
    if label is None:
        algorithm = result.get('algorithm', 'unknown')
        seed = input_data.get('seed', 0)
        structured_meta = input_data.get('structured_metadata', {})
        if structured_meta:
            src_h = structured_meta.get('source_height', 0)
            src_w = structured_meta.get('source_width', 0)
            label = f"fig:{algorithm}-src{src_h}x{src_w}-seed{seed}"
        else:
            label = f"fig:{algorithm}-seed{seed}"
    
    return latex_tikz_2d_rectangles_only(
        supergrid=supergrid,
        substrings=substrings,
        colors=colors,
        min_opacity=min_opacity,
        max_opacity=max_opacity,
        line_thickness=line_thickness,
        cell_min_size=cell_min_size,
        font_cmd=font_cmd,
        caption=caption,
        label=label,
        render_star_as_blank=render_star_as_blank,
        shrink=shrink,
    )


def latex_tikz_subfigure(
    supergrid: List[List[str]],
    substrings: List[List[List[str]]],
    colors: Optional[List[str]] = None,
    min_opacity: float = 0.25,
    max_opacity: float = 0.95,
    line_thickness: str = "thick",
    cell_min_size: str = "5.2mm",
    font_cmd: str = r"\footnotesize",
    subcaption: str = "",
    sublabel: str = "",
    render_star_as_blank: bool = False,
    shrink: str = "0.6pt",
    width: str = "0.48",
) -> str:
    """
    Generate a subfigure LaTeX snippet (without figure wrapper).
    Used for side-by-side comparison.
    Each occurrence is drawn only once (duplicates are removed).
    """
    if colors is None:
        colors = [
            "red", "blue", "green!60!black", "orange", "purple", "cyan!60!black", 
            "magenta", "teal", "brown", "lime", "pink", "olive", "violet", 
            "gray", "yellow!80!red", "blue!50!cyan", "red!70!black", 
            "green!50!yellow", "purple!70!blue", "orange!80!red"
        ]

    _validate_supergrid(supergrid)
    for sub in substrings:
        _validate_subgrid(sub)

    H = len(supergrid)
    W = len(supergrid[0]) if H else 0

    rects: List[Rect] = []
    n_subs = len(substrings)
    seen_rects = set()  # Track (r1, c1, r2, c2) to avoid duplicates

    def opacity_for(i: int) -> float:
        if n_subs == 1:
            return max_opacity
        return min_opacity + (max_opacity - min_opacity) * i / (n_subs - 1)

    for i, sub in enumerate(substrings):
        h, w = len(sub), len(sub[0])
        col = colors[i % len(colors)]
        op = opacity_for(i)
        for (r0, c0) in find_2d_occurrences_super_wildcard(supergrid, sub):
            rect_key = (r0 + 1, c0 + 1, r0 + h, c0 + w)
            if rect_key not in seen_rects:
                seen_rects.add(rect_key)
                rects.append(Rect(r1=r0 + 1, c1=c0 + 1, r2=r0 + h, c2=c0 + w, color=col, opacity=op))

    def cell_text(v: str) -> str:
        if render_star_as_blank and v == "*":
            return ""
        return escape_latex(v)

    matrix_rows = []
    for r in range(H):
        row = " & ".join(cell_text(supergrid[r][c]) for c in range(W))
        matrix_rows.append(row + r" \\")
    matrix_body = "\n".join(matrix_rows)

    nodes_style = (
        f"nodes={{minimum width={cell_min_size}, minimum height={cell_min_size},"
        f"inner sep=0pt, outer sep=0pt,font={font_cmd}}}"
    )

    rect_lines = []
    for rect in rects:
        rect_lines.append(
            f"\\draw[{rect.color}, {line_thickness}, thick, fill opacity={rect.opacity}] "
            f"([shift={{({shrink},-{shrink})}}]m-{rect.r1}-{rect.c1}.north west) "
            f"rectangle ([shift={{(-{shrink},{shrink})}}]m-{rect.r2}-{rect.c2}.south east);"
        )
    rect_code = "\n".join(rect_lines)

    return f"""\\begin{{subfigure}}{{{width}\\textwidth}}
\\centering
\\begin{{tikzpicture}}[baseline=(m.center)]
\\matrix (m) [matrix of nodes,
row sep=0pt, column sep=0pt,
{nodes_style}] {{
{matrix_body}
}};
{rect_code}
\\end{{tikzpicture}}
\\subcaption{{{subcaption}}}
\\label{{{sublabel}}}
\\end{{subfigure}}"""


def latex_compare_algorithms(
    experiment_data_left: Dict[str, Any],
    experiment_data_right: Dict[str, Any],
    result_index: int = 0,
    colors: Optional[List[str]] = None,
    min_opacity: float = 0.25,
    max_opacity: float = 0.95,
    line_thickness: str = "thick",
    cell_min_size: str = "5.2mm",
    font_cmd: str = r"\footnotesize",
    caption: Optional[str] = None,
    label: Optional[str] = None,
    render_star_as_blank: bool = False,
    shrink: str = "0.6pt",
    subfig_width: str = "0.48",
    experiment_filepath_left: Optional[str] = None,
    experiment_filepath_right: Optional[str] = None,
) -> str:
    """
    Generate LaTeX comparing two algorithm results side-by-side.
    """
    def extract_result_data(exp_data: Dict[str, Any], res_idx: int, exp_filepath: Optional[str] = None):
        input_data = exp_data.get('input', {})
        results = exp_data.get('results', [])
        
        if not results:
            raise ValueError("No results found in experiment data")
        
        if res_idx >= len(results):
            raise ValueError(f"Result index {res_idx} out of range (only {len(results)} results)")
        
        result = results[res_idx]
        canvas_str = result.get('canvas', '')
        if not canvas_str:
            raise ValueError("No canvas found in result")
        
        supergrid = parse_canvas_string(canvas_str)
        
        # Get tiles from input (either directly or from referenced dataset file)
        tiles_data = load_tiles_from_input(input_data, exp_filepath)
        
        if not tiles_data:
            raise ValueError("No tiles found in input data (check if dataset file exists)")
        
        substrings = tiles_from_experiment(tiles_data)
        
        algorithm = result.get('algorithm', 'unknown')
        objective = result.get('objective', '?')
        bbox_w = result.get('bbox_width', '?')
        bbox_h = result.get('bbox_height', '?')
        seed = input_data.get('seed', 0)
        
        return supergrid, substrings, algorithm, objective, bbox_w, bbox_h, seed
    
    # Extract data from both experiments
    sg_left, subs_left, alg_left, obj_left, bw_left, bh_left, seed_left = extract_result_data(experiment_data_left, result_index, experiment_filepath_left)
    sg_right, subs_right, alg_right, obj_right, bw_right, bh_right, seed_right = extract_result_data(experiment_data_right, result_index, experiment_filepath_right)
    
    # Generate subcaptions
    subcaption_left = f"{alg_left.upper()}: obj={obj_left}, bbox={bw_left}$\\times${bh_left}"
    subcaption_right = f"{alg_right.upper()}: obj={obj_right}, bbox={bw_right}$\\times${bh_right}"
    
    sublabel_left = f"fig:{alg_left}"
    sublabel_right = f"fig:{alg_right}"
    
    # Generate subfigures
    subfig_left = latex_tikz_subfigure(
        supergrid=sg_left,
        substrings=subs_left,
        colors=colors,
        min_opacity=min_opacity,
        max_opacity=max_opacity,
        line_thickness=line_thickness,
        cell_min_size=cell_min_size,
        font_cmd=font_cmd,
        subcaption=subcaption_left,
        sublabel=sublabel_left,
        render_star_as_blank=render_star_as_blank,
        shrink=shrink,
        width=subfig_width,
    )
    
    subfig_right = latex_tikz_subfigure(
        supergrid=sg_right,
        substrings=subs_right,
        colors=colors,
        min_opacity=min_opacity,
        max_opacity=max_opacity,
        line_thickness=line_thickness,
        cell_min_size=cell_min_size,
        font_cmd=font_cmd,
        subcaption=subcaption_right,
        sublabel=sublabel_right,
        render_star_as_blank=render_star_as_blank,
        shrink=shrink,
        width=subfig_width,
    )
    
    # Generate overall caption if not provided
    if caption is None:
        num_tiles = len(subs_left)
        caption = f"Comparison of {alg_left.upper()} vs {alg_right.upper()} ({num_tiles} tiles)"
    
    if label is None:
        label = f"fig:compare-{alg_left}-{alg_right}"
    
    return f"""\\begin{{figure}}
\\centering
{subfig_left}
\\hfill
{subfig_right}
\\caption{{{caption}}}
\\label{{{label}}}
\\end{{figure}}"""


def list_available_experiments(base_path: str) -> None:
    """List available experiment configurations in a directory."""
    base = Path(base_path)
    if not base.exists():
        print(f"Path does not exist: {base_path}", file=sys.stderr)
        return
    
    if base.is_file():
        print(f"File: {base_path}")
        return
    
    # Look for experiment subdirectories
    for scale_dir in sorted(base.iterdir()):
        if scale_dir.is_dir() and not scale_dir.name.startswith('.'):
            print(f"\n{scale_dir.name}/")
            for config_dir in sorted(scale_dir.iterdir()):
                # Handle both standard (T...) and structured (src...) experiment directories
                if config_dir.is_dir() and (config_dir.name.startswith('T') or config_dir.name.startswith('src')):
                    json_files = list(config_dir.glob('*.json'))
                    best_files = [f.name for f in json_files if 'best' in f.name]
                    run_count = len([f for f in json_files if f.name.startswith('run_')])
                    dataset_count = len([f for f in json_files if f.name.startswith('dataset_')])
                    
                    # Check if this is a structured experiment
                    if config_dir.name.startswith('src'):
                        # Structured experiment: srcHxW_T..._n..._m...
                        print(f"  {config_dir.name}/  ({run_count} runs, {dataset_count} datasets, best: {', '.join(best_files) or 'none'})")
                    else:
                        print(f"  {config_dir.name}/  ({run_count} runs, best: {', '.join(best_files) or 'none'})")


def main():
    parser = argparse.ArgumentParser(
        description='Generate LaTeX TikZ figures from MDSSP experiment results.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate LaTeX from a specific solution file
  python latex_string.py -f experiment_area/small/T6_n3_m3/best_cplex_solution.json

  # Generate from experiment directory (uses first matching file)
  python latex_string.py -d experiment_area/small/T6_n3_m3 --pattern best_cplex

  # Compare greedy vs genetic_stochastic for run 1
  python latex_string.py -d experiment_area/small/T6_n3_m3 --compare greedy genetic_stochastic --run 1

  # Structured/Reassembly experiments (uses src... directory naming)
  python latex_string.py -d experiments/structured/qrcode/src20x20_T50_n5_m5 --pattern best_greedy
  python latex_string.py -d experiments/structured/qrcode/src20x20_T50_n5_m5 --compare greedy merge_greedy --run 1

  # Show original source bitmap alongside algorithm result (structured only)
  python latex_string.py -d experiments/structured/qrcode/src20x20_T50_n5_m5 --pattern run_1_greedy --show-source
  
  # Show only the source bitmap (structured only)
  python latex_string.py -d experiments/structured/qrcode/src20x20_T50_n5_m5 --pattern run_1_greedy --source-only
  
  # Source bitmap with 0/1 values instead of filled rectangles
  python latex_string.py -d experiments/structured/qrcode/src20x20_T50_n5_m5 --source-only --source-values

  # List available experiments (including structured)
  python latex_string.py --list experiment_area
  python latex_string.py --list experiments/structured

  # Customize output
  python latex_string.py -f result.json --shrink 1.0pt --cell-size 6mm --opacity 0.3:0.9
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument('-f', '--file', type=str, 
                             help='Path to experiment JSON file')
    input_group.add_argument('-d', '--dir', type=str,
                             help='Path to experiment directory')
    input_group.add_argument('--list', type=str, metavar='PATH',
                             help='List available experiments in directory')
    input_group.add_argument('--demo', action='store_true',
                             help='Run with demo/example data')
    
    # Selection options
    parser.add_argument('--pattern', type=str, default=None,
                        help='Filter files by pattern (e.g., "best_cplex", "greedy")')
    parser.add_argument('--result-index', type=int, default=0,
                        help='Index of result to use if file has multiple results (default: 0)')
    
    # Formatting options
    parser.add_argument('--colors', type=str, nargs='+',
                        default=[
                            "red", "blue", "green!60!black", "orange", "purple", "cyan!60!black", 
                            "magenta", "teal", "brown", "lime", "pink", "olive", "violet", 
                            "gray", "yellow!80!red", "blue!50!cyan", "red!70!black", 
                            "green!50!yellow", "purple!70!blue", "orange!80!red"
                        ],
                        help='Colors for tile rectangles (up to 20 default colors)')
    parser.add_argument('--opacity', type=str, default="0.25:0.95",
                        help='Min:max opacity range (default: 0.25:0.95)')
    parser.add_argument('--shrink', type=str, default="0.6pt",
                        help='Rectangle shrink amount (default: 0.6pt)')
    parser.add_argument('--cell-size', type=str, default="5.2mm",
                        help='Minimum cell size (default: 5.2mm)')
    parser.add_argument('--line-thickness', type=str, default="thick",
                        help='Rectangle line thickness (default: thick)')
    parser.add_argument('--font', type=str, default=r"\footnotesize",
                        help='LaTeX font command (default: \\footnotesize)')
    parser.add_argument('--caption', type=str, default=None,
                        help='Custom caption (auto-generated if not provided)')
    parser.add_argument('--label', type=str, default=None,
                        help='Custom label (auto-generated if not provided)')
    parser.add_argument('--hide-wildcards', action='store_true',
                        help='Hide wildcard cells (show blank instead of *)')
    
    # Comparison mode
    parser.add_argument('--compare', type=str, nargs=2, metavar=('ALG1', 'ALG2'),
                        help='Compare two algorithms side-by-side (e.g., --compare greedy genetic_stochastic)')
    parser.add_argument('--run', type=int, default=1,
                        help='Run number for comparison mode (default: 1)')
    parser.add_argument('--subfig-width', type=str, default="0.48",
                        help='Subfigure width as fraction of textwidth (default: 0.48)')
    
    # Source bitmap options (for structured experiments)
    parser.add_argument('--show-source', action='store_true',
                        help='Also generate LaTeX for the original source bitmap (structured experiments only)')
    parser.add_argument('--source-only', action='store_true',
                        help='Only generate LaTeX for the source bitmap (structured experiments only)')
    parser.add_argument('--source-values', action='store_true',
                        help='Show 0/1 values in source bitmap (default: filled rectangles)')
    parser.add_argument('--source-cell-size', type=str, default="3.5mm",
                        help='Cell size for source bitmap (default: 3.5mm)')
    
    # Output options
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Output file path (default: stdout)')
    
    args = parser.parse_args()
    
    # Handle --list
    if args.list:
        list_available_experiments(args.list)
        return
    
    # Handle --demo (original example)
    if args.demo or (not args.file and not args.dir and not args.compare):
        run_demo()
        return
    
    # Parse opacity range
    try:
        min_op, max_op = map(float, args.opacity.split(':'))
    except ValueError:
        print(f"Invalid opacity format: {args.opacity}. Use min:max (e.g., 0.25:0.95)", file=sys.stderr)
        sys.exit(1)
    
    # Handle comparison mode
    if args.compare:
        if not args.dir:
            print("Comparison mode requires -d/--dir to specify experiment directory", file=sys.stderr)
            sys.exit(1)
        
        alg1, alg2 = args.compare
        pattern1 = f"run_{args.run}_{alg1}"
        pattern2 = f"run_{args.run}_{alg2}"
        
        files1 = find_experiment_files(args.dir, pattern1)
        files2 = find_experiment_files(args.dir, pattern2)
        
        if not files1:
            print(f"No files found matching pattern '{pattern1}' in {args.dir}", file=sys.stderr)
            sys.exit(1)
        if not files2:
            print(f"No files found matching pattern '{pattern2}' in {args.dir}", file=sys.stderr)
            sys.exit(1)
        
        try:
            exp_data_left, filepath_left = load_experiment_json(files1[0])
            exp_data_right, filepath_right = load_experiment_json(files2[0])
        except Exception as e:
            print(f"Error loading experiment files: {e}", file=sys.stderr)
            sys.exit(1)
        
        try:
            latex_output = latex_compare_algorithms(
                experiment_data_left=exp_data_left,
                experiment_data_right=exp_data_right,
                result_index=args.result_index,
                colors=args.colors,
                min_opacity=min_op,
                max_opacity=max_op,
                line_thickness=args.line_thickness,
                cell_min_size=args.cell_size,
                font_cmd=args.font,
                caption=args.caption,
                label=args.label,
                render_star_as_blank=args.hide_wildcards,
                shrink=args.shrink,
                subfig_width=args.subfig_width,
                experiment_filepath_left=filepath_left,
                experiment_filepath_right=filepath_right,
            )
        except Exception as e:
            print(f"Error generating comparison LaTeX: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Single file mode
        if args.file:
            filepath = args.file
        else:
            files = find_experiment_files(args.dir, args.pattern)
            if not files:
                print(f"No matching JSON files found in {args.dir}", file=sys.stderr)
                sys.exit(1)
            filepath = files[0]
            if len(files) > 1:
                print(f"Multiple files found, using: {filepath}", file=sys.stderr)
                print(f"Other options: {', '.join(files[1:5])}{'...' if len(files) > 5 else ''}", file=sys.stderr)
        
        try:
            experiment_data, filepath = load_experiment_json(filepath)
        except Exception as e:
            print(f"Error loading {filepath}: {e}", file=sys.stderr)
            sys.exit(1)
        
        try:
            # Check for source bitmap options
            input_data = experiment_data.get('input', {})
            structured_meta = input_data.get('structured_metadata', {})
            
            # If no structured_metadata in input, try loading from dataset file
            if not structured_meta and input_data.get('source') == 'dataset' and input_data.get('dataset_file'):
                tiles_data = load_tiles_from_input(input_data, filepath)
                structured_meta = input_data.get('structured_metadata', {})
            
            latex_parts = []
            
            # Generate source bitmap if requested
            if (args.show_source or args.source_only) and structured_meta:
                src_h = structured_meta.get('source_height')
                src_w = structured_meta.get('source_width')
                seed = structured_meta.get('seed')
                pattern = structured_meta.get('pattern', 'random')
                
                if src_h and src_w and seed is not None:
                    source_bitmap = regenerate_source_bitmap(src_h, src_w, seed, pattern)
                    source_caption = f"Original {pattern} source bitmap ({src_h}$\\times${src_w})"
                    source_label = f"fig:source-{pattern}-{seed}"
                    
                    source_latex = latex_source_bitmap(
                        bitmap=source_bitmap,
                        cell_min_size=args.source_cell_size,
                        caption=args.caption if args.source_only else source_caption,
                        label=args.label if args.source_only else source_label,
                        show_values=args.source_values,
                    )
                    latex_parts.append(source_latex)
                else:
                    print("Warning: Missing structured metadata for source bitmap generation", file=sys.stderr)
            elif (args.show_source or args.source_only) and not structured_meta:
                print("Warning: --show-source/--source-only requires structured experiment data", file=sys.stderr)
            
            # Generate algorithm result if not source-only
            if not args.source_only:
                result_latex = latex_from_experiment(
                    experiment_data=experiment_data,
                    result_index=args.result_index,
                    colors=args.colors,
                    min_opacity=min_op,
                    max_opacity=max_op,
                    line_thickness=args.line_thickness,
                    cell_min_size=args.cell_size,
                    font_cmd=args.font,
                    caption=args.caption,
                    label=args.label,
                    render_star_as_blank=args.hide_wildcards,
                    shrink=args.shrink,
                    experiment_filepath=filepath,
                )
                latex_parts.append(result_latex)
            
            latex_output = "\n\n".join(latex_parts)
        except Exception as e:
            print(f"Error generating LaTeX: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(latex_output)
        print(f"LaTeX written to {args.output}", file=sys.stderr)
    else:
        print(latex_output)


def run_demo():
    """Run the original demo example."""
    superstring = grid_from_text(r"""
    0 1 * 0 1 0
    1 0 1 1 0 1
    0 1 0 * 1 0
    1 0 1 1 0 1
    0 1 0 0 1 *
    1 0 1 1 0 1
    """)

    sub1 = grid_from_text(r"""
    0 1 0
    1 0 1
    """)

    sub2 = grid_from_text(r"""
    1 1
    0 1
    """)

    sub3 = grid_from_text(r"""
    0 0
    1 1
    """)

    print(
        latex_tikz_2d_rectangles_only(
            supergrid=superstring,
            substrings=[sub1, sub2, sub3],
            colors=["red", "blue", "green!60!black"],
            min_opacity=0.25,
            max_opacity=0.95,
            shrink="1.2pt",
            render_star_as_blank=False,
            caption="Rectangles shrunk slightly to reduce border overlap.",
            label="fig:rect-shrink",
        )
    )


# -------------------- Entry Point --------------------
if __name__ == "__main__":
    main()
