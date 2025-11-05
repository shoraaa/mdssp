#!/usr/bin/env python3
"""
Generate dataset file for MDSSP from cyclic substrings.

This script takes binary strings, generates cyclic substrings of length 9,
converts them to 3x3 tiles, and outputs them in JSON format compatible with mdssp.cpp
"""

import json

# Source binary strings
sources = [
    "1000010000",
    "0001001101",
    "1001111001",
    "1111010111",
    "1010101010",
    "0101011000",
    "0110111001",
    "0111010000",
]

def cyclic_substrings(s, k=9):
    """Generate all cyclic substrings of length k from string s."""
    doubled = s + s
    return [doubled[i:i+k] for i in range(len(s))]

def substr_to_tile(sub):
    """Convert a substring of length 9 to a 3x3 tile (list of lists)."""
    return [[int(ch) for ch in sub[r*3:(r+1)*3]] for r in range(3)]

def main():
    """Main function to generate dataset."""
    # Generate all tiles
    selected_tiles = []
    for s in sources:
        for sub in cyclic_substrings(s, 9):
            selected_tiles.append(substr_to_tile(sub))

    print(f"Generated {len(selected_tiles)} tiles from {len(sources)} source strings")
    print(f"Each tile is 3x3")

    # Output to file in JSON format
    output_file = "dataset.json"
    dataset = {
        "num_tiles": len(selected_tiles),
        "tile_height": 3,
        "tile_width": 3,
        "tiles": selected_tiles
    }

    with open(output_file, 'w') as f:
        json.dump(dataset, f, indent=2)

    print(f"\nDataset written to '{output_file}'")
    print(f"\nFirst 3 tiles:")
    for i in range(min(3, len(selected_tiles))):
        print(f"\nTile {i}:")
        for row in selected_tiles[i]:
            print("  ", " ".join(map(str, row)))

    print(f"\nTotal tiles: {len(selected_tiles)}")
    print(f"Dataset format: JSON")

if __name__ == "__main__":
    main()


