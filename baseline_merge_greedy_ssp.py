#!/usr/bin/env python3
import argparse
import json
import random
import time
from typing import Dict, List, Tuple

def gen_random_binary_strings(T: int, m: int, seed: int) -> List[str]:
    rng = random.Random(seed)
    return ["".join(rng.choice("01") for _ in range(m)) for _ in range(T)]

def overlap(a: str, b: str) -> int:
    """Max k s.t. suffix(a,k) == prefix(b,k)."""
    max_k = min(len(a), len(b))
    for k in range(max_k, 0, -1):
        if a[-k:] == b[:k]:
            return k
    return 0

def is_substring(s: str, t: str) -> int:
    """Return position of s in t if s is substring of t, else -1."""
    return t.find(s)

def prune_substrings(strings: List[Tuple[str, Dict[int, int]]]) -> List[Tuple[str, Dict[int, int]]]:
    """
    Remove strings that are substrings of others; preserve placements by
    adding them into the container's placement map.
    Each item is (superstring, placements_map original_id -> offset).
    """
    kept = []
    removed = set()

    for i in range(len(strings)):
        if i in removed:
            continue
        si, mi = strings[i]
        for j in range(len(strings)):
            if i == j or j in removed:
                continue
            sj, mj = strings[j]
            pos = is_substring(si, sj)
            if pos != -1:
                # si contained in sj: transfer placements from si into sj with shift pos
                for oid, off in mi.items():
                    mj[oid] = pos + off
                removed.add(i)
                break

    for idx, item in enumerate(strings):
        if idx not in removed:
            kept.append(item)
    return kept

def greedy_merge(strings: List[Tuple[str, Dict[int, int]]]) -> Tuple[str, Dict[int, int]]:
    """Standard greedy SSSP merge on maximum overlap with tie-breaks."""
    strings = prune_substrings(strings)

    while len(strings) > 1:
        best = None  # (ov, merged_len, i, j, merged_str, merged_map)
        for i in range(len(strings)):
            ai, mi = strings[i]
            for j in range(len(strings)):
                if i == j:
                    continue
                bj, mj = strings[j]
                ov = overlap(ai, bj)
                merged_str = ai + bj[ov:]
                merged_len = len(merged_str)

                # Tie-breaks:
                # 1) larger overlap
                # 2) smaller merged length
                # 3) deterministic: smaller (i,j)
                cand = (ov, merged_len, i, j, merged_str)
                if best is None or cand < best[:5]:
                    # NOTE: we want max overlap, so invert overlap for tuple-compare
                    pass

        # We want max overlap, so do explicit selection
        best_ov = -1
        best_merged_len = None
        best_i = best_j = None
        best_merged_str = None

        for i in range(len(strings)):
            ai, _ = strings[i]
            for j in range(len(strings)):
                if i == j:
                    continue
                bj, _ = strings[j]
                ov = overlap(ai, bj)
                merged_str = ai + bj[ov:]
                merged_len = len(merged_str)
                if (
                    ov > best_ov or
                    (ov == best_ov and (best_merged_len is None or merged_len < best_merged_len)) or
                    (ov == best_ov and merged_len == best_merged_len and (i, j) < (best_i, best_j))
                ):
                    best_ov = ov
                    best_merged_len = merged_len
                    best_i, best_j = i, j
                    best_merged_str = merged_str

        # Merge chosen pair
        a_str, a_map = strings[best_i]
        b_str, b_map = strings[best_j]
        shift_b = len(a_str) - best_ov

        merged_map = dict(a_map)
        for oid, off in b_map.items():
            merged_map[oid] = shift_b + off

        # Rebuild list: remove i and j, add merged, then prune substrings again
        new_list = []
        for k in range(len(strings)):
            if k not in (best_i, best_j):
                new_list.append(strings[k])
        new_list.append((best_merged_str, merged_map))
        strings = prune_substrings(new_list)

    return strings[0]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-T", type=int, required=True)
    ap.add_argument("-n", type=int, required=True)  # kept for compatibility; should be 1
    ap.add_argument("-m", type=int, required=True)
    ap.add_argument("-s", type=int, required=True)
    ap.add_argument("-o", type=str, required=True)
    ap.add_argument("--objective-type", choices=["square", "area"], default="area")
    ap.add_argument("--instance-json", type=str, default=None,
                    help="Optional: JSON file containing {'tiles': ['0101', ...]} to ensure same instance.")
    args = ap.parse_args()

    t0 = time.perf_counter()

    if args.instance_json:
        with open(args.instance_json, "r") as f:
            inst = json.load(f)
        tiles = inst["tiles"]
    else:
        # Fallback: generate deterministic random binary strings
        tiles = gen_random_binary_strings(args.T, args.m, args.s)

    # Initialize each tile with placement offset 0
    items = [(tiles[i], {i: 0}) for i in range(len(tiles))]

    super_s, placements = greedy_merge(items)

    runtime = time.perf_counter() - t0
    W = len(super_s)
    H = 1

    # For 1D, both objectives coincide numerically when H=1:
    # area = W*1 = W, square = max(W,1) = W
    objective = W

    # Build placements list (optional but nice)
    placement_list = [{"tile_id": tid, "x": int(x), "y": 0} for tid, x in sorted(placements.items())]

    out = {
        "input": {
            "T": args.T,
            "n": args.n,
            "m": args.m,
            "seed": args.s,
            "objective_type": args.objective_type,
        },
        "results": [{
            "algorithm": "merge_greedy_py",
            "status": "heuristic",
            "objective": int(objective),
            "runtime_seconds": float(runtime),
            "bbox_width": int(W),
            "bbox_height": int(H),
            "num_tiles_placed": int(args.T),
            "superstring": super_s,
            "placements": placement_list,
        }]
    }

    with open(args.o, "w") as f:
        json.dump(out, f, indent=2)

    # Optional stdout (helps your existing parser, but JSON is the source of truth)
    print(f"Status: heuristic")
    print(f"Objective (L): {objective}")
    print(f"Runtime: {runtime:.6f} seconds")
    print(f"Bounding Box: {W}×{H}")
    print(f"Placements: {args.T}")

if __name__ == "__main__":
    main()
