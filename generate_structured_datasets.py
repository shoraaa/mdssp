#!/usr/bin/env python3
"""
Generate structured datasets for MDSSP experiments.

This script pre-generates all structured experiment datasets with:
- 100% pixel coverage using greedy random sampling
- Reproducible seeds for each configuration
- Datasets saved to experiment_structural/datasets/

Usage:
    python generate_structured_datasets.py [options]

Options:
    --output-dir DIR    Output directory (default: experiment_structural)
    --seed SEED         Base random seed (default: 42)
    --patterns P1,P2    Comma-separated patterns (default: all)
    --sizes S1,S2       Comma-separated sizes like 14x14,36x36 (default: all)
    --tile-size NxM     Tile size (default: 3x3)
    --dry-run           Show what would be generated without creating files
"""

import argparse
import json
import random
from pathlib import Path
from datetime import datetime


# ============================================================================
# Pattern Generation (copied from systematic_experiments.py for standalone use)
# ============================================================================

def generate_source_bitmap(height, width, seed, pattern='random', alphabet_size=2):
    """Generate a source bitmap with values from 0 to alphabet_size-1."""
    rng = random.Random(seed)
    
    if pattern == 'random':
        return [[rng.randint(0, alphabet_size - 1) for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'checkerboard':
        return [[(i + j) % alphabet_size for j in range(width)] for i in range(height)]
    
    elif pattern == 'stripes_h':
        return [[i % alphabet_size for _ in range(width)] for i in range(height)]
    
    elif pattern == 'stripes_v':
        return [[j % alphabet_size for j in range(width)] for _ in range(height)]
    
    elif pattern == 'diagonal':
        return [[(i + j) % alphabet_size for j in range(width)] for i in range(height)]
    
    elif pattern == 'blocks':
        block_size = 4
        return [[((i // block_size) + (j // block_size)) % alphabet_size
                 for j in range(width)] for i in range(height)]
    
    elif pattern == 'gradient':
        def gradient_val(i, j):
            prob = 1 - (i + j) / (height + width)
            return int(prob * (alphabet_size - 1) + rng.random())
        return [[min(gradient_val(i, j), alphabet_size - 1) for j in range(width)] for i in range(height)]
    
    elif pattern == 'sparse':
        return [[rng.randint(1, alphabet_size - 1) if rng.random() < 0.25 else 0 for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'dense':
        return [[rng.randint(1, alphabet_size - 1) if rng.random() < 0.75 else 0 for _ in range(width)] for _ in range(height)]
    
    elif pattern == 'qrcode':
        bitmap = [[0 for _ in range(width)] for _ in range(height)]
        
        def draw_finder(r0, c0):
            for i in range(7):
                for j in range(7):
                    if r0 + i < height and c0 + j < width:
                        if i == 0 or i == 6 or j == 0 or j == 6:
                            bitmap[r0 + i][c0 + j] = alphabet_size - 1
                        elif i == 1 or i == 5 or j == 1 or j == 5:
                            bitmap[r0 + i][c0 + j] = 0
                        else:
                            bitmap[r0 + i][c0 + j] = alphabet_size - 1
        
        draw_finder(0, 0)
        draw_finder(0, width - 7)
        draw_finder(height - 7, 0)
        
        if height > 6:
            for j in range(8, width - 8):
                bitmap[6][j] = (j % alphabet_size)
        
        if width > 6:
            for i in range(8, height - 8):
                bitmap[i][6] = (i % alphabet_size)
        
        for i in range(height):
            for j in range(width):
                in_finder = ((i < 8 and j < 8) or
                            (i < 8 and j >= width - 8) or
                            (i >= height - 8 and j < 8))
                in_timing = (i == 6 and 8 <= j < width - 8) or (j == 6 and 8 <= i < height - 8)
                
                if not in_finder and not in_timing:
                    bitmap[i][j] = rng.randint(0, alphabet_size - 1)
        
        return bitmap
    
    else:
        return [[rng.randint(0, alphabet_size - 1) for _ in range(width)] for _ in range(height)]


def extract_subarrays_full_coverage(bitmap, tile_height, tile_width, seed, num_overlap=100):
    """
    Extract subarrays with two-phase strategy:
    1. Base set: Non-overlapping grid positions (minimal tiles for 100% coverage)
    2. Overlap set: Randomly sample additional tiles that add overlaps
    
    Args:
        bitmap: Source bitmap
        tile_height, tile_width: Tile dimensions
        seed: Random seed
        num_overlap: Fixed number of overlapping tiles to add
    """
    rng = random.Random(seed)
    
    src_height = len(bitmap)
    src_width = len(bitmap[0]) if bitmap else 0
    
    max_row = src_height - tile_height
    max_col = src_width - tile_width
    
    if max_row < 0 or max_col < 0:
        raise ValueError(f"Tile size ({tile_height}×{tile_width}) larger than source ({src_height}×{src_width})")
    
    tiles = []
    selected_positions = []
    used_positions = set()
    
    # Phase 1: Non-overlapping grid positions for base coverage
    # Positions at multiples of tile size
    base_positions = []
    for row in range(0, src_height, tile_height):
        for col in range(0, src_width, tile_width):
            # Clamp to valid range
            actual_row = min(row, max_row)
            actual_col = min(col, max_col)
            if (actual_row, actual_col) not in used_positions:
                base_positions.append((actual_row, actual_col))
                used_positions.add((actual_row, actual_col))
    
    # Shuffle base positions for randomness, then add them
    rng.shuffle(base_positions)
    for row, col in base_positions:
        tile = [[bitmap[row + i][col + j] for j in range(tile_width)] 
                for i in range(tile_height)]
        tiles.append(tile)
        selected_positions.append((row, col))
    
    base_count = len(tiles)
    
    # Phase 2: Randomly sample additional overlapping tiles
    # Get all remaining positions
    remaining_positions = [(row, col) 
                          for row in range(max_row + 1) 
                          for col in range(max_col + 1)
                          if (row, col) not in used_positions]
    
    # Shuffle and sample fixed number of overlap tiles
    rng.shuffle(remaining_positions)
    actual_overlap = min(num_overlap, len(remaining_positions))
    overlap_positions = remaining_positions[:actual_overlap]
    
    for row, col in overlap_positions:
        tile = [[bitmap[row + i][col + j] for j in range(tile_width)] 
                for i in range(tile_height)]
        tiles.append(tile)
        selected_positions.append((row, col))
    
    return tiles, selected_positions, base_count


def generate_dataset(source_height, source_width, tile_height, tile_width,
                     seed, pattern, alphabet_size=2, num_overlap=100):
    """Generate a complete dataset with metadata."""
    
    # Generate source bitmap
    bitmap = generate_source_bitmap(source_height, source_width, seed, pattern, alphabet_size)
    
    # Extract tiles with 100% coverage (use seed+1000 for extraction randomness)
    tiles, positions, base_count = extract_subarrays_full_coverage(
        bitmap, tile_height, tile_width, seed + 1000, num_overlap
    )
    
    # Calculate statistics
    total_positions = (source_height - tile_height + 1) * (source_width - tile_width + 1)
    
    dataset = {
        "num_tiles": len(tiles),
        "tile_height": tile_height,
        "tile_width": tile_width,
        "alphabet_size": alphabet_size,
        "tiles": tiles,
        "structured_metadata": {
            "source_height": source_height,
            "source_width": source_width,
            "optimal_area": source_height * source_width,
            "pattern": pattern,
            "alphabet_size": alphabet_size,
            "seed": seed,
            "full_coverage": True,
            "total_possible_positions": total_positions,
            "base_tiles": base_count,
            "overlap_tiles": len(tiles) - base_count,
            "selected_tiles": len(tiles),
            "num_overlap_requested": num_overlap,
            "coverage_efficiency": len(tiles) / total_positions if total_positions > 0 else 0,
            "extraction_positions": positions  # Store which positions were selected
        }
    }
    
    return dataset, bitmap


def main():
    parser = argparse.ArgumentParser(description='Generate structured datasets for MDSSP experiments')
    parser.add_argument('--output-dir', type=str, default='experiment_structural',
                        help='Output directory (default: experiment_structural)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Base random seed (default: 42)')
    parser.add_argument('--patterns', type=str, default=None,
                        help='Comma-separated patterns (default: all)')
    parser.add_argument('--sizes', type=str, default=None,
                        help='Comma-separated sizes like 14x14,36x36 (default: all)')
    parser.add_argument('--tile-size', type=str, default='4x4',
                        help='Tile size NxM (default: 4x4)')
    parser.add_argument('--alphabet-size', type=int, default=2,
                        help='Alphabet size (default: 2)')
    parser.add_argument('--num-overlap', type=int, default=100,
                        help='Fixed number of overlapping tiles to add (default: 100)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be generated without creating files')
    parser.add_argument('--save-bitmap', action='store_true',
                        help='Also save source bitmap as JSON')
    
    args = parser.parse_args()
    
    # Parse tile size
    tile_parts = args.tile_size.split('x')
    tile_height, tile_width = int(tile_parts[0]), int(tile_parts[1])
    
    # Default patterns
    all_patterns = ['qrcode', 'random', 'checkerboard', 'stripes_h', 'stripes_v', 
                    'diagonal', 'blocks', 'gradient', 'sparse', 'dense']
    
    if args.patterns:
        patterns = [p.strip() for p in args.patterns.split(',')]
    else:
        patterns = all_patterns
    
    # Default sizes
    all_sizes = [(14, 14), (36, 36), (64, 64)]
    
    if args.sizes:
        sizes = []
        for s in args.sizes.split(','):
            parts = s.strip().split('x')
            sizes.append((int(parts[0]), int(parts[1])))
    else:
        sizes = all_sizes
    
    # Create output directory
    output_dir = Path(args.output_dir)
    datasets_dir = output_dir / 'datasets'
    
    if not args.dry_run:
        datasets_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"{'='*70}")
    print(f"STRUCTURED DATASET GENERATOR")
    print(f"{'='*70}")
    print(f"Output directory: {datasets_dir}")
    print(f"Base seed: {args.seed}")
    print(f"Tile size: {tile_height}×{tile_width}")
    print(f"Alphabet size: {args.alphabet_size}")
    print(f"Overlap tiles: {args.num_overlap}")
    print(f"Patterns: {', '.join(patterns)}")
    print(f"Sizes: {', '.join(f'{h}x{w}' for h, w in sizes)}")
    print(f"Dry run: {args.dry_run}")
    print()
    
    # Track statistics
    total_datasets = 0
    total_tiles = 0
    
    # Generate datasets
    for src_h, src_w in sizes:
        print(f"\n--- Source size: {src_h}×{src_w} ---")
        
        for pattern in patterns:
            # Each pattern gets a unique seed offset
            pattern_seed = args.seed + hash(pattern) % 10000
            
            dataset, bitmap = generate_dataset(
                src_h, src_w, tile_height, tile_width,
                pattern_seed, pattern, args.alphabet_size, args.num_overlap
            )
            
            num_tiles = dataset['num_tiles']
            base_tiles = dataset['structured_metadata']['base_tiles']
            overlap_tiles = dataset['structured_metadata']['overlap_tiles']
            total_positions = dataset['structured_metadata']['total_possible_positions']
            optimal_area = dataset['structured_metadata']['optimal_area']
            
            print(f"  {pattern:12s}: {num_tiles:4d} tiles ({base_tiles} base + {overlap_tiles} overlap, "
                  f"from {total_positions:4d} positions, optimal_area={optimal_area})")
            
            if not args.dry_run:
                # Create pattern subdirectory
                pattern_dir = datasets_dir / f"src{src_h}x{src_w}" / pattern
                pattern_dir.mkdir(parents=True, exist_ok=True)
                
                # Save dataset
                dataset_file = pattern_dir / "dataset.json"
                with open(dataset_file, 'w') as f:
                    json.dump(dataset, f, indent=2)
                
                # Optionally save bitmap
                if args.save_bitmap:
                    bitmap_file = pattern_dir / "source_bitmap.json"
                    with open(bitmap_file, 'w') as f:
                        json.dump({
                            "height": src_h,
                            "width": src_w,
                            "pattern": pattern,
                            "seed": pattern_seed,
                            "bitmap": bitmap
                        }, f, indent=2)
            
            total_datasets += 1
            total_tiles += num_tiles
    
    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Total datasets: {total_datasets}")
    print(f"Total tiles across all datasets: {total_tiles}")
    print(f"Average tiles per dataset: {total_tiles / total_datasets:.1f}")
    
    if not args.dry_run:
        # Save metadata
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "base_seed": args.seed,
            "tile_size": [tile_height, tile_width],
            "alphabet_size": args.alphabet_size,
            "patterns": patterns,
            "source_sizes": sizes,
            "total_datasets": total_datasets,
            "total_tiles": total_tiles
        }
        
        with open(datasets_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\nDatasets saved to: {datasets_dir}")
        print(f"Metadata saved to: {datasets_dir / 'metadata.json'}")
    else:
        print(f"\n(Dry run - no files created)")


if __name__ == '__main__':
    main()
