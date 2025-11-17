#include "branch_and_bound.hpp"
#include "greedy.hpp"
#include <chrono>
#include <iostream>
#include <iomanip>
#include <algorithm>
#include <cmath>

// ============================================================================
// Helper Functions
// ============================================================================

// Check if two tiles have symbol conflicts at given positions
static bool has_symbol_conflict(const Tile& tile_i, Coord pos_i, 
                                 const Tile& tile_j, Coord pos_j) {
    // Check each cell of tile_i
    for (const auto& [local_i, symbol_i] : tile_i.cells) {
        Coord global_i = {pos_i.first + local_i.first, pos_i.second + local_i.second};
        
        // Check if this global position overlaps with tile_j
        for (const auto& [local_j, symbol_j] : tile_j.cells) {
            Coord global_j = {pos_j.first + local_j.first, pos_j.second + local_j.second};
            
            if (global_i == global_j && symbol_i != symbol_j) {
                return true;  // conflict found
            }
        }
    }
    return false;  // no conflict
}

// Check if two tiles at given positions are overlapping or adjacent
static bool is_overlapping_or_adjacent(const Tile& tile_i, Coord pos_i,
                                        const Tile& tile_j, Coord pos_j) {
    // Get the bounding boxes of both tiles
    int i_xmin = pos_i.first + tile_i.min_x();
    int i_xmax = pos_i.first + tile_i.max_x();
    int i_ymin = pos_i.second + tile_i.min_y();
    int i_ymax = pos_i.second + tile_i.max_y();
    
    int j_xmin = pos_j.first + tile_j.min_x();
    int j_xmax = pos_j.first + tile_j.max_x();
    int j_ymin = pos_j.second + tile_j.min_y();
    int j_ymax = pos_j.second + tile_j.max_y();
    
    // Check if bounding boxes are overlapping or adjacent (within 1 cell)
    // They should either overlap or be at most 1 cell apart
    bool x_close = (i_xmin <= j_xmax + 1) && (j_xmin <= i_xmax + 1);
    bool y_close = (i_ymin <= j_ymax + 1) && (j_ymin <= i_ymax + 1);
    
    return x_close && y_close;
}

// Build adjacency list: for each tile, list of (neighbor_tile, offset) pairs
// Only include edges where tiles are overlapping or adjacent and symbol-consistent
static std::vector<std::vector<AdjEdge>> build_adjacency(const std::vector<Tile>& tiles) {
    const int n = tiles.size();
    std::vector<std::vector<AdjEdge>> adj(n);
    
    std::cerr << "Building adjacency list (overlapping/adjacent tiles only)...\n";
    
    long long total_edges = 0;
    
    // For each pair of tiles
    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j) {
            if (i == j) continue;
            
            // Determine the range of offsets where tiles could be overlapping or adjacent
            // If tile_i is at (0,0), tile_j can be placed at offsets that make them touch
            
            const Tile& ti = tiles[i];
            const Tile& tj = tiles[j];
            
            // The tiles can be adjacent/overlapping when their bounding boxes are close
            // Try offsets where tile j's bounding box is near tile i's bounding box
            int i_width = ti.width();
            int i_height = ti.height();
            int j_width = tj.width();
            int j_height = tj.height();
            
            // Search range: tile j can be placed such that it's overlapping or adjacent to tile i
            int dx_min = ti.min_x() - tj.max_x() - 1;
            int dx_max = ti.max_x() - tj.min_x() + 1;
            int dy_min = ti.min_y() - tj.max_y() - 1;
            int dy_max = ti.max_y() - tj.min_y() + 1;
            
            for (int dx = dx_min; dx <= dx_max; ++dx) {
                for (int dy = dy_min; dy <= dy_max; ++dy) {
                    Coord pos_j = {dx, dy};
                    
                    // Check if they're overlapping or adjacent
                    if (!is_overlapping_or_adjacent(ti, {0, 0}, tj, pos_j)) {
                        continue;
                    }
                    
                    // Check if tile_j at offset (dx, dy) from tile_i has no symbol conflicts
                    if (!has_symbol_conflict(ti, {0, 0}, tj, pos_j)) {
                        adj[i].emplace_back(j, dx, dy);
                    }
                }
            }
        }
        
        total_edges += adj[i].size();
        std::cerr << "  Tile " << i << " has " << adj[i].size() << " valid edges\n";
    }
    
    std::cerr << "Total edges in adjacency graph: " << total_edges << "\n";
    std::cerr << "Average edges per tile: " << (n > 0 ? (double)total_edges / n : 0.0) << "\n";
    
    return adj;
}

// Check if adding tile j at pos_j is feasible with current state
static bool is_feasible_add(int j, Coord pos_j, const BnBState& state, 
                            const std::vector<Tile>& tiles) {
    const Tile& tile_j = tiles[j];
    
    // Check each cell of tile_j
    for (const auto& [local_j, symbol_j] : tile_j.cells) {
        Coord global_coord = {pos_j.first + local_j.first, pos_j.second + local_j.second};
        
        // Check if this position is already occupied
        auto it = state.canvas.find(global_coord);
        if (it != state.canvas.end()) {
            // Position is occupied - check if symbols match
            if (it->second != symbol_j) {
                return false;  // symbol conflict
            }
        }
    }
    
    return true;  // no conflicts
}

// Update bounding box with a new tile
static BBox update_bbox(const BBox& bbox, int tile_idx, Coord pos, const std::vector<Tile>& tiles) {
    BBox new_bbox = bbox;
    const Tile& tile = tiles[tile_idx];
    
    for (const auto& [local, symbol] : tile.cells) {
        int x = pos.first + local.first;
        int y = pos.second + local.second;
        
        new_bbox.xmin = std::min(new_bbox.xmin, x);
        new_bbox.xmax = std::max(new_bbox.xmax, x);
        new_bbox.ymin = std::min(new_bbox.ymin, y);
        new_bbox.ymax = std::max(new_bbox.ymax, y);
    }
    
    return new_bbox;
}

// Compute initial bounding box for root tile at (0,0)
static BBox compute_initial_bbox(int root, const std::vector<Tile>& tiles) {
    BBox bbox;
    const Tile& tile = tiles[root];
    
    for (const auto& [local, symbol] : tile.cells) {
        int x = local.first;
        int y = local.second;
        
        bbox.xmin = std::min(bbox.xmin, x);
        bbox.xmax = std::max(bbox.xmax, x);
        bbox.ymin = std::min(bbox.ymin, y);
        bbox.ymax = std::max(bbox.ymax, y);
    }
    
    return bbox;
}

// Lower bound for partial state (current bounding box side length)
static int lower_bound(const BnBState& state) {
    return state.bbox.side_length();
}

// ============================================================================
// Branch and Bound DFS
// ============================================================================

static long long g_nodes_explored = 0;
static long long g_nodes_pruned = 0;
static int g_best_L = std::numeric_limits<int>::max();
static BnBState g_best_solution;
static auto g_start_time = std::chrono::steady_clock::now();
static double g_time_limit_sec = 300.0;

static void dfs_branch_and_bound(BnBState& state, 
                                  const std::vector<std::vector<AdjEdge>>& adj,
                                  const std::vector<Tile>& tiles) {
    g_nodes_explored++;
    
    // Check time limit
    auto now = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(now - g_start_time).count();
    if (elapsed >= g_time_limit_sec) {
        return;  // time limit exceeded
    }
    
    // Progress reporting (every 10000 nodes)
    if (g_nodes_explored % 10000 == 0) {
        std::cerr << "Nodes: " << g_nodes_explored 
                  << ", Pruned: " << g_nodes_pruned
                  << ", Best L: " << g_best_L
                  << ", Placed: " << state.placed.size() << "/" << tiles.size()
                  << ", Time: " << std::fixed << std::setprecision(1) << elapsed << "s\n";
    }
    
    // 1. Lower bound check (prune)
    int LB = lower_bound(state);
    if (LB >= g_best_L) {
        g_nodes_pruned++;
        return;  // cannot beat current best
    }
    
    // 2. Check if complete solution
    if (state.placed.size() == tiles.size()) {
        int L = state.bbox.side_length();
        if (L < g_best_L) {
            g_best_L = L;
            g_best_solution = state;
            std::cerr << "*** New best solution found: L = " << L 
                      << " (nodes: " << g_nodes_explored << ")\n";
        }
        return;
    }
    
    // 3. Branch: try to add neighbors of already placed tiles
    // Collect all candidate (tile, position) pairs
    std::vector<std::tuple<int, Coord, int>> candidates;  // (tile_j, pos_j, parent_i)
    
    for (int i : state.placed) {
        for (const AdjEdge& edge : adj[i]) {
            int j = edge.tile_idx;
            
            // Skip if already placed
            if (state.placed.count(j) > 0) continue;
            
            // Compute position for tile j
            Coord pos_i = state.positions.at(i);
            Coord pos_j = {pos_i.first + edge.offset_x, pos_i.second + edge.offset_y};
            
            // Check feasibility
            if (is_feasible_add(j, pos_j, state, tiles)) {
                candidates.emplace_back(j, pos_j, i);
            }
        }
    }
    
    // If no candidates, we have a dead end (partial tree)
    if (candidates.empty()) {
        return;
    }
    
    // Try each candidate (in order, could add heuristics here)
    for (const auto& [j, pos_j, parent_i] : candidates) {
        // Create new state
        BnBState new_state = state;
        
        // Add tile j
        new_state.placed.insert(j);
        new_state.positions[j] = pos_j;
        
        // Update canvas
        const Tile& tile_j = tiles[j];
        for (const auto& [local, symbol] : tile_j.cells) {
            Coord global = {pos_j.first + local.first, pos_j.second + local.second};
            new_state.canvas[global] = symbol;
        }
        
        // Update bounding box
        new_state.bbox = update_bbox(state.bbox, j, pos_j, tiles);
        
        // Add tree edge
        int offset_x = pos_j.first - state.positions.at(parent_i).first;
        int offset_y = pos_j.second - state.positions.at(parent_i).second;
        new_state.tree_edges.emplace_back(parent_i, j, offset_x, offset_y);
        
        // Recurse
        dfs_branch_and_bound(new_state, adj, tiles);
    }
}

// ============================================================================
// Main Solver
// ============================================================================

BranchAndBoundResult solve_branch_and_bound(const std::vector<Tile>& tiles,
                                             int root_tile,
                                             double time_limit_sec,
                                             int initial_upper_bound) {
    auto start = std::chrono::steady_clock::now();
    
    BranchAndBoundResult result;
    const int n = tiles.size();
    
    if (n == 0) {
        return result;
    }
    
    // Clamp root tile
    if (root_tile < 0 || root_tile >= n) {
        root_tile = 0;
    }
    
    std::cerr << "\n=== Branch and Bound Solver ===\n";
    std::cerr << "Tiles: " << n << "\n";
    std::cerr << "Root tile: " << root_tile << "\n";
    std::cerr << "Time limit: " << time_limit_sec << "s\n";
    
    // Build adjacency list (edges only for overlapping/adjacent tiles)
    auto adj = build_adjacency(tiles);
    
    // Get initial upper bound from greedy if not provided
    if (initial_upper_bound == std::numeric_limits<int>::max()) {
        std::cerr << "\nRunning greedy heuristic for initial upper bound...\n";
        auto greedy_result = solve_greedy(tiles, root_tile);
        initial_upper_bound = greedy_result.best_obj;
        std::cerr << "Greedy solution: L = " << initial_upper_bound << "\n\n";
    }
    
    // Initialize global state
    g_nodes_explored = 0;
    g_nodes_pruned = 0;
    g_best_L = initial_upper_bound;
    g_best_solution = BnBState();
    g_start_time = start;
    g_time_limit_sec = time_limit_sec;
    
    // Create initial state with root tile at (0,0)
    BnBState initial_state;
    initial_state.placed.insert(root_tile);
    initial_state.positions[root_tile] = {0, 0};
    initial_state.bbox = compute_initial_bbox(root_tile, tiles);
    
    // Paint root tile on canvas
    const Tile& root = tiles[root_tile];
    for (const auto& [local, symbol] : root.cells) {
        initial_state.canvas[local] = symbol;
    }
    
    std::cerr << "Starting branch and bound search...\n\n";
    
    // Run DFS branch and bound
    dfs_branch_and_bound(initial_state, adj, tiles);
    
    auto end = std::chrono::steady_clock::now();
    double elapsed = std::chrono::duration<double>(end - start).count();
    
    std::cerr << "\n=== Search Complete ===\n";
    std::cerr << "Nodes explored: " << g_nodes_explored << "\n";
    std::cerr << "Nodes pruned: " << g_nodes_pruned << "\n";
    std::cerr << "Best L found: " << g_best_L << "\n";
    std::cerr << "Time: " << elapsed << "s\n";
    
    // Build result
    result.best_obj = g_best_L;
    result.nodes_explored = g_nodes_explored;
    result.nodes_pruned = g_nodes_pruned;
    result.wall_time_sec = elapsed;
    
    if (g_best_solution.placed.size() == tiles.size()) {
        // Complete solution found
        result.bbox_width = g_best_solution.bbox.width();
        result.bbox_height = g_best_solution.bbox.height();
        result.bbox_area = result.bbox_width * result.bbox_height;
        
        for (const auto& [tile_idx, pos] : g_best_solution.positions) {
            result.placements.push_back({tile_idx, pos.first, pos.second});
        }
        
        std::cerr << "Complete solution found!\n";
    } else {
        std::cerr << "No complete solution found within time limit.\n";
    }
    
    return result;
}
