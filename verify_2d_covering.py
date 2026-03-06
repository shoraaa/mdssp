import json
import os
import glob
import re
from itertools import product

def hamming_distance(t1, t2, R):
    dist = 0
    for r1, r2 in zip(t1, t2):
        for c1, c2 in zip(r1, r2):
            if c1 != c2:
                dist += 1
                if dist > R:
                    return dist
    return dist

def verify_instance(json_path):
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Extract R from the directory name, typically m_n_R_size (e.g., 2_5_1_175)
    dir_name = os.path.basename(os.path.dirname(json_path))
    match = re.search(r'^\d+_\d+_(\d+)_', dir_name)
    if match:
        R = int(match.group(1))
    else:
        R = 0 # Default to exact match if not parseable

    dataset_file = data.get("input", {}).get("dataset_file")
    if not dataset_file or not os.path.exists(dataset_file):
        # Fallback to local directory if absolute/relative path from dataset fails
        dataset_file = os.path.join(os.path.dirname(json_path), "dataset.json")
    
    if not os.path.exists(dataset_file):
        return {"error": f"Cannot find dataset file: {dataset_file}"}

    with open(dataset_file, 'r') as f:
        dataset = json.load(f)

    tile_height = dataset["tile_height"]
    tile_width = dataset["tile_width"]
    
    # Flatten tiles from dataset to sets of strings/tuples for fast lookup
    dataset_tiles = set()
    for tile in dataset["tiles"]:
        # tile is a list of lists of ints
        # Convert to tuple of tuples for hashability
        stringified_tile = tuple(tuple(row) for row in tile)
        dataset_tiles.add(stringified_tile)

    alphabet_size = dataset.get("alphabet_size", 2)
    # We only assume binary strings
    assert alphabet_size == 2
    
    required_full_coverage_count = 2 ** (tile_height * tile_width)

    # Let's verify all results in the json file
    verifications = []

    for result in data.get("results", []):
        algorithm = result.get("algorithm", "unknown")
        
        # We need the canvas or the placements. Let's build the canvas from placements
        # It's safer to build from placements since the canvas string format in JSON might be 1D serialized
        placements = result.get("placements")
        
        if not placements:
            verifications.append({"algorithm": algorithm, "error": "No placements found."})
            continue
            
        bbox_height = result.get("bbox_height", 0)
        bbox_width = result.get("bbox_width", 0)
        
        # Calculate coordinate offsets because placements can have negative coordinates
        min_x = min([p["x"] for p in placements] + [0])
        min_y = min([p["y"] for p in placements] + [0])

        offset_x = -min_x
        offset_y = -min_y

        # Note: sometimes bbox_width/height are exact, but with offsets we might need slightly larger 
        # actual bounds if max_x + tile_width > min_x + bbox_width. So we can re-compute them safely.
        max_x = max(p["x"] for p in placements)
        max_y = max(p["y"] for p in placements)
        
        actual_width = (max_x + tile_width) - min_x
        actual_height = (max_y + tile_height) - min_y
        
        # Using actual computed dimensions to prevent out of bounds
        canvas = [[-1 for _ in range(actual_width)] for _ in range(actual_height)]

        valid_placement = True
        for p in placements:
            tid = p["tile_id"]
            x = p["x"] + offset_x
            y = p["y"] + offset_y
            
            # bounds check
            if y < 0 or y + tile_height > actual_height or x < 0 or x + tile_width > actual_width:
                valid_placement = False
                break
                
            tile = dataset["tiles"][tid]
            
            for ty in range(tile_height):
                for tx in range(tile_width):
                    val = tile[ty][tx]
                    existing = canvas[y + ty][x + tx]
                    if existing != -1 and existing != val:
                        # Conflict!
                        valid_placement = False
                        break
                    canvas[y + ty][x + tx] = val
                if not valid_placement:
                    break
            if not valid_placement:
                 break
        
        if not valid_placement:
            verifications.append({
                "algorithm": algorithm,
                "valid": False,
                "reason": "Placements conflict or out of bounds."
            })
            continue

        extracted_tiles = set()
        for y in range(actual_height - tile_height + 1):
            for x in range(actual_width - tile_width + 1):
                # Check if this crop has holes
                has_hole = False
                crop = []
                for cy in range(tile_height):
                    row = []
                    for cx in range(tile_width):
                        val = canvas[y + cy][x + cx]
                        if val == -1:
                            has_hole = True
                            break
                        row.append(val)
                    if has_hole:
                        break
                    crop.append(tuple(row))
                
                if not has_hole:
                    extracted_tiles.add(tuple(crop))

        solution_valid = True
        for t in dataset_tiles:
            if t not in extracted_tiles:
                solution_valid = False
                break
        
        # Generate all possible 2^(m*n) target matrices
        all_possible = []
        for bits in product([0, 1], repeat=tile_height * tile_width):
            tile = []
            for r in range(tile_height):
                tile.append(tuple(bits[r * tile_width:(r + 1) * tile_width]))
            all_possible.append(tuple(tile))

        hypothesis_valid = True
        missing_radius_coverage = 0
        
        for target in all_possible:
            covered = False
            for ext in extracted_tiles:
                if hamming_distance(target, ext, R) <= R:
                    covered = True
                    break
            if not covered:
                hypothesis_valid = False
                missing_radius_coverage += 1

        verifications.append({
            "algorithm": algorithm,
            "solution_valid": solution_valid,
            "dataset_tiles_missing_count": len(dataset_tiles) - sum(1 for t in dataset_tiles if t in extracted_tiles),
            "hypothesis_valid": hypothesis_valid,
            "missing_radius_coverage": missing_radius_coverage,
            "unique_extracted_count": len(extracted_tiles),
            "expected_total_count": required_full_coverage_count,
            "actual_area": actual_width * actual_height,
            "reported_area": bbox_width * bbox_height,
            "R": R
        })

    return {"file": json_path, "results": verifications}

def main():
    base_dir = "experiments/2d_covering_original"
    if not os.path.exists(base_dir):
        print(f"Directory {base_dir} not found.")
        return

    json_files = glob.glob(os.path.join(base_dir, "**", "*.json"), recursive=True)
    
    # filter out dataset.json and summary files
    test_files = [f for f in json_files if "run_" in os.path.basename(f) and not "summary" in os.path.basename(f)]
    
    print(f"Found {len(test_files)} runs to verify.\n")
    
    all_verifications = []
    
    for f in test_files:
        try:
            res = verify_instance(f)
            all_verifications.append(res)
        except Exception as e:
            all_verifications.append({"file": f, "error": str(e)})

    # Print summary
    total_runs = 0
    total_solution_valid = 0
    total_hypothesis_valid = 0
    total_errors = 0

    for item in all_verifications:
        err = item.get("error")
        if err:
            print(f"[{item['file']}] ERROR: {err}")
            total_errors += 1
            continue
            
        print(f"[{item['file']}]")
        for res in item["results"]:
            total_runs += 1
            algo = res.get("algorithm", "-")
            if "error" in res or res.get("valid") is False:
                print(f"  Algo: {algo} - INVALID ({res.get('error') or res.get('reason')})")
                total_errors += 1
            else:
                s_valid = res["solution_valid"]
                h_valid = res["hypothesis_valid"]
                if s_valid:
                    total_solution_valid += 1
                if h_valid:
                    total_hypothesis_valid += 1
                
                print(f"  Algo: {algo} - Actual Area: {res['actual_area']} (Reported: {res['reported_area']})")
                print(f"    Solution Valid: {s_valid} (Missing: {res['dataset_tiles_missing_count']})")
                if h_valid:
                    print(f"    Hypothesis Valid: True (Covered all {res['expected_total_count']} with R={res.get('R', 0)})")
                else:
                    print(f"    Hypothesis Valid: False (Missing {res['missing_radius_coverage']}/{res['expected_total_count']} with R={res.get('R', 0)})")
        print()

    print("=" * 40)
    print("VERIFICATION SUMMARY")
    print("=" * 40)
    print(f"Total runs analyzed: {total_runs}")
    print(f"Total errors:        {total_errors}")
    print(f"Solution Valid:      {total_solution_valid} / {total_runs}")
    print(f"Hypothesis Valid:    {total_hypothesis_valid} / {total_runs}")


if __name__ == "__main__":
    main()
