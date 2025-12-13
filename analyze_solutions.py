import json

# Load genetic solution
with open('/tmp/genetic_solution.json') as f:
    genetic = json.load(f)['results'][0]

print("Genetic solution placements:")
for p in genetic['placements']:
    print(f"  Tile {p['tile_id']}: ({p['x']}, {p['y']})")

print(f"\nGenetic bbox: {genetic['bbox_width']}×{genetic['bbox_height']} = {genetic['bbox_area']}")
print(f"Canvas:\n{genetic['canvas']}")

# Load CPLEX solution
with open('/tmp/cplex_solution.json') as f:
    cplex_sol = json.load(f)['results'][0]

print(f"\nCPLEX bbox: {cplex_sol['bbox_width']}×{cplex_sol['bbox_height']} = {cplex_sol['bbox_area']}")
print("CPLEX placements:")
for p in cplex_sol['placements']:
    print(f"  Tile {p['tile_id']}: ({p['x']}, {p['y']})")
