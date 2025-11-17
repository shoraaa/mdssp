#!/usr/bin/env python3
"""Quick test for CSV output functionality."""

import json
import subprocess
from pathlib import Path
import csv

# Create a minimal test dataset
test_dir = Path('experiments/csv_test')
test_dir.mkdir(parents=True, exist_ok=True)

# Run a quick test
print("Running quick CSV test...")
cmd = [
    './mdssp',
    '-a', 'genetic_greedy',
    '-T', '6',
    '-n', '3',
    '-m', '3',
    '-s', '42',
    '--pop-size', '10',
    '--generations', '5',
    '-o', str(test_dir / 'result.json')
]

result = subprocess.run(cmd, capture_output=True, text=True)

# Load and display the JSON
if (test_dir / 'result.json').exists():
    with open(test_dir / 'result.json', 'r') as f:
        data = json.load(f)
    
    # Extract result
    if 'results' in data and len(data['results']) > 0:
        r = data['results'][0]
        
        # Write to CSV
        csv_file = test_dir / 'test_results.csv'
        fieldnames = ['algorithm', 'objective', 'bbox_width', 'bbox_height', 
                      'runtime_seconds', 'num_tiles_placed',
                      'total_crossovers', 'crossovers_needing_completion', 
                      'total_tiles_completed', 'completion_rate']
        
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            row = {
                'algorithm': r.get('algorithm', 'N/A'),
                'objective': r.get('objective', 'N/A'),
                'bbox_width': r.get('bbox_width', 'N/A'),
                'bbox_height': r.get('bbox_height', 'N/A'),
                'runtime_seconds': r.get('runtime_seconds', 'N/A'),
                'num_tiles_placed': r.get('num_tiles_placed', 'N/A'),
                'total_crossovers': r.get('total_crossovers', 'N/A'),
                'crossovers_needing_completion': r.get('crossovers_needing_completion', 'N/A'),
                'total_tiles_completed': r.get('total_tiles_completed', 'N/A'),
            }
            
            if r.get('total_crossovers'):
                row['completion_rate'] = r['crossovers_needing_completion'] / r['total_crossovers']
            else:
                row['completion_rate'] = 'N/A'
            
            writer.writerow(row)
        
        print(f"\n✓ CSV written to: {csv_file}")
        print("\nCSV Contents:")
        with open(csv_file, 'r') as f:
            print(f.read())
    else:
        print("No results found in JSON")
else:
    print("Result file not created")
