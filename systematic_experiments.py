#!/usr/bin/env python3
"""
MDSSP Systematic Experiments - Multi-Scale Testing

This script runs systematic experiments across different problem scales:
- Small scale (T=6-10): With CPLEX as baseline
- Medium scale (T=20-30): Heuristics comparison
- Large scale (T=50-60): Scalability testing
- Structured (reassembly): Test reconstruction from overlapping subarrays
- 2D Covering: Test cases from cycling substrings of a source string

All results are organized in the experiments/ directory.

Objective Types:
- 'square': Minimize max(width, height) - creates square-ish bounding boxes
- 'area': Minimize width × height - creates compact rectangular arrangements

Use --objective-type to override the default objective for all scales.

Alphabet Size:
- Default is 2 (binary: 0/1 values)
- Use --alphabet-size to specify larger alphabets (e.g., 4 for quaternary)
- Higher alphabets reduce overlap opportunities, affecting compression

Structured/Reassembly Experiments:
- Use --structured or --scales structured to run reassembly experiments
- Takes a source bitmap (e.g., 20×20), extracts overlapping subarrays
- Tests if algorithm can reconstruct the original area
- Random data: Area ≈ T*n*m (minimal compression)
- Structured data: Area ≈ source_area (high compression)
- Use --pattern to specify source bitmap pattern (random, checkerboard, etc.)

2D Covering Experiments:
- Use --2d-covering or --scales 2d_covering to run cycling string experiments
- Reads test cases from a file (default: 2d_covering.txt)
- Format: n m r L followed by string S of length L
- Generates L cycling substrings of length n*m, converts to 2D tiles
- Removes duplicate tiles before running algorithms
- Use --covering-file to specify a different input file
"""

import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import time
import sys
import csv
import random
import shutil

# ============================================================================
# 2D Covering Data Parsing
# ============================================================================

def parse_2d_covering_file(filepath):
    """
    Parse a 2d_covering.txt file containing multiple test cases.
    
    Format per test case:
        n m r L
        S
    
    Where:
        - n: tile height
        - m: tile width
        - r: some parameter (logged but not used)
        - L: length of string S
        - S: the string to generate cycling substrings from
    
    Returns:
        List of dictionaries with parsed test cases
    """
    test_cases = []
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    i = 0
    case_id = 0
    while i < len(lines):
        # Skip empty lines
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        
        # Parse header line: n m r L
        parts = line.split()
        if len(parts) < 4:
            i += 1
            continue
        
        try:
            n = int(parts[0])
            m = int(parts[1])
            r = int(parts[2])
            L = int(parts[3])
        except ValueError:
            i += 1
            continue
        
        # Next line(s) contain the string S
        # String may span multiple lines, collect until we have L characters
        i += 1
        S = ""
        while i < len(lines) and len(S) < L:
            S += lines[i].strip()
            i += 1
        
        if len(S) >= L:
            S = S[:L]  # Truncate to exactly L characters
            case_id += 1
            test_cases.append({
                'case_id': case_id,
                'n': n,
                'm': m,
                'r': r,
                'L': L,
                'S': S
            })
    
    return test_cases


def generate_tiles_from_cycling_string(S, n, m):
    """
    Generate tiles from a cycling string.
    
    Takes L cycling substrings of S, each of length n*m,
    and converts them to 2D arrays of size n×m.
    
    Removes duplicate tiles.
    
    Args:
        S: The source string
        n: Tile height
        m: Tile width
    
    Returns:
        Tuple of (unique_tiles, total_generated, duplicates_removed)
        where unique_tiles is a list of 2D arrays
    """
    L = len(S)
    tile_size = n * m
    
    if tile_size > L:
        raise ValueError(f"Tile size {n}x{m}={tile_size} is larger than string length {L}")
    
    # Generate all cycling substrings and convert to tiles
    seen_tiles = set()
    unique_tiles = []
    total_generated = 0
    
    for start in range(L):
        # Extract cycling substring of length n*m
        substring = ""
        for j in range(tile_size):
            substring += S[(start + j) % L]
        
        total_generated += 1
        
        # Check for duplicate (use tuple representation for hashing)
        if substring in seen_tiles:
            continue
        seen_tiles.add(substring)
        
        # Convert to 2D array
        tile = []
        for row in range(n):
            tile_row = []
            for col in range(m):
                char = substring[row * m + col]
                # Convert character to integer (assume '0'-'9' or use ord)
                if char.isdigit():
                    tile_row.append(int(char))
                else:
                    tile_row.append(ord(char) - ord('0'))
            tile.append(tile_row)
        unique_tiles.append(tile)
    
    duplicates_removed = total_generated - len(unique_tiles)
    return unique_tiles, total_generated, duplicates_removed


def parse_2d_covering_original_file(filepath):
    """
    Parse a 2d_covering_original format file.
    
    Filename format: n_m_r_L.txt (e.g., 3_3_1_102.txt)
    Content format: [string1], [string2], [string3], ...
    
    Args:
        filepath: Path to the file
    
    Returns:
        Dictionary with parsed data including n, m, r, L, and list of strings
    """
    path = Path(filepath)
    filename = path.stem  # e.g., "3_3_1_102"
    
    # Parse n, m, r, L from filename
    parts = filename.split('_')
    if len(parts) < 4:
        raise ValueError(f"Invalid filename format: {filename}. Expected n_m_r_L.txt")
    
    n = int(parts[0])
    m = int(parts[1])
    r = int(parts[2])
    L = int(parts[3])
    
    # Read and parse content
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Extract strings from [string1], [string2], ... format
    import re
    strings = re.findall(r'\[([01]+)\]', content)
    
    return {
        'filepath': str(filepath),
        'filename': filename,
        'n': n,
        'm': m,
        'r': r,
        'L': L,
        'strings': strings,
        'num_input_strings': len(strings)
    }


def generate_tiles_from_multiple_strings(strings, n, m):
    """
    Generate tiles from multiple strings using cycling substrings.
    
    For each string, for each position, takes cyclic substring of length n*m
    and converts to 2D tile. Removes duplicates across all strings.
    
    Args:
        strings: List of source strings
        n: Tile height
        m: Tile width
    
    Returns:
        Tuple of (unique_tiles, total_generated, duplicates_removed)
    """
    tile_size = n * m
    seen_tiles = set()
    unique_tiles = []
    total_generated = 0
    
    for S in strings:
        L = len(S)
        if tile_size > L:
            # Skip strings that are too short
            continue
        
        for start in range(L):
            # Extract cycling substring of length n*m
            substring = ""
            for j in range(tile_size):
                substring += S[(start + j) % L]
            
            total_generated += 1
            
            # Check for duplicate
            if substring in seen_tiles:
                continue
            seen_tiles.add(substring)
            
            # Convert to 2D array
            tile = []
            for row in range(n):
                tile_row = []
                for col in range(m):
                    char = substring[row * m + col]
                    if char.isdigit():
                        tile_row.append(int(char))
                    else:
                        tile_row.append(ord(char) - ord('0'))
                tile.append(tile_row)
            unique_tiles.append(tile)
    
    duplicates_removed = total_generated - len(unique_tiles)
    return unique_tiles, total_generated, duplicates_removed


def write_2d_covering_original_dataset_file(parsed_data, output_file):
    """
    Write a 2d_covering_original dataset to a JSON file for use with mdssp.
    
    Args:
        parsed_data: Dictionary from parse_2d_covering_original_file
        output_file: Output file path
    
    Returns:
        Tuple of (output_file, num_tiles, total_generated, duplicates_removed, num_input_strings)
    """
    n = parsed_data['n']
    m = parsed_data['m']
    strings = parsed_data['strings']
    
    tiles, total_generated, duplicates_removed = generate_tiles_from_multiple_strings(strings, n, m)
    
    # Determine alphabet size from the tiles
    max_val = 0
    for tile in tiles:
        for row in tile:
            if row:  # Check if row is not empty
                max_val = max(max_val, max(row))
    alphabet_size = max_val + 1 if max_val >= 0 else 2
    
    dataset = {
        "num_tiles": len(tiles),
        "tile_height": n,
        "tile_width": m,
        "alphabet_size": alphabet_size,
        "tiles": tiles,
        "2d_covering_original_metadata": {
            "filename": parsed_data['filename'],
            "n": n,
            "m": m,
            "r": parsed_data['r'],
            "L": parsed_data['L'],
            "num_input_strings": parsed_data['num_input_strings'],
            "total_generated": total_generated,
            "duplicates_removed": duplicates_removed,
            "unique_tiles": len(tiles)
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(dataset, f, indent=2)
    
    return output_file, len(tiles), total_generated, duplicates_removed, parsed_data['num_input_strings']


def write_2d_covering_dataset_file(test_case, output_file):
    """
    Write a 2d_covering dataset to a JSON file for use with mdssp.
    
    Args:
        test_case: Dictionary with test case data
        output_file: Output file path
    
    Returns:
        Tuple of (output_file, num_tiles, total_generated, duplicates_removed)
    """
    n = test_case['n']
    m = test_case['m']
    S = test_case['S']
    
    tiles, total_generated, duplicates_removed = generate_tiles_from_cycling_string(S, n, m)
    
    # Determine alphabet size from the tiles
    max_val = 0
    for tile in tiles:
        for row in tile:
            max_val = max(max_val, max(row))
    alphabet_size = max_val + 1
    
    dataset = {
        "num_tiles": len(tiles),
        "tile_height": n,
        "tile_width": m,
        "alphabet_size": alphabet_size,
        "tiles": tiles,
        "2d_covering_metadata": {
            "case_id": test_case['case_id'],
            "r": test_case['r'],
            "L": test_case['L'],
            "total_generated": total_generated,
            "duplicates_removed": duplicates_removed,
            "unique_tiles": len(tiles)
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(dataset, f, indent=2)
    
    return output_file, len(tiles), total_generated, duplicates_removed


# ============================================================================
# Structured/Reassembly Data Generation
# ============================================================================

def generate_source_bitmap(height, width, seed, pattern='random', alphabet_size=2):
    """
    Generate a source bitmap with values from 0 to alphabet_size-1.
    
    Args:
        height: Height of the bitmap
        width: Width of the bitmap
        seed: Random seed for reproducibility
        pattern: 'random' for random values, or a pattern name like 'checkerboard', 'stripes', 'icon'
        alphabet_size: Number of distinct values (2=binary, higher for larger alphabets)
    
    Returns:
        2D list of values in range [0, alphabet_size-1]
    """
    rng = random.Random(seed)
    
    if pattern == 'random':
        # Random values from the alphabet
        return [[rng.randint(0, alphabet_size - 1) for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'checkerboard':
        # Checkerboard pattern (uses modulo for higher alphabets)
        return [[(i + j) % alphabet_size for j in range(width)] for i in range(height)]
    
    elif pattern == 'stripes_h':
        # Horizontal stripes (uses modulo for higher alphabets)
        return [[i % alphabet_size for _ in range(width)] for i in range(height)]
    
    elif pattern == 'stripes_v':
        # Vertical stripes (uses modulo for higher alphabets)
        return [[j % alphabet_size for j in range(width)] for _ in range(height)]
    
    elif pattern == 'diagonal':
        # Diagonal pattern (uses modulo for higher alphabets)
        return [[(i + j) % alphabet_size for j in range(width)] for i in range(height)]
    
    elif pattern == 'blocks':
        # Block pattern (4x4 blocks, uses modulo for higher alphabets)
        block_size = 4
        return [[((i // block_size) + (j // block_size)) % alphabet_size
                 for j in range(width)] for i in range(height)]
    
    elif pattern == 'gradient':
        # Gradient pattern (probability decreases from top-left)
        # For binary: more 1s at top-left
        # For higher alphabets: higher values more likely at top-left
        def gradient_val(i, j):
            prob = 1 - (i + j) / (height + width)
            return int(prob * (alphabet_size - 1) + rng.random())
        return [[min(gradient_val(i, j), alphabet_size - 1) for j in range(width)] for i in range(height)]
    
    elif pattern == 'sparse':
        # Sparse pattern (~25% non-zero, random values for non-zero)
        return [[rng.randint(1, alphabet_size - 1) if rng.random() < 0.25 else 0 for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'dense':
        # Dense pattern (~75% non-zero, random values for non-zero)
        return [[rng.randint(1, alphabet_size - 1) if rng.random() < 0.75 else 0 for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'qrcode':
        # QR-code-like pattern with finder patterns and timing
        # Uses only binary (0/1) for the structured parts, but fills with full alphabet
        bitmap = [[0 for _ in range(width)] for _ in range(height)]
        
        # Helper to draw a finder pattern (7x7 with nested squares)
        def draw_finder(r0, c0):
            # Outer black square (7x7)
            for i in range(7):
                for j in range(7):
                    if r0 + i < height and c0 + j < width:
                        # Outer border
                        if i == 0 or i == 6 or j == 0 or j == 6:
                            bitmap[r0 + i][c0 + j] = alphabet_size - 1  # Use max value
                        # Inner white border
                        elif i == 1 or i == 5 or j == 1 or j == 5:
                            bitmap[r0 + i][c0 + j] = 0
                        # Center black square (3x3)
                        else:
                            bitmap[r0 + i][c0 + j] = alphabet_size - 1
        
        # Draw finder patterns in three corners
        draw_finder(0, 0)  # Top-left
        draw_finder(0, width - 7)  # Top-right
        draw_finder(height - 7, 0)  # Bottom-left
        
        # Timing patterns (alternating values)
        # Horizontal timing pattern (row 6)
        if height > 6:
            for j in range(8, width - 8):
                bitmap[6][j] = (j % alphabet_size)
        
        # Vertical timing pattern (column 6)
        if width > 6:
            for i in range(8, height - 8):
                bitmap[i][6] = (i % alphabet_size)
        
        # Fill rest with pseudo-random data based on seed
        for i in range(height):
            for j in range(width):
                # Skip finder pattern areas and timing patterns
                in_finder = ((i < 8 and j < 8) or  # Top-left
                            (i < 8 and j >= width - 8) or  # Top-right
                            (i >= height - 8 and j < 8))  # Bottom-left
                in_timing = (i == 6 and 8 <= j < width - 8) or (j == 6 and 8 <= i < height - 8)
                
                if not in_finder and not in_timing:
                    bitmap[i][j] = rng.randint(0, alphabet_size - 1)
        
        return bitmap
    
    else:
        # Default to random
        return [[rng.randint(0, alphabet_size - 1) for _ in range(width)] for _ in range(height)]


def extract_subarrays(bitmap, num_tiles, tile_height, tile_width, seed, allow_overlap=True):
    """
    Extract random subarrays from a bitmap.
    
    Args:
        bitmap: 2D source bitmap
        num_tiles: Number of tiles to extract
        tile_height: Height of each tile (n)
        tile_width: Width of each tile (m)
        seed: Random seed for reproducibility
        allow_overlap: If True, tiles can overlap in the source
    
    Returns:
        List of 2D tiles (each is n×m)
    """
    rng = random.Random(seed)
    
    src_height = len(bitmap)
    src_width = len(bitmap[0]) if bitmap else 0
    
    # Valid range for top-left corner of extractions
    max_row = src_height - tile_height
    max_col = src_width - tile_width
    
    if max_row < 0 or max_col < 0:
        raise ValueError(f"Tile size ({tile_height}×{tile_width}) is larger than source ({src_height}×{src_width})")
    
    tiles = []
    for _ in range(num_tiles):
        # Random top-left corner
        row = rng.randint(0, max_row)
        col = rng.randint(0, max_col)
        
        # Extract the subarray
        tile = [[bitmap[row + i][col + j] for j in range(tile_width)] 
                for i in range(tile_height)]
        tiles.append(tile)
    
    return tiles


def extract_subarrays_full_coverage(bitmap, tile_height, tile_width, seed):
    """
    Extract subarrays from a bitmap ensuring 100% coverage of all positions.
    
    Uses a greedy approach: randomly order all positions, then keep only tiles
    that cover at least one previously uncovered pixel. This guarantees 100%
    coverage while minimizing redundant tiles.
    
    Args:
        bitmap: 2D source bitmap
        tile_height: Height of each tile (n)
        tile_width: Width of each tile (m)
        seed: Random seed (used for shuffling order)
    
    Returns:
        List of 2D tiles (each is n×m), covering all source positions with minimal redundancy
    """
    rng = random.Random(seed)
    
    src_height = len(bitmap)
    src_width = len(bitmap[0]) if bitmap else 0
    
    # Valid range for top-left corner of extractions
    max_row = src_height - tile_height
    max_col = src_width - tile_width
    
    if max_row < 0 or max_col < 0:
        raise ValueError(f"Tile size ({tile_height}×{tile_width}) is larger than source ({src_height}×{src_width})")
    
    # Generate all valid positions and shuffle
    positions = [(row, col) for row in range(max_row + 1) for col in range(max_col + 1)]
    rng.shuffle(positions)
    
    # Track which pixels are covered
    covered = [[False] * src_width for _ in range(src_height)]
    total_pixels = src_height * src_width
    covered_count = 0
    
    # Greedily select tiles that add new coverage
    tiles = []
    selected_positions = []
    
    for row, col in positions:
        # Check if this tile covers any new pixels
        adds_coverage = False
        for i in range(tile_height):
            for j in range(tile_width):
                if not covered[row + i][col + j]:
                    adds_coverage = True
                    break
            if adds_coverage:
                break
        
        if adds_coverage:
            # Extract the tile
            tile = [[bitmap[row + i][col + j] for j in range(tile_width)] 
                    for i in range(tile_height)]
            tiles.append(tile)
            selected_positions.append((row, col))
            
            # Mark pixels as covered
            for i in range(tile_height):
                for j in range(tile_width):
                    if not covered[row + i][col + j]:
                        covered[row + i][col + j] = True
                        covered_count += 1
            
            # Early exit if fully covered
            if covered_count >= total_pixels:
                break
    
    return tiles


def generate_structured_dataset(source_height, source_width, num_tiles, tile_height, tile_width, 
                                 seed, pattern='random', output_file=None, alphabet_size=2,
                                 full_coverage=False):
    """
    Generate a structured dataset by extracting subarrays from a source bitmap.
    
    Args:
        source_height: Height of the source bitmap
        source_width: Width of the source bitmap
        num_tiles: Number of tiles to extract (ignored if full_coverage=True)
        tile_height: Height of each tile
        tile_width: Width of each tile
        seed: Random seed
        pattern: Pattern for source bitmap generation
        output_file: Optional file to write the dataset JSON
        alphabet_size: Number of distinct values (2=binary, higher for larger alphabets)
        full_coverage: If True, extract tiles at ALL positions for 100% coverage
    
    Returns:
        Dictionary with dataset and metadata including optimal_area
    """
    # Generate source bitmap
    bitmap = generate_source_bitmap(source_height, source_width, seed, pattern, alphabet_size)
    
    # Extract tiles (use seed+1000 to ensure different random choices than bitmap)
    if full_coverage:
        tiles = extract_subarrays_full_coverage(bitmap, tile_height, tile_width, seed + 1000)
    else:
        tiles = extract_subarrays(bitmap, num_tiles, tile_height, tile_width, seed + 1000)
    
    # Build dataset structure
    dataset = {
        "num_tiles": len(tiles),
        "tile_height": tile_height,
        "tile_width": tile_width,
        "alphabet_size": alphabet_size,
        "tiles": tiles,
        # Metadata for structured experiments
        "structured_metadata": {
            "source_height": source_height,
            "source_width": source_width,
            "optimal_area": source_height * source_width,  # Best possible reconstruction
            "pattern": pattern,
            "alphabet_size": alphabet_size,
            "seed": seed,
            "full_coverage": full_coverage
        }
    }
    
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(dataset, f, indent=2)
    
    return dataset


def write_structured_dataset_file(source_height, source_width, num_tiles, tile_height, tile_width,
                                   seed, pattern, output_file, alphabet_size=2, full_coverage=False):
    """
    Write a structured dataset to a JSON file for use with mdssp.
    
    Args:
        source_height, source_width: Dimensions of source bitmap
        num_tiles: Number of tiles (ignored if full_coverage=True)
        tile_height, tile_width: Tile dimensions
        seed: Random seed
        pattern: Pattern for bitmap generation
        output_file: Output file path
        alphabet_size: Number of distinct values
        full_coverage: If True, extract ALL tiles for 100% coverage
    
    Returns the path to the written file and the optimal_area metric.
    """
    # Warn about large alphabet sizes that may cause UTF-8 issues in C++ JSON output
    if alphabet_size > 127:
        print(f"    Warning: alphabet_size={alphabet_size} may cause UTF-8 encoding issues in C++ output")
    
    dataset = generate_structured_dataset(
        source_height, source_width, num_tiles, tile_height, tile_width,
        seed, pattern, output_file, alphabet_size, full_coverage
    )
    return output_file, dataset["structured_metadata"]["optimal_area"], dataset["num_tiles"]


# ============================================================================
# Experiment configurations
# ============================================================================
EXPERIMENTS = {
    '2d_covering_original': {
        'data_dir': '2d_covering_dataset',  # Directory with n_m_r_L.txt files
        'algorithms': ['genetic_greedy', 'genetic_stochastic'],
        'pop_size': 256,
        'generations': 512,
        'beam_width': 20,
        'sa_max_iter': 20000,
        'cplex_time_limit': 600,
        'objective_types': ['area', 'square'],  # Run both objective types
        'alphabet_size': 2,
        'runs': 1,
        'description': '2D Covering Original: Multiple input strings parsed from [str1], [str2], ... format'
    },
    '2d_covering': {
        'data_file': '2d_covering.txt',  # Input file with test cases
        'algorithms': ['genetic_greedy', 'genetic_stochastic'],
        'pop_size': 256,
        'generations': 512,
        'beam_width': 20,
        'sa_max_iter': 20000,
        'cplex_time_limit': 600,
        'objective_types': ['area'],
        'alphabet_size': 2,  # 2=binary, higher for larger alphabets (auto-detected from data)
        'runs': 1,  # Single run per test case since data is fixed
        'description': '2D Covering: Test cases from cycling substrings of a source string'
    },
    '1d': {
        'tiles': [10, 20, 50, 100, 200, 300],
        'tile_size': [(1, 2), (1, 4), (1, 8)],
        'runs': 10,
        'algorithms': ['merge_greedy', 'greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'beam_search', 'simulated_annealing'],
        'pop_size': 150,
        'generations': 300,
        'beam_width': 10,
        'sa_max_iter': 10000,
        'cplex_time_limit': 2000,  # CPLEX time limit in seconds
        'objective_type': 'area',  # 'square' or 'area'
        'alphabet_size': 2,  # 2=binary, higher for larger alphabets
    },
    'structured': {
        # Structured/Reassembly experiment:
        # - Load pre-generated datasets from experiment_structural/datasets/
        # - Datasets have 100% pixel coverage with minimal tiles (greedy random sampling)
        # - Test if algorithm can reconstruct original (Area=400 for 20x20)
        # - Random data: Area ≈ high (minimal compression)
        # - Structured data: Area ≈ source_area (high compression/perfect reconstruction)
        # 
        # Pre-generate datasets using: python generate_structured_datasets.py
        # Dataset path: experiment_structural/datasets/src{H}x{W}/{pattern}/dataset.json
        #
        # Examples with 3x3 tiles (greedy 100% coverage):
        #   14x14 → ~25-35 tiles (from 144 possible)
        #   36x36 → ~150-200 tiles (from 1156 possible)
        #   64x64 → ~500-600 tiles (from 3844 possible)
        'source_sizes': [(14, 14), (36, 36), (64, 64)],  # (height, width) of source bitmap
        'tile_size': [(3, 3)],  # (n, m) tile extraction size
        'use_pregenerated_datasets': True,  # Load from datasets/ folder
        'datasets_dir': 'experiment_structural/datasets',  # Pre-generated datasets location
        'full_coverage': True,  # Fallback: generate with 100% coverage if dataset not found
        'patterns': ['qrcode', 'random', 'checkerboard', 'stripes_h', 'stripes_v', 'diagonal', 'blocks', 'gradient', 'sparse', 'dense'],  # List of patterns to test
        'structured': True,  # Flag indicating structured data generation
        'runs': 1,
        'algorithms': ['merge_greedy', 'greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'beam_search'],
        'pop_size': 150,
        'generations': 300,
        'beam_width': 15,
        'sa_max_iter': 15000,
        'cplex_time_limit': 600,
        'objective_type': 'square',  # 'square' or 'area'
        'alphabet_size': 2,  # 2=binary, higher for larger alphabets
        'description': 'Structured/Reassembly: Can algorithm reconstruct source bitmap from overlapping subarray extractions?'
    },
    'small': {
        'tiles': [6, 8, 10],
        'tile_size': [(3, 3), (2, 4), (5, 5), (4, 6)],
        'runs': 10,
        'algorithms': ['cplex', 'merge_greedy', 'greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'beam_search'],
        'pop_size': 100,
        'generations': 200,
        'beam_width': 10,
        'sa_max_iter': 10000,
        'cplex_time_limit': 300,  # CPLEX time limit in seconds
        'objective_type': 'square',  # 'square' or 'area'
        'alphabet_size': 2,  # 2=binary, higher for larger alphabets
        'description': 'Small scale with CPLEX baseline'
    },
    'medium': {
        'tiles': [20, 30, 50],
        'tile_size': [(3, 3), (2, 4), (5, 5), (4, 6)],
        'runs': 10,
        'algorithms': ['merge_greedy', 'greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'beam_search'],
        'pop_size': 150,
        'generations': 300,
        'beam_width': 15,
        'sa_max_iter': 15000,
        'objective_type': 'square',  # 'square' or 'area'
        'alphabet_size': 2,  # 2=binary, higher for larger alphabets
        'description': 'Medium scale heuristics comparison'
    },
    'large': {
        'tiles': [60, 80, 100],
        'tile_size': [(3, 3), (2, 4)],
        'runs': 10,
        'algorithms': ['merge_greedy', 'greedy', 'stochastic_greedy', 'genetic_greedy', 'genetic_stochastic', 'beam_search'],
        'pop_size': 200,
        'generations': 400,
        'beam_width': 20,
        'sa_max_iter': 20000,
        'objective_type': 'square',  # 'square' or 'area'
        'alphabet_size': 2,  # 2=binary, higher for larger alphabets
        'description': 'Large scale scalability testing'
    }
}

def run_single_experiment(algorithm, tiles, n, m, seed, output_file, pop_size=None, generations=None, objective_type=None, cplex_time_limit=None, beam_width=None, sa_max_iter=None, dataset_file=None, alphabet_size=2):
    """Run a single experiment and return results.
    
    Args:
        algorithm: Algorithm to run
        tiles: Number of tiles (used for random generation if dataset_file is None)
        n: Tile height
        m: Tile width
        seed: Random seed
        output_file: Output JSON file path
        pop_size: Population size for genetic algorithms
        generations: Number of generations for genetic algorithms
        objective_type: 'square' or 'area'
        cplex_time_limit: Time limit for CPLEX
        beam_width: Beam width for beam search
        sa_max_iter: Max iterations for simulated annealing
        dataset_file: Optional path to a pre-generated dataset JSON file
        alphabet_size: Alphabet size (2=binary, higher for larger alphabets)
    """

    if algorithm == "merge_greedy_py":
        cmd = [
            sys.executable,  # python
            "baseline_merge_greedy_ssp.py",
            "-T", str(tiles),
            "-n", str(n),
            "-m", str(m),
            "-s", str(seed),
            "-o", str(output_file),
        ]
        if objective_type:
            cmd.extend(["--objective-type", objective_type])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1000000)
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "timeout"}

        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip() or "python baseline failed"}

        # Load JSON written by the baseline and return in your usual shape
        try:
            with open(output_file, "r") as f:
                solution_data = json.load(f)
            r0 = solution_data["results"][0]
            return {
                'success': True,
                'status': r0.get('status'),
                'objective': r0.get('objective'),
                'runtime': r0.get('runtime_seconds'),
                'bbox_width': r0.get('bbox_width'),
                'bbox_height': r0.get('bbox_height'),
                'num_tiles': r0.get('num_tiles_placed'),
                'total_crossovers': None,
                'crossovers_needing_completion': None,
                'total_tiles_completed': None,
                'iterations': None,
                'states_explored': None,
                'improvements_found': None,
                'solution': solution_data,
            }

        except Exception as e:
            return {"success": False, "error": f"Parse failed (python baseline JSON): {e}"}

    # Build command based on whether we have a pre-generated dataset file
    if dataset_file:
        # Use dataset file instead of random generation
        cmd = [
            "./mdssp",
            "-a", algorithm,
            "-d", str(dataset_file),  # Use -d for dataset file
            "-o", output_file
        ]
    else:
        # Random generation mode
        cmd = [
            "./mdssp",
            "-a", algorithm,
            "-T", str(tiles),
            "-n", str(n),
            "-m", str(m),
            "-s", str(seed),
            "-o", output_file
        ]
        # Add alphabet size for non-dataset mode
        if alphabet_size and alphabet_size != 2:
            cmd.extend(["--alphabet-size", str(alphabet_size)])
    
    if objective_type:
        cmd.extend(["--objective-type", objective_type])
     
    if algorithm == 'cplex' and cplex_time_limit:
        cmd.extend(["--time-limit", str(cplex_time_limit)])
    
    if algorithm in ['genetic_greedy', 'genetic_stochastic']:
        if pop_size:
            cmd.extend(["--pop-size", str(pop_size)])
        if generations:
            cmd.extend(["--generations", str(generations)])
    
    if algorithm == 'beam_search' and beam_width:
        cmd.extend(["--beam-width", str(beam_width)])
    
    if algorithm == 'simulated_annealing' and sa_max_iter:
        cmd.extend(["--sa-max-iter", str(sa_max_iter)])
    
    subprocess_timeout = 10000    # Large timeout to let CPLEX run as long as needed
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=  subprocess_timeout)
        
        # Parse output
        output = result.stdout
        objective = None
        runtime = None
        bbox_width = None
        bbox_height = None
        num_tiles = None
        status = None
        total_crossovers = None
        crossovers_needing_completion = None
        total_tiles_completed = None
        # Search algorithm stats
        iterations = None
        states_explored = None
        improvements_found = None
        
        for line in output.split('\n'):
            if 'Status:' in line and 'Algorithm Results' not in line:
                try:
                    status = line.split(':')[1].strip()
                except (ValueError, IndexError):
                    pass
            elif 'Objective (L):' in line:
                try:
                    objective = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Runtime:' in line:
                try:
                    runtime = float(line.split(':')[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif 'Bounding Box:' in line:
                try:
                    parts = line.split(':')[1].strip().split('×')
                    bbox_width = int(parts[0].strip())
                    bbox_height = int(parts[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Placements:' in line:
                try:
                    num_tiles = int(line.split(':')[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            elif 'Total crossovers:' in line:
                try:
                    total_crossovers = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Crossovers needing greedy completion:' in line:
                try:
                    crossovers_needing_completion = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Total tiles placed by greedy completion:' in line:
                try:
                    total_tiles_completed = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'States explored:' in line:
                try:
                    states_explored = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
            elif 'Improvements found:' in line:
                try:
                    improvements_found = int(line.split(':')[1].strip())
                except (ValueError, IndexError):
                    pass
        
        # Load JSON solution if available
        solution_data = None
        if Path(output_file).exists():
            try:
                with open(output_file, 'r') as f:
                    solution_data = json.load(f)
                    
                # Check for error status in JSON (like "Model too large")
                if solution_data and 'results' in solution_data:
                    result_obj = solution_data['results'][0]
                    
                    # If there's an error status, return it immediately
                    if 'error' in result_obj or result_obj.get('status') in ['Model too large (too many origin variables)']:
                        error_msg = result_obj.get('error', result_obj.get('status', 'Unknown error'))
                        return {'success': False, 'error': error_msg}
                    
                    # Extract crossover stats from JSON if available
                    if 'total_crossovers' in result_obj:
                        total_crossovers = result_obj['total_crossovers']
                    if 'crossovers_needing_completion' in result_obj:
                        crossovers_needing_completion = result_obj['crossovers_needing_completion']
                    if 'total_tiles_completed' in result_obj:
                        total_tiles_completed = result_obj['total_tiles_completed']
                    
                    # Extract search algorithm stats from JSON if available
                    if 'iterations' in result_obj:
                        iterations = result_obj['iterations']
                    if 'states_explored' in result_obj:
                        states_explored = result_obj['states_explored']
                    if 'improvements_found' in result_obj:
                        improvements_found = result_obj['improvements_found']
                        
            except Exception as e:
                print(f"    Warning: Could not load solution JSON: {e}")
        
        # Check if we got valid results
        if result.returncode != 0:
            # Command failed, check stderr for error message
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            return {'success': False, 'error': f'Command failed with code {result.returncode}: {error_msg}'}
        
        # Even with returncode 0, check if we parsed essential fields
        if objective is None or runtime is None:
            # Try to get error from stderr or stdout
            error_info = result.stderr.strip() if result.stderr else result.stdout[-500:] if result.stdout else "No output"
            return {'success': False, 'error': f'Parse failed: {error_info}'}
        
        return {
            'success': True,
            'status': status,
            'objective': objective,
            'runtime': runtime,
            'bbox_width': bbox_width,
            'bbox_height': bbox_height,
            'num_tiles': num_tiles,
            'total_crossovers': total_crossovers,
            'crossovers_needing_completion': crossovers_needing_completion,
            'total_tiles_completed': total_tiles_completed,
            'iterations': iterations,
            'states_explored': states_explored,
            'improvements_found': improvements_found,
            'solution': solution_data
        }
    
    except subprocess.TimeoutExpired:
        # Even on timeout, CPLEX might have written a feasible solution to the file
        # Check if the JSON file exists and has valid results
        if Path(output_file).exists():
            try:
                with open(output_file, 'r') as f:
                    solution_data = json.load(f)
                    
                if solution_data and 'results' in solution_data and len(solution_data['results']) > 0:
                    result_obj = solution_data['results'][0]
                    
                    # Check if we have a valid solution (even if just feasible)
                    if 'objective' in result_obj and 'runtime_seconds' in result_obj:
                        return {
                            'success': True,
                            'status': result_obj.get('status', 'timeout'),
                            'objective': result_obj.get('objective'),
                            'runtime': result_obj.get('runtime_seconds'),
                            'bbox_width': result_obj.get('bbox_width'),
                            'bbox_height': result_obj.get('bbox_height'),
                            'num_tiles': result_obj.get('num_tiles_placed'),
                            'total_crossovers': result_obj.get('total_crossovers'),
                            'crossovers_needing_completion': result_obj.get('crossovers_needing_completion'),
                            'total_tiles_completed': result_obj.get('total_tiles_completed'),
                            'iterations': result_obj.get('iterations'),
                            'states_explored': result_obj.get('states_explored'),
                            'improvements_found': result_obj.get('improvements_found'),
                            'solution': solution_data
                        }
            except Exception as e:
                print(f"    Warning: Timeout occurred but couldn't parse output file: {e}")
        
        return {'success': False, 'error': 'timeout'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def is_experiment_completed(output_file):
    """Check if an experiment has already been completed or marked as failed."""
    if not Path(output_file).exists():
        return False
    
    try:
        with open(output_file, 'r') as f:
            data = json.load(f)
            # Check if the JSON file has valid results
            if 'results' in data and len(data['results']) > 0:
                result = data['results'][0]
                # Valid completed run has objective and runtime
                if 'objective' in result and 'runtime_seconds' in result:
                    return True
                # Failed/error marker also counts as "completed" (don't retry)
                if result.get('status') in ['failed', 'parse_failed', 'error']:
                    return True
    except:
        return False
    
    return False

def run_experiment_suite(scale, config, base_seed, output_dir, resume=True):
    """Run all experiments for a given scale."""
    print(f"\n{'='*80}")
    print(f"RUNNING {scale.upper()} SCALE EXPERIMENTS")
    print(f"{'='*80}")
    if 'description' in config:
        print(f"Description: {config['description']}")
    print(f"Tile counts: {config['tiles']}")
    print(f"Tile sizes: {config['tile_size']}")
    print(f"Algorithms: {config['algorithms']}")
    print(f"Objective type: {config.get('objective_type', 'square')} ({'max(H,W)' if config.get('objective_type', 'square') == 'square' else 'H×W'})")
    
    alphabet_size = config.get('alphabet_size', 2)
    print(f"Alphabet size: {alphabet_size}")
    if alphabet_size > 127:
        print(f"WARNING: alphabet_size > 127 may cause UTF-8 encoding issues in C++ JSON output!")
    
    print(f"Runs per configuration: {config['runs']}")
    if resume:
        print(f"Resume mode: ON (will skip completed experiments)")
    print()
    
    scale_dir = output_dir / scale
    scale_dir.mkdir(exist_ok=True, parents=True)
    
    all_results = []
    best_results = {}
    
    # Load existing results if resuming
    completed_count = 0
    skipped_count = 0
    
    for tiles in config['tiles']:
        for (n, m) in config['tile_size']:
            alphabet_size = config.get('alphabet_size', 2)
            exp_name = f"T{tiles}_n{n}_m{m}"
            if alphabet_size != 2:
                exp_name += f"_a{alphabet_size}"
            print(f"\n--- Experiment: {exp_name} ---")
            
            
            exp_dir = scale_dir / exp_name
            exp_dir.mkdir(exist_ok=True)
            
            for run in range(config['runs']):
                seed = base_seed + run * 100
                print(f"\nRun {run + 1}/{config['runs']} (seed={seed})")
                
                for algo in config['algorithms']:
                    algo_name = algo.replace('_', ' ').title()
                    
                    output_filename = f"run_{run+1}_{algo}.json"
                    if alphabet_size != 2:
                        output_filename = f"run_{run+1}_{algo}_a{alphabet_size}.json"
                    output_file = exp_dir / output_filename
                    
                    # Check if already completed
                    if resume and is_experiment_completed(output_file):
                        skipped_count += 1
                        
                        # Load the existing result
                        try:
                            with open(output_file, 'r') as f:
                                solution_data = json.load(f)
                                if 'results' in solution_data and len(solution_data['results']) > 0:
                                    result_obj = solution_data['results'][0]
                                    
                                    # Check if this was a failed run
                                    if result_obj.get('status') in ['failed', 'parse_failed', 'error']:
                                        print(f"  [{algo}] ⊙ Previously failed (skipped)", flush=True)
                                        continue
                                    
                                    result_entry = {
                                        'scale': scale,
                                        'tiles': tiles,
                                        'n': n,
                                        'm': m,
                                        'run': run + 1,
                                        'seed': seed,
                                        'algorithm': algo,
                                        'objective_type': config.get('objective_type', 'square'),
                                        'status': result_obj.get('status'),
                                        'objective': result_obj.get('objective'),
                                        'runtime': result_obj.get('runtime_seconds'),
                                        'bbox_width': result_obj.get('bbox_width'),
                                        'bbox_height': result_obj.get('bbox_height'),
                                        'num_tiles': result_obj.get('num_tiles_placed')
                                    }
                                    
                                    # Add genetic algorithm specific stats
                                    if 'total_crossovers' in result_obj:
                                        result_entry['total_crossovers'] = result_obj['total_crossovers']
                                        result_entry['crossovers_needing_completion'] = result_obj.get('crossovers_needing_completion')
                                        result_entry['total_tiles_completed'] = result_obj.get('total_tiles_completed')
                                    
                                    # Add search algorithm specific stats
                                    if 'iterations' in result_obj:
                                        result_entry['iterations'] = result_obj['iterations']
                                    if 'states_explored' in result_obj:
                                        result_entry['states_explored'] = result_obj['states_explored']
                                    if 'improvements_found' in result_obj:
                                        result_entry['improvements_found'] = result_obj['improvements_found']
                                    
                                    all_results.append(result_entry)
                                    
                                    print(f"  [{algo}] ⊙ Already completed (skipped), objective = {result_entry['objective']}", flush=True)
                                    
                                    # Track best result (only if we have a valid objective)
                                    if result_entry['objective'] is not None:
                                        key = f"{exp_name}_{algo}"
                                        if key not in best_results or (best_results[key]['objective'] is not None and result_entry['objective'] < best_results[key]['objective']):
                                            best_results[key] = result_entry.copy()
                                            best_results[key]['solution'] = solution_data
                        except Exception as e:
                            print(f"  [{algo}] ⊙ Previously completed (warning: couldn't load: {e})", flush=True)
                        
                        continue
                    
                    print(f"  [{algo}] ", end='', flush=True)
                    
                    result = run_single_experiment(
                        algo, tiles, n, m, seed, str(output_file),
                        config.get('pop_size'), config.get('generations'),
                        config.get('objective_type'), config.get('cplex_time_limit'),
                        config.get('beam_width'), config.get('sa_max_iter'),
                        alphabet_size=config.get('alphabet_size', 2)
                    )
                    
                    completed_count += 1
                    
                    if result['success']:
                        obj = result['objective']
                        runtime = result['runtime']
                        status = result.get('status')
                        
                        # Check if parsing failed - handle missing output file gracefully
                        if obj is None or runtime is None:
                            if not Path(output_file).exists():
                                print(f"✗ No output file (process may have been killed before completing)")
                                result['success'] = False
                                result['error'] = 'no_output_file'
                            # Otherwise parsing succeeded but got None values - will be handled below
                        
                        if obj is not None and runtime is not None:
                            # Show status indicator for CPLEX feasible (non-optimal) solutions
                            status_marker = "✓"
                            if status == "feasible":
                                status_marker = "≈"  # Approximate/feasible but not optimal
                            
                            print(f"{status_marker} Obj={obj}, Time={runtime:.3f}s", end='')
                            
                            # Add crossover stats if available
                            if result['total_crossovers'] and result['crossovers_needing_completion'] is not None:
                                completion_rate = result['crossovers_needing_completion'] / result['total_crossovers'] * 100
                                print(f", Completion={completion_rate:.1f}%", end='')
                            
                            print()
                            
                            # Store result
                            result_entry = {
                                'scale': scale,
                                'tiles': tiles,
                                'n': n,
                                'm': m,
                                'run': run + 1,
                                'seed': seed,
                                'algorithm': algo,
                                'objective_type': config.get('objective_type', 'square'),
                                'status': status,
                                'objective': obj,
                                'runtime': runtime,
                                'bbox_width': result['bbox_width'],
                                'bbox_height': result['bbox_height'],
                                'num_tiles': result['num_tiles']
                            }
                            
                            # Add genetic algorithm specific stats
                            if result.get('total_crossovers') is not None:
                                result_entry['total_crossovers'] = result['total_crossovers']
                                result_entry['crossovers_needing_completion'] = result.get('crossovers_needing_completion')
                                result_entry['total_tiles_completed'] = result.get('total_tiles_completed')
                            
                            # Add search algorithm specific stats
                            if result.get('iterations') is not None:
                                result_entry['iterations'] = result['iterations']
                            if result.get('states_explored') is not None:
                                result_entry['states_explored'] = result['states_explored']
                            if result.get('improvements_found') is not None:
                                result_entry['improvements_found'] = result['improvements_found']
                            
                            all_results.append(result_entry)
                            
                            # Track best result
                            key = f"{exp_name}_{algo}"
                            if key not in best_results or obj < best_results[key]['objective']:
                                best_results[key] = result_entry.copy()
                                best_results[key]['solution'] = result['solution']
                        else:
                            # This shouldn't happen now with improved error detection
                            print("✗ Parse failed (unexpected)")
                            # Save failure marker so we don't retry this indefinitely
                            failure_data = {
                                'input': {
                                    'T': tiles,
                                    'n': n,
                                    'm': m,
                                    'seed': seed,
                                    'objective_type': config.get('objective_type', 'square')
                                },
                                'results': [{
                                    'algorithm': algo,
                                    'status': 'parse_failed',
                                    'error': 'Failed to parse algorithm output (unexpected)'
                                }]
                            }
                            with open(output_file, 'w') as f:
                                json.dump(failure_data, f, indent=2)
                    else:
                        error_msg = result.get('error', 'unknown error')
                        # Truncate very long error messages for display
                        if len(error_msg) > 200:
                            error_msg = error_msg[:200] + "..."
                        print(f"✗ {error_msg}")
                        # Save failure marker
                        failure_data = {
                            'input': {
                                'T': tiles,
                                'n': n,
                                'm': m,
                                'seed': seed,
                                'objective_type': config.get('objective_type', 'square')
                            },
                            'results': [{
                                'algorithm': algo,
                                'status': 'failed',
                                'error': error_msg
                            }]
                        }
                        with open(output_file, 'w') as f:
                            json.dump(failure_data, f, indent=2)
            
            # Save experiment results
            exp_results = [r for r in all_results if r['tiles'] == tiles and r['n'] == n and r['m'] == m]
            with open(exp_dir / 'all_results.json', 'w') as f:
                json.dump(exp_results, f, indent=2)
            
            # Save best solutions for this experiment
            exp_best = {k: v for k, v in best_results.items() if k.startswith(exp_name)}
            for key, result in exp_best.items():
                algo = key.split('_')[-1]
                if result.get('solution'):
                    with open(exp_dir / f'best_{algo}_solution.json', 'w') as f:
                        json.dump(result['solution'], f, indent=2)
    
    # Save scale-wide results
    with open(scale_dir / 'all_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    with open(scale_dir / 'best_results.json', 'w') as f:
        # Remove solution data for summary file
        best_summary = {k: {kk: vv for kk, vv in v.items() if kk != 'solution'} 
                       for k, v in best_results.items()}
        json.dump(best_summary, f, indent=2)
    
    # Write results to CSV
    write_results_to_csv(all_results, scale_dir / 'all_results.csv')
    
    # Calculate summary statistics
    summary = calculate_summary_statistics(all_results)
    with open(scale_dir / 'summary_statistics.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Write summary statistics to CSV
    write_summary_to_csv(summary, scale_dir / 'summary_statistics.csv')
    
    print(f"\n{'='*80}")
    print(f"✓ {scale.upper()} scale experiments completed")
    print(f"  Total runs: {len(all_results)}")
    if resume:
        print(f"  New experiments run: {completed_count}")
        print(f"  Skipped (already done): {skipped_count}")
    print(f"  Results saved to: {scale_dir}")
    print(f"  CSV files: all_results.csv, summary_statistics.csv")
    print(f"{'='*80}")
    
    return all_results, best_results, summary


def run_2d_covering_experiment_suite(scale, config, base_seed, output_dir, resume=True):
    """
    Run 2D covering experiments from a data file.
    
    This reads test cases from 2d_covering.txt, generates tiles from cycling
    substrings, removes duplicates, and tests algorithms on each case.
    Runs experiments for both 'area' and 'square' objective types.
    
    Args:
        scale: Scale name (e.g., '2d_covering')
        config: Experiment configuration
        base_seed: Base random seed (used for stochastic algorithms)
        output_dir: Output directory
        resume: Whether to skip completed experiments
    """
    data_file = config.get('data_file', '2d_covering.txt')
    
    # Get objective types to run (default to both if 'objective_types' is set, otherwise use single 'objective_type')
    objective_types = config.get('objective_types', [config.get('objective_type', 'area')])
    if isinstance(objective_types, str):
        objective_types = [objective_types]
    
    print(f"\n{'='*80}")
    print(f"RUNNING {scale.upper()} SCALE EXPERIMENTS (2D Covering)")
    print(f"{'='*80}")
    if 'description' in config:
        print(f"Description: {config['description']}")
    print(f"Data file: {data_file}")
    print(f"Algorithms: {config['algorithms']}")
    print(f"Objective types: {objective_types}")
    print(f"Runs per configuration: {config.get('runs', 1)}")
    if resume:
        print(f"Resume mode: ON (will skip completed experiments)")
    print()
    
    # Parse the data file
    if not Path(data_file).exists():
        print(f"ERROR: Data file not found: {data_file}")
        return [], {}, {}
    
    test_cases = parse_2d_covering_file(data_file)
    print(f"Loaded {len(test_cases)} test cases from {data_file}")
    print()
    
    scale_dir = output_dir / scale
    scale_dir.mkdir(exist_ok=True, parents=True)
    
    all_results = []
    best_results = {}
    
    completed_count = 0
    skipped_count = 0
    
    for test_case in test_cases:
        case_id = test_case['case_id']
        n = test_case['n']
        m = test_case['m']
        r = test_case['r']
        L = test_case['L']
        
        print(f"\n{'='*60}")
        print(f"Test Case {case_id}: n={n}, m={m}, r={r}, L={L}")
        print(f"{'='*60}")
        
        # Create case-specific directory
        case_name = f"case{case_id}_n{n}_m{m}_r{r}"
        case_dir = scale_dir / case_name
        case_dir.mkdir(exist_ok=True)
        
        # Generate dataset file for this test case (shared across objective types)
        dataset_file = case_dir / "dataset.json"
        
        if not dataset_file.exists():
            try:
                _, num_tiles, total_generated, duplicates_removed = write_2d_covering_dataset_file(
                    test_case, str(dataset_file)
                )
                print(f"  Generated {num_tiles} unique tiles (from {total_generated} total, {duplicates_removed} duplicates removed)")
            except Exception as e:
                print(f"  ERROR: Failed to generate dataset: {e}")
                continue
        else:
            # Load existing dataset to get stats
            with open(dataset_file, 'r') as f:
                dataset = json.load(f)
            num_tiles = dataset['num_tiles']
            metadata = dataset.get('2d_covering_metadata', {})
            total_generated = metadata.get('total_generated', num_tiles)
            duplicates_removed = metadata.get('duplicates_removed', 0)
            print(f"  Using existing dataset: {num_tiles} unique tiles")
        
        # Run for each objective type
        for objective_type in objective_types:
            print(f"\n  --- Objective type: {objective_type} ---")
            
            # Run each algorithm
            for run in range(config.get('runs', 1)):
                seed = base_seed + run * 100
                
                for algo in config['algorithms']:
                    # Include objective type in filename to differentiate
                    output_filename = f"run_{run+1}_{algo}_{objective_type}.json"
                    output_file = case_dir / output_filename
                    
                    # Check if already completed
                    if resume and is_experiment_completed(output_file):
                        skipped_count += 1
                        
                        # Load existing result
                        try:
                            with open(output_file, 'r') as f:
                                solution_data = json.load(f)
                                if 'results' in solution_data and len(solution_data['results']) > 0:
                                    result_obj = solution_data['results'][0]
                                    
                                    if result_obj.get('status') in ['failed', 'parse_failed', 'error']:
                                        print(f"  [{algo}/{objective_type}] ⊙ Previously failed (skipped)", flush=True)
                                        continue
                                    
                                    result_entry = {
                                        'scale': scale,
                                        'case_id': case_id,
                                        'tiles': num_tiles,
                                        'n': n,
                                        'm': m,
                                        'r': r,
                                        'L': L,
                                        'total_generated': total_generated,
                                        'duplicates_removed': duplicates_removed,
                                        'run': run + 1,
                                        'seed': seed,
                                        'algorithm': algo,
                                        'objective_type': objective_type,
                                        'status': result_obj.get('status'),
                                        'objective': result_obj.get('objective'),
                                        'runtime': result_obj.get('runtime_seconds'),
                                        'bbox_width': result_obj.get('bbox_width'),
                                        'bbox_height': result_obj.get('bbox_height'),
                                        'num_tiles': result_obj.get('num_tiles_placed')
                                    }
                                    
                                    # Add genetic algorithm specific stats
                                    if 'total_crossovers' in result_obj:
                                        result_entry['total_crossovers'] = result_obj['total_crossovers']
                                        result_entry['crossovers_needing_completion'] = result_obj.get('crossovers_needing_completion')
                                        result_entry['total_tiles_completed'] = result_obj.get('total_tiles_completed')
                                    
                                    # Add search algorithm specific stats
                                    if 'iterations' in result_obj:
                                        result_entry['iterations'] = result_obj['iterations']
                                    if 'states_explored' in result_obj:
                                        result_entry['states_explored'] = result_obj['states_explored']
                                    if 'improvements_found' in result_obj:
                                        result_entry['improvements_found'] = result_obj['improvements_found']
                                    
                                    all_results.append(result_entry)
                                    obj = result_entry['objective']
                                    bbox_w = result_entry.get('bbox_width')
                                    bbox_h = result_entry.get('bbox_height')
                                    print(f"  [{algo}/{objective_type}] ⊙ Skipped, Obj={obj}, bbox={bbox_h}x{bbox_w}", flush=True)
                                    
                                    # Track best result
                                    if result_entry['objective'] is not None:
                                        key = f"{case_name}_{algo}_{objective_type}"
                                        if key not in best_results or (best_results[key]['objective'] is not None and result_entry['objective'] < best_results[key]['objective']):
                                            best_results[key] = result_entry.copy()
                                            best_results[key]['solution'] = solution_data
                        except Exception as e:
                            print(f"  [{algo}/{objective_type}] ⊙ Previously completed (warning: couldn't load: {e})", flush=True)
                        
                        continue
                    
                    print(f"  [{algo}/{objective_type}] ", end='', flush=True)
                    
                    # Run the experiment with the dataset file
                    result = run_single_experiment(
                        algo, num_tiles, n, m, seed, str(output_file),
                        config.get('pop_size'), config.get('generations'),
                        objective_type, config.get('cplex_time_limit'),
                        config.get('beam_width'), config.get('sa_max_iter'),
                        dataset_file=str(dataset_file)
                    )
                    
                    completed_count += 1
                    
                    if result['success']:
                        obj = result['objective']
                        runtime = result['runtime']
                        status = result.get('status')
                        bbox_w = result.get('bbox_width')
                        bbox_h = result.get('bbox_height')
                        
                        if obj is not None and runtime is not None:
                            print(f"✓ Obj={obj}, bbox={bbox_h}x{bbox_w}, Time={runtime:.3f}s")
                            
                            result_entry = {
                                'scale': scale,
                                'case_id': case_id,
                                'tiles': num_tiles,
                                'n': n,
                                'm': m,
                                'r': r,
                                'L': L,
                                'total_generated': total_generated,
                                'duplicates_removed': duplicates_removed,
                                'run': run + 1,
                                'seed': seed,
                                'algorithm': algo,
                                'objective_type': objective_type,
                                'status': status,
                                'objective': obj,
                                'runtime': runtime,
                                'bbox_width': result['bbox_width'],
                                'bbox_height': result['bbox_height'],
                                'num_tiles': result['num_tiles'],
                                'total_crossovers': result.get('total_crossovers'),
                                'crossovers_needing_completion': result.get('crossovers_needing_completion'),
                                'total_tiles_completed': result.get('total_tiles_completed'),
                                'iterations': result.get('iterations'),
                                'states_explored': result.get('states_explored'),
                                'improvements_found': result.get('improvements_found')
                            }
                            
                            all_results.append(result_entry)
                            
                            key = f"{case_name}_{algo}_{objective_type}"
                            if key not in best_results or obj < best_results[key]['objective']:
                                best_results[key] = result_entry.copy()
                                best_results[key]['solution'] = result['solution']
                        else:
                            print("✗ Parse failed (unexpected)")
                            failure_data = {
                                'input': {
                                    'case_id': case_id,
                                    'T': num_tiles,
                                    'n': n,
                                    'm': m,
                                    'r': r,
                                    'L': L,
                                    'seed': seed,
                                    'objective_type': objective_type
                                },
                                'results': [{
                                    'algorithm': algo,
                                    'status': 'parse_failed',
                                    'error': 'Failed to parse algorithm output'
                                }]
                            }
                            with open(output_file, 'w') as f:
                                json.dump(failure_data, f, indent=2)
                    else:
                        error_msg = result.get('error', 'unknown error')
                        if len(error_msg) > 200:
                            error_msg = error_msg[:200] + "..."
                        print(f"✗ {error_msg}")
                        failure_data = {
                            'input': {
                                'case_id': case_id,
                                'T': num_tiles,
                                'n': n,
                                'm': m,
                                'r': r,
                                'L': L,
                                'seed': seed,
                                'objective_type': objective_type
                            },
                            'results': [{
                                'algorithm': algo,
                                'status': 'failed',
                                'error': error_msg
                            }]
                        }
                        with open(output_file, 'w') as f:
                            json.dump(failure_data, f, indent=2)
        
        # Save case results (includes both objective types)
        case_results = [r for r in all_results if r.get('case_id') == case_id]
        with open(case_dir / 'all_results.json', 'w') as f:
            json.dump(case_results, f, indent=2)
    
    # Save scale-wide results
    with open(scale_dir / 'all_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    with open(scale_dir / 'best_results.json', 'w') as f:
        best_summary = {k: {kk: vv for kk, vv in v.items() if kk != 'solution'} 
                       for k, v in best_results.items()}
        json.dump(best_summary, f, indent=2)
    
    # Write results to CSV
    write_2d_covering_results_to_csv(all_results, scale_dir / 'all_results.csv')
    
    # Calculate and save summary statistics
    summary = calculate_2d_covering_summary_statistics(all_results)
    with open(scale_dir / 'summary_statistics.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    write_2d_covering_summary_to_csv(summary, scale_dir / 'summary_statistics.csv')
    
    print(f"\n{'='*80}")
    print(f"✓ {scale.upper()} scale experiments completed")
    print(f"  Total runs: {len(all_results)}")
    if resume:
        print(f"  New experiments run: {completed_count}")
        print(f"  Skipped (already done): {skipped_count}")
    print(f"  Results saved to: {scale_dir}")
    print(f"  CSV files: all_results.csv, summary_statistics.csv")
    print(f"{'='*80}")
    
    return all_results, best_results, summary


def run_2d_covering_original_experiment_suite(scale, config, base_seed, output_dir, resume=True):
    """
    Run 2D covering original experiments from a directory of files.
    
    Reads files from 2d_covering_dataset/ folder with format:
    - Filename: n_m_r_L.txt (e.g., 3_3_1_102.txt)
    - Content: [string1], [string2], ...
    
    For each string, for each position, takes cyclic substring of length n*m
    and converts to 2D tile. Removes duplicates.
    
    Args:
        scale: Scale name (e.g., '2d_covering_original')
        config: Experiment configuration
        base_seed: Base random seed
        output_dir: Output directory
        resume: Whether to skip completed experiments
    """
    data_dir = Path(config.get('data_dir', '2d_covering_dataset'))
    
    # Get objective types
    objective_types = config.get('objective_types', [config.get('objective_type', 'area')])
    if isinstance(objective_types, str):
        objective_types = [objective_types]
    
    print(f"\n{'='*80}")
    print(f"RUNNING {scale.upper()} SCALE EXPERIMENTS (2D Covering Original)")
    print(f"{'='*80}")
    if 'description' in config:
        print(f"Description: {config['description']}")
    print(f"Data directory: {data_dir}")
    print(f"Algorithms: {config['algorithms']}")
    print(f"Objective types: {objective_types}")
    print(f"Runs per configuration: {config.get('runs', 1)}")
    if resume:
        print(f"Resume mode: ON (will skip completed experiments)")
    print()
    
    # Find all .txt files in the data directory
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        return [], {}, {}
    
    txt_files = sorted(data_dir.glob('*.txt'))
    # Filter out input.txt or other non-data files
    txt_files = [f for f in txt_files if f.stem != 'input' and '_' in f.stem]
    
    print(f"Found {len(txt_files)} data files in {data_dir}")
    print()
    
    scale_dir = output_dir / scale
    scale_dir.mkdir(exist_ok=True, parents=True)
    
    all_results = []
    best_results = {}
    
    completed_count = 0
    skipped_count = 0
    
    for txt_file in txt_files:
        # Parse the file
        try:
            parsed_data = parse_2d_covering_original_file(txt_file)
        except Exception as e:
            print(f"ERROR: Failed to parse {txt_file}: {e}")
            continue
        
        n = parsed_data['n']
        m = parsed_data['m']
        r = parsed_data['r']
        L = parsed_data['L']
        num_input_strings = parsed_data['num_input_strings']
        
        print(f"\n{'='*60}")
        print(f"File: {txt_file.name} (n={n}, m={m}, r={r}, L={L})")
        print(f"  Input strings: {num_input_strings}")
        print(f"{'='*60}")
        
        # Create case-specific directory
        case_name = txt_file.stem  # e.g., "3_3_1_102"
        case_dir = scale_dir / case_name
        case_dir.mkdir(exist_ok=True)
        
        # Generate dataset file
        dataset_file = case_dir / "dataset.json"
        
        if not dataset_file.exists():
            try:
                _, num_tiles, total_generated, duplicates_removed, _ = write_2d_covering_original_dataset_file(
                    parsed_data, str(dataset_file)
                )
                print(f"  Generated {num_tiles} unique tiles (from {total_generated} total, {duplicates_removed} duplicates removed)")
            except Exception as e:
                print(f"  ERROR: Failed to generate dataset: {e}")
                continue
        else:
            # Load existing dataset to get stats
            with open(dataset_file, 'r') as f:
                dataset = json.load(f)
            num_tiles = dataset['num_tiles']
            metadata = dataset.get('2d_covering_original_metadata', {})
            total_generated = metadata.get('total_generated', num_tiles)
            duplicates_removed = metadata.get('duplicates_removed', 0)
            print(f"  Using existing dataset: {num_tiles} unique tiles")
        
        # Run for each objective type
        for objective_type in objective_types:
            print(f"\n  --- Objective type: {objective_type} ---")
            
            # Run each algorithm
            for run in range(config.get('runs', 1)):
                seed = base_seed + run * 100
                
                for algo in config['algorithms']:
                    output_filename = f"run_{run+1}_{algo}_{objective_type}.json"
                    output_file = case_dir / output_filename
                    
                    # Check if already completed
                    if resume and is_experiment_completed(output_file):
                        skipped_count += 1
                        
                        try:
                            with open(output_file, 'r') as f:
                                solution_data = json.load(f)
                                if 'results' in solution_data and len(solution_data['results']) > 0:
                                    result_obj = solution_data['results'][0]
                                    
                                    if result_obj.get('status') in ['failed', 'parse_failed', 'error']:
                                        print(f"  [{algo}/{objective_type}] ⊙ Previously failed (skipped)", flush=True)
                                        continue
                                    
                                    result_entry = {
                                        'scale': scale,
                                        'case_name': case_name,
                                        'tiles': num_tiles,
                                        'n': n,
                                        'm': m,
                                        'r': r,
                                        'L': L,
                                        'num_input_strings': num_input_strings,
                                        'total_generated': total_generated,
                                        'duplicates_removed': duplicates_removed,
                                        'run': run + 1,
                                        'seed': seed,
                                        'algorithm': algo,
                                        'objective_type': objective_type,
                                        'status': result_obj.get('status'),
                                        'objective': result_obj.get('objective'),
                                        'runtime': result_obj.get('runtime_seconds'),
                                        'bbox_width': result_obj.get('bbox_width'),
                                        'bbox_height': result_obj.get('bbox_height'),
                                        'num_tiles_placed': result_obj.get('num_tiles_placed')
                                    }
                                    
                                    all_results.append(result_entry)
                                    obj = result_entry['objective']
                                    bbox_w = result_entry.get('bbox_width')
                                    bbox_h = result_entry.get('bbox_height')
                                    print(f"  [{algo}/{objective_type}] ⊙ Skipped, Obj={obj}, bbox={bbox_h}x{bbox_w}", flush=True)
                                    
                                    if result_entry['objective'] is not None:
                                        key = f"{case_name}_{algo}_{objective_type}"
                                        if key not in best_results or (best_results[key]['objective'] is not None and result_entry['objective'] < best_results[key]['objective']):
                                            best_results[key] = result_entry.copy()
                                            best_results[key]['solution'] = solution_data
                        except Exception as e:
                            print(f"  [{algo}/{objective_type}] ⊙ Previously completed (warning: couldn't load: {e})", flush=True)
                        
                        continue
                    
                    print(f"  [{algo}/{objective_type}] ", end='', flush=True)
                    
                    # Run the experiment
                    result = run_single_experiment(
                        algo, num_tiles, n, m, seed, str(output_file),
                        config.get('pop_size'), config.get('generations'),
                        objective_type, config.get('cplex_time_limit'),
                        config.get('beam_width'), config.get('sa_max_iter'),
                        dataset_file=str(dataset_file)
                    )
                    
                    completed_count += 1
                    
                    if result['success']:
                        obj = result['objective']
                        runtime = result['runtime']
                        status = result.get('status')
                        bbox_w = result.get('bbox_width')
                        bbox_h = result.get('bbox_height')
                        
                        if obj is not None and runtime is not None:
                            print(f"✓ Obj={obj}, bbox={bbox_h}x{bbox_w}, Time={runtime:.3f}s")
                            
                            result_entry = {
                                'scale': scale,
                                'case_name': case_name,
                                'tiles': num_tiles,
                                'n': n,
                                'm': m,
                                'r': r,
                                'L': L,
                                'num_input_strings': num_input_strings,
                                'total_generated': total_generated,
                                'duplicates_removed': duplicates_removed,
                                'run': run + 1,
                                'seed': seed,
                                'algorithm': algo,
                                'objective_type': objective_type,
                                'status': status,
                                'objective': obj,
                                'runtime': runtime,
                                'bbox_width': bbox_w,
                                'bbox_height': bbox_h,
                                'num_tiles_placed': result['num_tiles']
                            }
                            
                            all_results.append(result_entry)
                            
                            key = f"{case_name}_{algo}_{objective_type}"
                            if key not in best_results or obj < best_results[key]['objective']:
                                best_results[key] = result_entry.copy()
                                best_results[key]['solution'] = result['solution']
                        else:
                            print("✗ Parse failed (unexpected)")
                            failure_data = {
                                'input': {
                                    'case_name': case_name,
                                    'n': n,
                                    'm': m,
                                    'r': r,
                                    'L': L,
                                    'num_input_strings': num_input_strings,
                                    'seed': seed,
                                    'objective_type': objective_type
                                },
                                'results': [{
                                    'algorithm': algo,
                                    'status': 'parse_failed',
                                    'error': 'Failed to parse algorithm output'
                                }]
                            }
                            with open(output_file, 'w') as f:
                                json.dump(failure_data, f, indent=2)
                    else:
                        error_msg = result.get('error', 'unknown error')
                        if len(error_msg) > 200:
                            error_msg = error_msg[:200] + "..."
                        print(f"✗ {error_msg}")
                        failure_data = {
                            'input': {
                                'case_name': case_name,
                                'n': n,
                                'm': m,
                                'r': r,
                                'L': L,
                                'num_input_strings': num_input_strings,
                                'seed': seed,
                                'objective_type': objective_type
                            },
                            'results': [{
                                'algorithm': algo,
                                'status': 'failed',
                                'error': error_msg
                            }]
                        }
                        with open(output_file, 'w') as f:
                            json.dump(failure_data, f, indent=2)
        
        # Save case results
        case_results = [r for r in all_results if r.get('case_name') == case_name]
        with open(case_dir / 'all_results.json', 'w') as f:
            json.dump(case_results, f, indent=2)
    
    # Save scale-wide results
    with open(scale_dir / 'all_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    with open(scale_dir / 'best_results.json', 'w') as f:
        best_summary = {k: {kk: vv for kk, vv in v.items() if kk != 'solution'} 
                       for k, v in best_results.items()}
        json.dump(best_summary, f, indent=2)
    
    # Write results to CSV
    write_2d_covering_original_results_to_csv(all_results, scale_dir / 'all_results.csv')
    
    # Calculate and save summary statistics
    summary = calculate_2d_covering_original_summary_statistics(all_results)
    with open(scale_dir / 'summary_statistics.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    write_2d_covering_original_summary_to_csv(summary, scale_dir / 'summary_statistics.csv')
    
    print(f"\n{'='*80}")
    print(f"✓ {scale.upper()} scale experiments completed")
    print(f"  Total runs: {len(all_results)}")
    if resume:
        print(f"  New experiments run: {completed_count}")
        print(f"  Skipped (already done): {skipped_count}")
    print(f"  Results saved to: {scale_dir}")
    print(f"  CSV files: all_results.csv, summary_statistics.csv")
    print(f"{'='*80}")
    
    return all_results, best_results, summary


def run_structured_experiment_suite(scale, config, base_seed, output_dir, resume=True, patterns=None):
    """
    Run structured/reassembly experiments.
    
    This creates source bitmaps and extracts overlapping subarrays to test
    if algorithms can reconstruct the original image.
    
    Args:
        scale: Scale name (e.g., 'structured')
        config: Experiment configuration
        base_seed: Base random seed
        output_dir: Output directory
        resume: Whether to skip completed experiments
        patterns: List of patterns to test (overrides config['patterns'] if provided)
    """
    # Get patterns from argument or config
    pattern_list = patterns if patterns else config.get('patterns', ['random'])
    
    print(f"\n{'='*80}")
    print(f"RUNNING {scale.upper()} SCALE EXPERIMENTS (Structured/Reassembly)")
    print(f"{'='*80}")
    if 'description' in config:
        print(f"Description: {config['description']}")
    print(f"Source sizes: {config['source_sizes']}")
    print(f"Tile sizes: {config['tile_size']}")
    tile_density = config.get('tile_density', 4.0)
    print(f"Tile density: {tile_density} (num_tiles = source_area / (tile_area * density))")
    print(f"Patterns: {pattern_list}")
    print(f"Algorithms: {config['algorithms']}")
    print(f"Objective type: {config.get('objective_type', 'area')}")
    
    alphabet_size = config.get('alphabet_size', 2)
    print(f"Alphabet size: {alphabet_size}")
    if alphabet_size > 127:
        print(f"WARNING: alphabet_size > 127 may cause UTF-8 encoding issues in C++ JSON output!")
    
    print(f"Runs per configuration: {config['runs']}")
    if resume:
        print(f"Resume mode: ON (will skip completed experiments)")
    print()
    
    scale_dir = output_dir / scale
    scale_dir.mkdir(exist_ok=True, parents=True)
    
    all_results = []
    best_results = {}
    
    completed_count = 0
    skipped_count = 0
    
    # Iterate over each pattern
    for pattern in pattern_list:
        print(f"\n{'='*60}")
        print(f"Pattern: {pattern}")
        print(f"{'='*60}")
        
        # Create pattern-specific subdirectory
        pattern_dir = scale_dir / pattern
        pattern_dir.mkdir(exist_ok=True)
        
        for (src_h, src_w) in config['source_sizes']:
            for (n, m) in config['tile_size']:
                # Determine number of tiles based on coverage mode
                full_coverage = config.get('full_coverage', False)
                source_area = src_h * src_w
                tile_area = n * m
                
                if full_coverage:
                    # Full coverage: all valid positions → (H-n+1) × (W-m+1) tiles
                    num_tiles = (src_h - n + 1) * (src_w - m + 1)
                else:
                    # Density-based: num_tiles = source_area / (tile_area * tile_density)
                    tile_density = config.get('tile_density', 4.0)
                    num_tiles = max(10, int(source_area / (tile_area * tile_density)))
                
                alphabet_size = config.get('alphabet_size', 2)
                optimal_area = src_h * src_w
                exp_name = f"src{src_h}x{src_w}_T{num_tiles}_n{n}_m{m}"
                if alphabet_size != 2:
                    exp_name += f"_a{alphabet_size}"
                coverage_str = "100% coverage" if full_coverage else f"density={config.get('tile_density', 4.0)}"
                print(f"\n--- Experiment: {exp_name} (optimal area={optimal_area}, {coverage_str}) ---")
                
                exp_dir = pattern_dir / exp_name
                exp_dir.mkdir(exist_ok=True)
                
                for run in range(config['runs']):
                    seed = base_seed + run * 100
                    print(f"\nRun {run + 1}/{config['runs']} (seed={seed})")
                    
                    # Generate the structured dataset file
                    dataset_filename = f"dataset_run{run+1}.json"
                    if alphabet_size != 2:
                        dataset_filename = f"dataset_run{run+1}_a{alphabet_size}.json"
                    dataset_file = exp_dir / dataset_filename
                    
                    if not dataset_file.exists():
                        # Check for pre-generated dataset first
                        use_pregenerated = config.get('use_pregenerated_datasets', False)
                        datasets_dir = config.get('datasets_dir', 'experiment_structural/datasets')
                        pregenerated_path = Path(datasets_dir) / f"src{src_h}x{src_w}" / pattern / "dataset.json"
                        
                        if use_pregenerated and pregenerated_path.exists():
                            # Load pre-generated dataset and save to experiment dir
                            shutil.copy(pregenerated_path, dataset_file)
                            # Read to get tile count
                            with open(dataset_file, 'r') as f:
                                pregenerated_data = json.load(f)
                            actual_num_tiles = pregenerated_data.get('num_tiles', len(pregenerated_data.get('tiles', [])))
                            print(f"    Loaded pre-generated dataset with {actual_num_tiles} tiles from {pregenerated_path}")
                        else:
                            # Generate on-the-fly
                            if use_pregenerated:
                                print(f"    Warning: Pre-generated dataset not found at {pregenerated_path}, generating...")
                            _, _, actual_num_tiles = write_structured_dataset_file(
                                src_h, src_w, num_tiles, n, m, seed, pattern,
                                str(dataset_file),
                                alphabet_size=config.get('alphabet_size', 2),
                                full_coverage=full_coverage
                            )
                            print(f"    Generated dataset with {actual_num_tiles} tiles")
                        # Validate the dataset file is valid JSON
                        try:
                            with open(dataset_file, 'r') as f:
                                json.load(f)
                        except Exception as e:
                            print(f"    ERROR: Generated dataset file is invalid: {e}")
                            continue
                    
                    for algo in config['algorithms']:
                        output_filename = f"run_{run+1}_{algo}.json"
                        if alphabet_size != 2:
                            output_filename = f"run_{run+1}_{algo}_a{alphabet_size}.json"
                        output_file = exp_dir / output_filename
                        
                        # Check if already completed
                        if resume and is_experiment_completed(output_file):
                            skipped_count += 1
                            
                            # Load existing result
                            try:
                                with open(output_file, 'r') as f:
                                    solution_data = json.load(f)
                                    if 'results' in solution_data and len(solution_data['results']) > 0:
                                        result_obj = solution_data['results'][0]
                                        
                                        if result_obj.get('status') in ['failed', 'parse_failed', 'error']:
                                            print(f"  [{algo}] ⊙ Previously failed (skipped)", flush=True)
                                            continue
                                        
                                        result_entry = {
                                            'scale': scale,
                                            'source_height': src_h,
                                            'source_width': src_w,
                                            'optimal_area': optimal_area,
                                            'tiles': num_tiles,
                                            'n': n,
                                            'm': m,
                                            'run': run + 1,
                                            'seed': seed,
                                            'algorithm': algo,
                                            'objective_type': config.get('objective_type', 'area'),
                                            'pattern': pattern,
                                            'status': result_obj.get('status'),
                                            'objective': result_obj.get('objective'),
                                            'runtime': result_obj.get('runtime_seconds'),
                                            'bbox_width': result_obj.get('bbox_width'),
                                            'bbox_height': result_obj.get('bbox_height'),
                                            'num_tiles': result_obj.get('num_tiles_placed'),
                                            'compression_ratio': optimal_area / result_obj.get('objective', optimal_area) if result_obj.get('objective') else None
                                        }
                                        
                                        all_results.append(result_entry)
                                        print(f"  [{algo}] ⊙ Already completed (skipped)", flush=True)
                                        
                                        if result_entry['objective'] is not None:
                                            key = f"{exp_name}_{algo}"
                                            if key not in best_results or result_entry['objective'] < best_results[key]['objective']:
                                                best_results[key] = result_entry.copy()
                                                best_results[key]['solution'] = solution_data
                            except Exception as e:
                                print(f"  [{algo}] ⊙ Previously completed (warning: couldn't load: {e})", flush=True)
                            
                            continue
                        
                        print(f"  [{algo}] ", end='', flush=True)
                        
                        # Run the experiment with the dataset file
                        result = run_single_experiment(
                            algo, num_tiles, n, m, seed, str(output_file),
                            config.get('pop_size'), config.get('generations'),
                            config.get('objective_type'), config.get('cplex_time_limit'),
                            config.get('beam_width'), config.get('sa_max_iter'),
                            dataset_file=str(dataset_file)
                        )
                        
                        completed_count += 1
                        
                        if result['success']:
                            obj = result['objective']
                            runtime = result['runtime']
                            status = result.get('status')
                            
                            if obj is not None and runtime is not None:
                                compression = optimal_area / obj if obj > 0 else 0
                                status_marker = "✓" if compression >= 0.9 else "≈" if compression >= 0.5 else "!"
                                
                                print(f"{status_marker} Area={obj} (optimal={optimal_area}, ratio={compression:.2f}), Time={runtime:.3f}s")
                                
                                result_entry = {
                                    'scale': scale,
                                    'source_height': src_h,
                                    'source_width': src_w,
                                    'optimal_area': optimal_area,
                                    'tiles': num_tiles,
                                    'n': n,
                                    'm': m,
                                    'run': run + 1,
                                    'seed': seed,
                                    'algorithm': algo,
                                    'objective_type': config.get('objective_type', 'area'),
                                    'pattern': pattern,
                                    'status': status,
                                    'objective': obj,
                                    'runtime': runtime,
                                    'bbox_width': result['bbox_width'],
                                    'bbox_height': result['bbox_height'],
                                    'num_tiles': result['num_tiles'],
                                    'compression_ratio': compression
                                }
                                
                                all_results.append(result_entry)
                                
                                key = f"{exp_name}_{algo}"
                                if key not in best_results or obj < best_results[key]['objective']:
                                    best_results[key] = result_entry.copy()
                                    best_results[key]['solution'] = result['solution']
                            else:
                                print("✗ Parse failed (unexpected)")
                                failure_data = {
                                    'input': {
                                        'source_height': src_h,
                                        'source_width': src_w,
                                        'T': num_tiles,
                                        'n': n,
                                        'm': m,
                                        'seed': seed,
                                        'objective_type': config.get('objective_type', 'area')
                                    },
                                    'results': [{
                                        'algorithm': algo,
                                        'status': 'parse_failed',
                                        'error': 'Failed to parse algorithm output'
                                    }]
                                }
                                with open(output_file, 'w') as f:
                                    json.dump(failure_data, f, indent=2)
                        else:
                            error_msg = result.get('error', 'unknown error')
                            if len(error_msg) > 200:
                                error_msg = error_msg[:200] + "..."
                            print(f"✗ {error_msg}")
                            failure_data = {
                                'input': {
                                    'source_height': src_h,
                                    'source_width': src_w,
                                    'T': num_tiles,
                                    'n': n,
                                    'm': m,
                                    'seed': seed,
                                    'objective_type': config.get('objective_type', 'area')
                                },
                                'results': [{
                                    'algorithm': algo,
                                    'status': 'failed',
                                    'error': error_msg
                                }]
                            }
                            with open(output_file, 'w') as f:
                                json.dump(failure_data, f, indent=2)
                
                # Save experiment results for this configuration
                exp_results = [r for r in all_results 
                              if r.get('source_height') == src_h and r.get('source_width') == src_w 
                              and r['tiles'] == num_tiles and r['n'] == n and r['m'] == m
                              and r.get('pattern') == pattern]
                with open(exp_dir / 'all_results.json', 'w') as f:
                    json.dump(exp_results, f, indent=2)
        
        # Save pattern-specific results
        pattern_results = [r for r in all_results if r.get('pattern') == pattern]
        with open(pattern_dir / 'all_results.json', 'w') as f:
            json.dump(pattern_results, f, indent=2)
        
        # Write pattern-specific CSV
        write_structured_results_to_csv(pattern_results, pattern_dir / 'all_results.csv')
        
        # Calculate pattern-specific summary
        pattern_summary = calculate_structured_summary_statistics(pattern_results)
        with open(pattern_dir / 'summary_statistics.json', 'w') as f:
            json.dump(pattern_summary, f, indent=2)
        write_structured_summary_to_csv(pattern_summary, pattern_dir / 'summary_statistics.csv')
    
    # Save scale-wide results (all patterns combined)
    with open(scale_dir / 'all_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    with open(scale_dir / 'best_results.json', 'w') as f:
        best_summary = {k: {kk: vv for kk, vv in v.items() if kk != 'solution'} 
                       for k, v in best_results.items()}
        json.dump(best_summary, f, indent=2)
    
    # Write results to CSV with structured-specific fields
    write_structured_results_to_csv(all_results, scale_dir / 'all_results.csv')
    
    # Calculate and save summary statistics
    summary = calculate_structured_summary_statistics(all_results)
    with open(scale_dir / 'summary_statistics.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    write_structured_summary_to_csv(summary, scale_dir / 'summary_statistics.csv')
    
    print(f"\n{'='*80}")
    print(f"✓ {scale.upper()} scale experiments completed")
    print(f"  Total runs: {len(all_results)}")
    if resume:
        print(f"  New experiments run: {completed_count}")
        print(f"  Skipped (already done): {skipped_count}")
    print(f"  Results saved to: {scale_dir}")
    print(f"{'='*80}")
    
    return all_results, best_results, summary


def write_2d_covering_results_to_csv(results, output_file):
    """Write 2d_covering experiment results to CSV."""
    if not results:
        return
    
    fieldnames = ['scale', 'case_id', 'tiles', 'n', 'm', 'r', 'L',
                  'total_generated', 'duplicates_removed',
                  'run', 'seed', 'algorithm', 'objective_type',
                  'status', 'objective', 'runtime', 'bbox_width', 'bbox_height', 'num_tiles',
                  'total_crossovers', 'crossovers_needing_completion', 'total_tiles_completed',
                  'iterations', 'states_explored', 'improvements_found']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)


def write_2d_covering_original_results_to_csv(results, output_file):
    """Write 2d_covering_original experiment results to CSV."""
    if not results:
        return
    
    fieldnames = ['scale', 'case_name', 'tiles', 'n', 'm', 'r', 'L',
                  'num_input_strings', 'total_generated', 'duplicates_removed',
                  'run', 'seed', 'algorithm', 'objective_type',
                  'status', 'objective', 'runtime', 'bbox_width', 'bbox_height', 'num_tiles_placed']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)


def calculate_2d_covering_original_summary_statistics(results):
    """Calculate summary statistics for 2d_covering_original experiments."""
    summary = {}
    
    groups = {}
    for r in results:
        key = f"{r['algorithm']}_{r['case_name']}_{r['objective_type']}"
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    
    for key, group in groups.items():
        objectives = [r['objective'] for r in group if r['objective'] is not None]
        runtimes = [r['runtime'] for r in group if r['runtime'] is not None]
        
        if not objectives or not runtimes:
            continue
        
        stats = {
            'algorithm': group[0]['algorithm'],
            'case_name': group[0]['case_name'],
            'objective_type': group[0]['objective_type'],
            'tiles': group[0]['tiles'],
            'n': group[0]['n'],
            'm': group[0]['m'],
            'r': group[0]['r'],
            'L': group[0]['L'],
            'num_input_strings': group[0].get('num_input_strings'),
            'total_generated': group[0].get('total_generated'),
            'duplicates_removed': group[0].get('duplicates_removed'),
            'num_runs': len(group),
            'successful_runs': len(objectives),
            'objective': {
                'mean': sum(objectives) / len(objectives),
                'min': min(objectives),
                'max': max(objectives),
                'std': (sum((x - sum(objectives)/len(objectives))**2 for x in objectives) / len(objectives))**0.5 if len(objectives) > 1 else 0
            },
            'runtime': {
                'mean': sum(runtimes) / len(runtimes),
                'min': min(runtimes),
                'max': max(runtimes),
                'std': (sum((x - sum(runtimes)/len(runtimes))**2 for x in runtimes) / len(runtimes))**0.5 if len(runtimes) > 1 else 0
            }
        }
        
        summary[key] = stats
    
    return summary


def write_2d_covering_original_summary_to_csv(summary, output_file):
    """Write 2d_covering_original summary statistics to CSV."""
    if not summary:
        return
    
    fieldnames = ['algorithm', 'case_name', 'objective_type', 'tiles', 'n', 'm', 'r', 'L',
                  'num_input_strings', 'total_generated', 'duplicates_removed',
                  'num_runs', 'successful_runs',
                  'obj_mean', 'obj_min', 'obj_max', 'obj_std',
                  'runtime_mean', 'runtime_min', 'runtime_max', 'runtime_std']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for key, stats in summary.items():
            row = {
                'algorithm': stats['algorithm'],
                'case_name': stats['case_name'],
                'objective_type': stats['objective_type'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'r': stats['r'],
                'L': stats['L'],
                'num_input_strings': stats.get('num_input_strings'),
                'total_generated': stats.get('total_generated'),
                'duplicates_removed': stats.get('duplicates_removed'),
                'num_runs': stats['num_runs'],
                'successful_runs': stats.get('successful_runs', stats['num_runs']),
                'obj_mean': stats['objective']['mean'],
                'obj_min': stats['objective']['min'],
                'obj_max': stats['objective']['max'],
                'obj_std': stats['objective']['std'],
                'runtime_mean': stats['runtime']['mean'],
                'runtime_min': stats['runtime']['min'],
                'runtime_max': stats['runtime']['max'],
                'runtime_std': stats['runtime']['std']
            }
            writer.writerow(row)


def calculate_2d_covering_summary_statistics(results):
    """Calculate summary statistics for 2d_covering experiments."""
    summary = {}
    
    groups = {}
    for r in results:
        key = f"{r['algorithm']}_case{r['case_id']}_n{r['n']}_m{r['m']}"
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    
    for key, group in groups.items():
        objectives = [r['objective'] for r in group if r['objective'] is not None]
        runtimes = [r['runtime'] for r in group if r['runtime'] is not None]
        
        if not objectives or not runtimes:
            continue
        
        stats = {
            'algorithm': group[0]['algorithm'],
            'case_id': group[0]['case_id'],
            'tiles': group[0]['tiles'],
            'n': group[0]['n'],
            'm': group[0]['m'],
            'r': group[0]['r'],
            'L': group[0]['L'],
            'total_generated': group[0].get('total_generated'),
            'duplicates_removed': group[0].get('duplicates_removed'),
            'num_runs': len(group),
            'successful_runs': len(objectives),
            'objective': {
                'mean': sum(objectives) / len(objectives),
                'min': min(objectives),
                'max': max(objectives),
                'std': (sum((x - sum(objectives)/len(objectives))**2 for x in objectives) / len(objectives))**0.5 if len(objectives) > 1 else 0
            },
            'runtime': {
                'mean': sum(runtimes) / len(runtimes),
                'min': min(runtimes),
                'max': max(runtimes),
                'std': (sum((x - sum(runtimes)/len(runtimes))**2 for x in runtimes) / len(runtimes))**0.5 if len(runtimes) > 1 else 0
            }
        }
        
        summary[key] = stats
    
    return summary


def write_2d_covering_summary_to_csv(summary, output_file):
    """Write 2d_covering summary statistics to CSV."""
    if not summary:
        return
    
    fieldnames = ['algorithm', 'case_id', 'tiles', 'n', 'm', 'r', 'L',
                  'total_generated', 'duplicates_removed',
                  'num_runs', 'successful_runs',
                  'obj_mean', 'obj_min', 'obj_max', 'obj_std',
                  'runtime_mean', 'runtime_min', 'runtime_max', 'runtime_std']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for key, stats in summary.items():
            row = {
                'algorithm': stats['algorithm'],
                'case_id': stats['case_id'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'r': stats['r'],
                'L': stats['L'],
                'total_generated': stats.get('total_generated'),
                'duplicates_removed': stats.get('duplicates_removed'),
                'num_runs': stats['num_runs'],
                'successful_runs': stats.get('successful_runs', stats['num_runs']),
                'obj_mean': stats['objective']['mean'],
                'obj_min': stats['objective']['min'],
                'obj_max': stats['objective']['max'],
                'obj_std': stats['objective']['std'],
                'runtime_mean': stats['runtime']['mean'],
                'runtime_min': stats['runtime']['min'],
                'runtime_max': stats['runtime']['max'],
                'runtime_std': stats['runtime']['std']
            }
            writer.writerow(row)


def write_structured_results_to_csv(results, output_file):
    """Write structured experiment results to CSV."""
    if not results:
        return
    
    fieldnames = ['scale', 'source_height', 'source_width', 'optimal_area', 'tiles', 'n', 'm', 
                  'run', 'seed', 'algorithm', 'objective_type', 'pattern',
                  'status', 'objective', 'runtime', 'bbox_width', 'bbox_height', 'num_tiles',
                  'compression_ratio']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)


def calculate_structured_summary_statistics(results):
    """Calculate summary statistics for structured experiments."""
    summary = {}
    
    groups = {}
    for r in results:
        key = f"{r['algorithm']}_src{r['source_height']}x{r['source_width']}_T{r['tiles']}_n{r['n']}_m{r['m']}"
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    
    for key, group in groups.items():
        objectives = [r['objective'] for r in group if r['objective'] is not None]
        runtimes = [r['runtime'] for r in group if r['runtime'] is not None]
        compression_ratios = [r['compression_ratio'] for r in group if r.get('compression_ratio') is not None]
        
        if not objectives or not runtimes:
            continue
        
        optimal = group[0].get('optimal_area', 0)
        
        stats = {
            'algorithm': group[0]['algorithm'],
            'source_height': group[0]['source_height'],
            'source_width': group[0]['source_width'],
            'optimal_area': optimal,
            'tiles': group[0]['tiles'],
            'n': group[0]['n'],
            'm': group[0]['m'],
            'num_runs': len(group),
            'successful_runs': len(objectives),
            'objective': {
                'mean': sum(objectives) / len(objectives),
                'min': min(objectives),
                'max': max(objectives),
                'std': (sum((x - sum(objectives)/len(objectives))**2 for x in objectives) / len(objectives))**0.5 if len(objectives) > 1 else 0
            },
            'runtime': {
                'mean': sum(runtimes) / len(runtimes),
                'min': min(runtimes),
                'max': max(runtimes),
                'std': (sum((x - sum(runtimes)/len(runtimes))**2 for x in runtimes) / len(runtimes))**0.5 if len(runtimes) > 1 else 0
            },
            'compression_ratio': {
                'mean': sum(compression_ratios) / len(compression_ratios) if compression_ratios else 0,
                'min': min(compression_ratios) if compression_ratios else 0,
                'max': max(compression_ratios) if compression_ratios else 0
            }
        }
        
        summary[key] = stats
    
    return summary


def write_structured_summary_to_csv(summary, output_file):
    """Write structured summary statistics to CSV."""
    if not summary:
        return
    
    fieldnames = ['algorithm', 'source_height', 'source_width', 'optimal_area', 'tiles', 'n', 'm',
                  'num_runs', 'successful_runs',
                  'obj_mean', 'obj_min', 'obj_max', 'obj_std',
                  'runtime_mean', 'runtime_min', 'runtime_max', 'runtime_std',
                  'compression_mean', 'compression_min', 'compression_max']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for key, stats in summary.items():
            row = {
                'algorithm': stats['algorithm'],
                'source_height': stats['source_height'],
                'source_width': stats['source_width'],
                'optimal_area': stats['optimal_area'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'num_runs': stats['num_runs'],
                'successful_runs': stats.get('successful_runs', stats['num_runs']),
                'obj_mean': stats['objective']['mean'],
                'obj_min': stats['objective']['min'],
                'obj_max': stats['objective']['max'],
                'obj_std': stats['objective']['std'],
                'runtime_mean': stats['runtime']['mean'],
                'runtime_min': stats['runtime']['min'],
                'runtime_max': stats['runtime']['max'],
                'runtime_std': stats['runtime']['std'],
                'compression_mean': stats['compression_ratio']['mean'],
                'compression_min': stats['compression_ratio']['min'],
                'compression_max': stats['compression_ratio']['max']
            }
            writer.writerow(row)


def write_results_to_csv(results, output_file):
    """Write all results to a CSV file."""
    if not results:
        return
    
    # Determine all possible fields
    fieldnames = ['scale', 'tiles', 'n', 'm', 'run', 'seed', 'algorithm', 'objective_type',
                  'status', 'objective', 'runtime', 'bbox_width', 'bbox_height', 'num_tiles',
                  'total_crossovers', 'crossovers_needing_completion', 'total_tiles_completed',
                  'completion_rate', 'avg_tiles_per_incomplete',
                  # Search algorithm specific stats (beam search, simulated annealing)
                  'iterations', 'states_explored', 'improvements_found']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for result in results:
            row = result.copy()
            # Calculate derived metrics for genetic algorithms
            if result.get('total_crossovers') and result['total_crossovers'] > 0:
                row['completion_rate'] = result['crossovers_needing_completion'] / result['total_crossovers']
                if result['crossovers_needing_completion'] > 0:
                    row['avg_tiles_per_incomplete'] = result['total_tiles_completed'] / result['crossovers_needing_completion']
            writer.writerow(row)

def write_summary_to_csv(summary, output_file):
    """Write summary statistics to a CSV file."""
    if not summary:
        return
    
    fieldnames = ['algorithm', 'tiles', 'n', 'm', 'num_runs', 'successful_runs',
                  'obj_mean', 'obj_min', 'obj_max', 'obj_std',
                  'runtime_mean', 'runtime_min', 'runtime_max', 'runtime_std',
                  'crossovers_mean', 'completion_rate_mean', 'tiles_completed_mean',
                  # Search algorithm specific stats
                  'iterations_mean', 'states_explored_mean', 'improvements_found_mean',
                  'cplex_optimal', 'cplex_feasible', 'cplex_infeasible', 'cplex_timeout', 'cplex_failed']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for key, stats in summary.items():
            row = {
                'algorithm': stats['algorithm'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'num_runs': stats['num_runs'],
                'successful_runs': stats.get('successful_runs', stats['num_runs']),
                'obj_mean': stats['objective']['mean'],
                'obj_min': stats['objective']['min'],
                'obj_max': stats['objective']['max'],
                'obj_std': stats['objective']['std'],
                'runtime_mean': stats['runtime']['mean'],
                'runtime_min': stats['runtime']['min'],
                'runtime_max': stats['runtime']['max'],
                'runtime_std': stats['runtime']['std']
            }
            
            # Add genetic algorithm specific stats
            if 'crossover_stats' in stats:
                row['crossovers_mean'] = stats['crossover_stats']['avg_total_crossovers']
                row['completion_rate_mean'] = stats['crossover_stats']['avg_completion_rate']
                row['tiles_completed_mean'] = stats['crossover_stats']['avg_tiles_completed']
            
            # Add search algorithm specific stats
            if 'search_stats' in stats:
                row['iterations_mean'] = stats['search_stats']['avg_iterations']
                row['states_explored_mean'] = stats['search_stats']['avg_states_explored']
                row['improvements_found_mean'] = stats['search_stats']['avg_improvements_found']
            
            # Add CPLEX status counts
            if 'cplex_status_counts' in stats:
                row['cplex_optimal'] = stats['cplex_status_counts']['optimal']
                row['cplex_feasible'] = stats['cplex_status_counts']['feasible']
                row['cplex_infeasible'] = stats['cplex_status_counts']['infeasible']
                row['cplex_timeout'] = stats['cplex_status_counts']['timeout']
                row['cplex_failed'] = stats['cplex_status_counts']['failed']
            
            writer.writerow(row)

def write_aggregated_stats_csv(results, output_file):
    """Write aggregated statistics (avg and stdev) for each configuration to CSV."""
    if not results:
        return
    
    # Calculate summary statistics
    summary = calculate_summary_statistics(results)
    
    fieldnames = ['algorithm', 'tiles', 'n', 'm', 'objective_type', 
                  'avg_objective', 'stdev_objective', 
                  'avg_runtime', 'stdev_runtime']
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for key, stats in sorted(summary.items()):
            row = {
                'algorithm': stats['algorithm'],
                'tiles': stats['tiles'],
                'n': stats['n'],
                'm': stats['m'],
                'objective_type': stats.get('objective_type', 'square'),
                'avg_objective': round(stats['objective']['mean'], 2),
                'stdev_objective': round(stats['objective']['std'], 2),
                'avg_runtime': round(stats['runtime']['mean'], 4),
                'stdev_runtime': round(stats['runtime']['std'], 4)
            }
            
            writer.writerow(row)

def calculate_summary_statistics(results):
    """Calculate summary statistics for results."""
    summary = {}
    
    # Group by algorithm, configuration, and objective_type
    groups = {}
    for r in results:
        obj_type = r.get('objective_type', 'square')
        key = f"{r['algorithm']}_T{r['tiles']}_n{r['n']}_m{r['m']}_{obj_type}"
        if key not in groups:
            groups[key] = []
        groups[key].append(r)
    
    for key, group in groups.items():
        # Filter out None values from failed experiments
        objectives = [r['objective'] for r in group if r['objective'] is not None]
        runtimes = [r['runtime'] for r in group if r['runtime'] is not None]
        
        # Skip if no valid data
        if not objectives or not runtimes:
            continue
        
        stats = {
            'algorithm': group[0]['algorithm'],
            'tiles': group[0]['tiles'],
            'n': group[0]['n'],
            'm': group[0]['m'],
            'objective_type': group[0].get('objective_type', 'square'),
            'num_runs': len(group),
            'successful_runs': len(objectives),
            'objective': {
                'mean': sum(objectives) / len(objectives),
                'min': min(objectives),
                'max': max(objectives),
                'std': (sum((x - sum(objectives)/len(objectives))**2 for x in objectives) / len(objectives))**0.5 if len(objectives) > 1 else 0
            },
            'runtime': {
                'mean': sum(runtimes) / len(runtimes),
                'min': min(runtimes),
                'max': max(runtimes),
                'std': (sum((x - sum(runtimes)/len(runtimes))**2 for x in runtimes) / len(runtimes))**0.5 if len(runtimes) > 1 else 0
            }
        }
        
        # Add CPLEX-specific status counts
        if group[0]['algorithm'] == 'cplex':
            status_counts = {
                'optimal': sum(1 for r in group if r.get('status') == 'optimal'),
                'feasible': sum(1 for r in group if r.get('status') == 'feasible'),
                'infeasible': sum(1 for r in group if r.get('status') == 'infeasible'),
                'timeout': sum(1 for r in group if r.get('status') == 'timeout'),
                'failed': sum(1 for r in group if r.get('status') in ['failed', 'parse_failed', 'error'])
            }
            stats['cplex_status_counts'] = status_counts
        
        # Add genetic algorithm specific stats
        if group[0].get('total_crossovers'):
            crossovers = [r['total_crossovers'] for r in group if r.get('total_crossovers')]
            completions = [r['crossovers_needing_completion'] for r in group if r.get('crossovers_needing_completion')]
            tiles_completed = [r['total_tiles_completed'] for r in group if r.get('total_tiles_completed')]
            
            if crossovers:
                stats['crossover_stats'] = {
                    'avg_total_crossovers': sum(crossovers) / len(crossovers),
                    'avg_completions': sum(completions) / len(completions),
                    'avg_completion_rate': sum(c/t for c, t in zip(completions, crossovers)) / len(crossovers),
                    'avg_tiles_completed': sum(tiles_completed) / len(tiles_completed) if tiles_completed else 0
                }
        
        # Add search algorithm specific stats (beam search, simulated annealing)
        if group[0].get('states_explored'):
            iterations = [r['iterations'] for r in group if r.get('iterations')]
            states_explored = [r['states_explored'] for r in group if r.get('states_explored')]
            improvements_found = [r['improvements_found'] for r in group if r.get('improvements_found') is not None]
            
            if states_explored:
                stats['search_stats'] = {
                    'avg_iterations': sum(iterations) / len(iterations) if iterations else 0,
                    'avg_states_explored': sum(states_explored) / len(states_explored),
                    'avg_improvements_found': sum(improvements_found) / len(improvements_found) if improvements_found else 0
                }
        
        summary[key] = stats
    
    return summary

def load_all_results_from_directory(output_dir):
    """Load all existing results from the output directory."""
    all_results = []
    output_path = Path(output_dir)
    
    # Scan all scale directories
    for scale_dir in output_path.iterdir():
        if not scale_dir.is_dir():
            continue
        
        # Check if this looks like a scale directory by looking for all_results.json
        all_results_file = scale_dir / 'all_results.json'
        if all_results_file.exists():
            try:
                with open(all_results_file, 'r') as f:
                    scale_results = json.load(f)
                    all_results.extend(scale_results)
                    print(f"  Loaded {len(scale_results)} results from {scale_dir.name}")
            except Exception as e:
                print(f"  Warning: Could not load results from {scale_dir.name}: {e}")
    
    return all_results

def write_structured_comparison_json(results, output_file):
    """Write structured comparison JSON organized by config, objective type, and algorithm."""
    if not results:
        return
    
    # Group results by config (T, n, m)
    by_config = {}
    
    for r in results:
        if r['objective'] is None or r['runtime'] is None:
            continue  # Skip failed runs
        
        config_key = f"T{r['tiles']}_n{r['n']}_m{r['m']}"
        obj_type = r.get('objective_type', 'square')
        algo = r['algorithm']
        
        if config_key not in by_config:
            by_config[config_key] = {}
        
        if obj_type not in by_config[config_key]:
            by_config[config_key][obj_type] = {}
        
        if algo not in by_config[config_key][obj_type]:
            by_config[config_key][obj_type][algo] = []
        
        by_config[config_key][obj_type][algo].append(r)
    
    # Calculate statistics for each group
    structured_data = {}
    
    for config_key in sorted(by_config.keys()):
        structured_data[config_key] = {}
        
        for obj_type in sorted(by_config[config_key].keys()):
            structured_data[config_key][obj_type] = {}
            
            for algo in sorted(by_config[config_key][obj_type].keys()):
                runs = by_config[config_key][obj_type][algo]
                
                objectives = [r['objective'] for r in runs]
                runtimes = [r['runtime'] for r in runs]
                
                avg_obj = sum(objectives) / len(objectives)
                avg_runtime = sum(runtimes) / len(runtimes)
                
                stdev_obj = (sum((x - avg_obj)**2 for x in objectives) / len(objectives))**0.5 if len(objectives) > 1 else 0
                stdev_runtime = (sum((x - avg_runtime)**2 for x in runtimes) / len(runtimes))**0.5 if len(runtimes) > 1 else 0
                
                structured_data[config_key][obj_type][algo] = {
                    'num_runs': len(runs),
                    'avg_cost': round(avg_obj, 2),
                    'stdev_cost': round(stdev_obj, 2),
                    'avg_runtime': round(avg_runtime, 4),
                    'stdev_runtime': round(stdev_runtime, 4)
                }
    
    # Write to file
    with open(output_file, 'w') as f:
        json.dump(structured_data, f, indent=2)


def print_final_summary(all_results, output_dir):
    """Print and save final summary across all scales."""
    print(f"\n{'='*80}")
    print("FINAL SUMMARY - ALL SCALES")
    print(f"{'='*80}\n")
    
    # Group by scale and algorithm
    by_scale = {}
    for r in all_results:
        scale = r['scale']
        if scale not in by_scale:
            by_scale[scale] = {}
        algo = r['algorithm']
        if algo not in by_scale[scale]:
            by_scale[scale][algo] = []
        by_scale[scale][algo].append(r)
    
    for scale in sorted(by_scale.keys()):
        print(f"\n{scale.upper()} Scale:")
        print("-" * 60)
        
        for algo in sorted(by_scale[scale].keys()):
            results = by_scale[scale][algo]
            objectives = [r['objective'] for r in results]
            runtimes = [r['runtime'] for r in results]
            
            print(f"  {algo:25s}: Runs={len(results):3d}, "
                  f"Obj={sum(objectives)/len(objectives):.2f}±{(sum((x-sum(objectives)/len(objectives))**2 for x in objectives)/len(objectives))**0.5:.2f}, "
                  f"Time={sum(runtimes)/len(runtimes):.3f}±{(sum((x-sum(runtimes)/len(runtimes))**2 for x in runtimes)/len(runtimes))**0.5:.3f}s")
    
    # Save combined summary JSON
    with open(output_dir / 'combined_summary.json', 'w') as f:
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_experiments': len(all_results),
            'by_scale': {scale: {
                algo: {
                    'num_runs': len(results),
                    'avg_objective': sum(r['objective'] for r in results) / len(results),
                    'avg_runtime': sum(r['runtime'] for r in results) / len(results)
                } for algo, results in algos.items()
            } for scale, algos in by_scale.items()}
        }
        json.dump(summary, f, indent=2)
    
    print(f"✓ Combined JSON written to: {output_dir / 'combined_summary.json'}")
    
    print(f"\n{'='*80}")
    print(f"✓ All experiments completed!")
    print(f"  Total experiments: {len(all_results)}")
    print(f"  Results directory: {output_dir.absolute()}")
    print(f"{'='*80}\n")

def main():
    parser = argparse.ArgumentParser(description='Run systematic MDSSP experiments across multiple scales')
    parser.add_argument('--scales', nargs='+', choices=['1d', 'small', 'medium', 'large', 'structured', '2d_covering', '2d_covering_original', 'all'],
                       default=['all'], help='Which scales to run (default: all). Use "structured" for reassembly experiments, "2d_covering" for cycling string experiments, "2d_covering_original" for multi-string format.')
    parser.add_argument('--seed', type=int, default=42, help='Base random seed (default: 42)')
    parser.add_argument('--output-dir', type=str, default='experiments',
                       help='Output directory for all results (default: experiments)')
    parser.add_argument('--objective-type', type=str, choices=['square', 'area'],
                       help='Override objective type for all scales (square=max(H,W), area=H*W)')
    parser.add_argument('--alphabet-size', type=int,
                       help='Override alphabet size for all scales (2=binary, higher for larger alphabets)')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be run without executing')
    parser.add_argument('--no-resume', action='store_true', 
                       help='Disable resume mode (run all experiments even if already completed)')
    parser.add_argument('--structured', action='store_true',
                       help='Run structured/reassembly experiments only (equivalent to --scales structured)')
    parser.add_argument('--2d-covering', dest='twod_covering', action='store_true',
                       help='Run 2D covering experiments only (equivalent to --scales 2d_covering)')
    parser.add_argument('--2d-covering-original', dest='twod_covering_original', action='store_true',
                       help='Run 2D covering original experiments only (equivalent to --scales 2d_covering_original)')
    parser.add_argument('--covering-file', type=str, default='2d_covering.txt',
                       help='Input file for 2D covering experiments (default: 2d_covering.txt)')
    parser.add_argument('--covering-dir', type=str, default='2d_covering_dataset',
                       help='Input directory for 2D covering original experiments (default: 2d_covering_dataset)')
    parser.add_argument('--patterns', type=str, nargs='+',
                       choices=['qrcode', 'random', 'checkerboard', 'stripes_h', 'stripes_v', 'diagonal', 'blocks', 'gradient', 'sparse', 'dense'],
                       help='Override patterns for structured experiments (default: use config patterns)')
    
    args = parser.parse_args()
    
    resume_mode = not args.no_resume
    
    # Handle --structured, --2d-covering, and --2d-covering-original flags
    if args.structured:
        scales_to_run = ['structured']
    elif args.twod_covering:
        scales_to_run = ['2d_covering']
    elif args.twod_covering_original:
        scales_to_run = ['2d_covering_original']
    elif 'all' in args.scales:
        scales_to_run = ['small', 'medium', 'large']
    else:
        scales_to_run = args.scales
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Check if resuming from previous run
    metadata_file = output_dir / 'experiment_metadata.json'
    if resume_mode and metadata_file.exists():
        with open(metadata_file, 'r') as f:
            prev_metadata = json.load(f)
        print(f"\n{'='*80}")
        print(f"RESUMING FROM PREVIOUS RUN")
        print(f"{'='*80}")
        print(f"Previous run started: {prev_metadata.get('timestamp', 'unknown')}")
        print(f"Scales: {prev_metadata.get('scales', [])}")
        print(f"Base seed: {prev_metadata.get('base_seed', 'unknown')}")
        print(f"Resume mode: ENABLED - Will skip completed experiments")
        print(f"{'='*80}\n")
    
    # Save experiment metadata
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'scales': scales_to_run,
        'base_seed': args.seed,
        'resume_mode': resume_mode,
        'configurations': {scale: EXPERIMENTS[scale] for scale in scales_to_run}
    }
    with open(output_dir / 'experiment_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    if args.dry_run:
        print("DRY RUN - Would execute:")
        for scale in scales_to_run:
            config = EXPERIMENTS[scale]
            print(f"\n{scale.upper()}:")
            if scale == '2d_covering_original':
                # 2D covering original dry run
                data_dir = Path(args.covering_dir if hasattr(args, 'covering_dir') else config.get('data_dir', '2d_covering_dataset'))
                objective_types = config.get('objective_types', [config.get('objective_type', 'area')])
                print(f"  Data directory: {data_dir}")
                print(f"  Objective types: {objective_types}")
                if data_dir.exists():
                    txt_files = sorted(data_dir.glob('*.txt'))
                    txt_files = [f for f in txt_files if f.stem != 'input' and '_' in f.stem]
                    print(f"  Data files: {len(txt_files)}")
                    for tf in txt_files:
                        try:
                            parsed = parse_2d_covering_original_file(tf)
                            total = config.get('runs', 1) * len(config['algorithms']) * len(objective_types)
                            print(f"    {tf.name}: n={parsed['n']}, m={parsed['m']}, r={parsed['r']}, L={parsed['L']}, input_strings={parsed['num_input_strings']}: {total} experiments")
                        except Exception as e:
                            print(f"    {tf.name}: ERROR - {e}")
                else:
                    print(f"  WARNING: Data directory not found: {data_dir}")
            elif scale == '2d_covering':
                # 2D covering dry run
                data_file = args.covering_file if hasattr(args, 'covering_file') else config.get('data_file', '2d_covering.txt')
                objective_types = config.get('objective_types', [config.get('objective_type', 'area')])
                print(f"  Data file: {data_file}")
                print(f"  Objective types: {objective_types}")
                if Path(data_file).exists():
                    test_cases = parse_2d_covering_file(data_file)
                    print(f"  Test cases: {len(test_cases)}")
                    for tc in test_cases:
                        # Multiply by number of objective types
                        total = config.get('runs', 1) * len(config['algorithms']) * len(objective_types)
                        print(f"    Case {tc['case_id']}: n={tc['n']}, m={tc['m']}, r={tc['r']}, L={tc['L']}: {total} experiments")
                else:
                    print(f"  WARNING: Data file not found: {data_file}")
            elif config.get('structured'):
                # Structured experiment dry run
                pattern_list = args.patterns if args.patterns else config.get('patterns', ['random'])
                print(f"  Patterns: {pattern_list}")
                for pattern in pattern_list:
                    print(f"  Pattern '{pattern}':")
                    for (src_h, src_w) in config['source_sizes']:
                        for (n, m) in config['tile_size']:
                            for num_tiles in config['num_tiles']:
                                total = config['runs'] * len(config['algorithms'])
                                print(f"    Source={src_h}x{src_w}, T={num_tiles}, tile={n}x{m}: {total} experiments")
            elif 'tiles' in config:
                # Standard experiment dry run
                for tiles in config['tiles']:
                    for (n, m) in config['tile_size']:
                        total = config['runs'] * len(config['algorithms'])
                        print(f"  T={tiles}, n={n}, m={m}: {total} experiments")
            else:
                print(f"  Unknown config format for scale '{scale}'")
        return
    
    # Run experiments for each scale
    all_results = []
    start_time = time.time()
    
    for scale in scales_to_run:
        config = EXPERIMENTS[scale].copy()
        # Override objective type if specified
        if args.objective_type:
            config['objective_type'] = args.objective_type
        
        # Override alphabet size if specified
        if args.alphabet_size:
            config['alphabet_size'] = args.alphabet_size
        
        # Check the type of experiment
        if scale == '2d_covering_original':
            # Override data dir if specified
            if args.covering_dir:
                config['data_dir'] = args.covering_dir
            results, best, summary = run_2d_covering_original_experiment_suite(
                scale, config, args.seed, output_dir, 
                resume=resume_mode
            )
        elif scale == '2d_covering':
            # Override data file if specified
            if args.covering_file:
                config['data_file'] = args.covering_file
            results, best, summary = run_2d_covering_experiment_suite(
                scale, config, args.seed, output_dir, 
                resume=resume_mode
            )
        elif config.get('structured'):
            # Override patterns if specified via command line
            patterns = args.patterns if args.patterns else None
            results, best, summary = run_structured_experiment_suite(
                scale, config, args.seed, output_dir, 
                resume=resume_mode, patterns=patterns
            )
        else:
            results, best, summary = run_experiment_suite(
                scale, config, args.seed, output_dir, 
                resume=resume_mode
            )
        all_results.extend(results)
    
    # Reload ALL results from output directory for accurate combined CSV and JSON
    print(f"\n{'='*80}")
    print("RECALCULATING COMBINED RESULTS FROM ALL SCALES")
    print(f"{'='*80}")
    all_results = load_all_results_from_directory(output_dir)
    print(f"Total results loaded: {len(all_results)}")
    print(f"{'='*80}\n")
    
    # Write combined CSV with all results
    if all_results:
        write_results_to_csv(all_results, output_dir / 'combined_all_results.csv')
        print(f"✓ Combined CSV written to: {output_dir / 'combined_all_results.csv'}")
        
        # Write aggregated statistics CSV
        write_aggregated_stats_csv(all_results, output_dir / 'aggregated_statistics.csv')
        print(f"✓ Aggregated statistics CSV written to: {output_dir / 'aggregated_statistics.csv'}")
        
        # Write structured comparison JSON
        write_structured_comparison_json(all_results, output_dir / 'comparison_by_config.json')
        print(f"✓ Structured comparison JSON written to: {output_dir / 'comparison_by_config.json'}")
        
        # Recalculate and save combined summary JSON
        print_final_summary(all_results, output_dir)
    
    # Print execution time
    total_time = time.time() - start_time
    print(f"Total execution time: {total_time/60:.1f} minutes")

if __name__ == '__main__':
    main()
