#include "search.hpp"
#include <chrono>
#include <random>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <queue>
#include <set>
#include <limits>

// ============================================================================
// Helper Functions (shared between algorithms)
// ============================================================================

// Check if two tiles can be placed adjacent/overlapping without conflict
static bool tiles_can_contact_search(const Tile& tile_u, int dx_u, int dy_u,
                                     const Tile& tile_v, int dx_v, int dy_v) {
    CellMap cells_u = tile_u.translate(dx_u, dy_u);
    CellMap cells_v = tile_v.translate(dx_v, dy_v);
    
    // Check for overlap (must have matching labels)
    for (const auto& [coord_u, label_u] : cells_u) {
        auto it_v = cells_v.find(coord_u);
        if (it_v != cells_v.end()) {
            if (it_v->second == label_u) {
                return true; // Valid overlap
            } else {
                return false; // Invalid overlap (different labels)
            }
        }
    }
    
    // Check for 4-adjacency
    static const int dx_arr[4] = {1, -1, 0, 0};
    static const int dy_arr[4] = {0,  0, 1, -1};
    
    for (const auto& [coord_u, _] : cells_u) {
        for (int k = 0; k < 4; ++k) {
            Coord neighbor = {coord_u.first + dx_arr[k], coord_u.second + dy_arr[k]};
            if (cells_v.find(neighbor) != cells_v.end()) {
                return true;
            }
        }
    }
    
    return false;
}

// Evaluate a partial placement and compute objective
static int evaluate_placement(const std::unordered_map<int, Coord>& placements,
                             const std::vector<Tile>& tiles,
                             int& out_width, int& out_height,
                             ObjectiveType obj_type) {
    if (placements.empty()) {
        out_width = out_height = 0;
        return std::numeric_limits<int>::max();
    }
    
    CellMap canvas;
    for (const auto& [tile_idx, pos] : placements) {
        CellMap tile_cells = tiles[tile_idx].translate(pos.first, pos.second);
        for (const auto& [coord, label] : tile_cells) {
            canvas[coord] = label;
        }
    }
    
    int xmin = std::numeric_limits<int>::max();
    int xmax = std::numeric_limits<int>::min();
    int ymin = std::numeric_limits<int>::max();
    int ymax = std::numeric_limits<int>::min();
    
    for (const auto& [coord, _] : canvas) {
        xmin = std::min(xmin, coord.first);
        xmax = std::max(xmax, coord.first);
        ymin = std::min(ymin, coord.second);
        ymax = std::max(ymax, coord.second);
    }
    
    out_width = xmax - xmin + 1;
    out_height = ymax - ymin + 1;
    
    if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
        return std::max(out_width, out_height);
    } else {
        return out_width * out_height;
    }
}

// Check if a placement is valid (no conflicting overlaps)
static bool is_valid_placement(const std::unordered_map<int, Coord>& placements,
                               const std::vector<Tile>& tiles,
                               int new_tile_idx, Coord new_pos) {
    CellMap new_cells = tiles[new_tile_idx].translate(new_pos.first, new_pos.second);
    
    for (const auto& [tile_idx, pos] : placements) {
        if (tile_idx == new_tile_idx) continue;
        
        CellMap existing_cells = tiles[tile_idx].translate(pos.first, pos.second);
        
        for (const auto& [coord, label] : new_cells) {
            auto it = existing_cells.find(coord);
            if (it != existing_cells.end() && it->second != label) {
                return false; // Conflict
            }
        }
    }
    
    return true;
}

// ============================================================================
// Beam Search State
// ============================================================================

struct BeamState {
    std::unordered_map<int, Coord> placements;  // tile_idx -> position
    std::vector<int> placed_order;               // order in which tiles were placed
    int objective;
    int bbox_width;
    int bbox_height;
    
    BeamState() : objective(std::numeric_limits<int>::max()), bbox_width(0), bbox_height(0) {}
    
    bool operator<(const BeamState& other) const {
        // First prefer solutions that placed more tiles
        if (placements.size() != other.placements.size()) {
            return placements.size() > other.placements.size();
        }
        // Then prefer smaller objective
        return objective < other.objective;
    }
};

// ============================================================================
// Beam Search Implementation
// ============================================================================

SearchResult solve_beam_search(const std::vector<Tile>& tiles,
                               int beam_width,
                               unsigned int seed,
                               ObjectiveType obj_type) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    std::cout << "\n=== Beam Search Algorithm Started ===\n";
    std::cout << "Beam width: " << beam_width << "\n";
    std::cout << "Tiles: " << tiles.size() << "\n";
    std::cout << "Seed: " << (seed == 0 ? "random" : std::to_string(seed)) << "\n\n";
    
    std::mt19937 rng(seed == 0 ? std::random_device{}() : seed);
    
    const int n = tiles.size();
    int states_explored = 0;
    int improvements_found = 0;
    
    // Precompute valid relative placements between all tile pairs
    // adjacency[u][v] = list of valid offsets to place v relative to u
    std::cout << "Precomputing valid placements...\n";
    std::vector<std::vector<std::vector<Coord>>> adjacency(n, std::vector<std::vector<Coord>>(n));
    
    for (int u = 0; u < n; ++u) {
        for (int v = 0; v < n; ++v) {
            if (u == v) continue;
            
            const int max_offset = std::max({tiles[u].width(), tiles[u].height(),
                                            tiles[v].width(), tiles[v].height()}) + 2;
            
            for (int dx = -max_offset; dx <= max_offset; ++dx) {
                for (int dy = -max_offset; dy <= max_offset; ++dy) {
                    if (tiles_can_contact_search(tiles[u], 0, 0, tiles[v], dx, dy)) {
                        adjacency[u][v].push_back({dx, dy});
                    }
                }
            }
        }
    }
    
    // Initialize beam with single-tile states (one state per tile)
    std::vector<BeamState> beam;
    
    // Start with each tile as a possible root
    for (int i = 0; i < std::min(n, beam_width); ++i) {
        BeamState state;
        state.placements[i] = {0, 0};
        state.placed_order.push_back(i);
        state.objective = evaluate_placement(state.placements, tiles, 
                                             state.bbox_width, state.bbox_height, obj_type);
        beam.push_back(state);
        states_explored++;
    }
    
    // Sort and keep only beam_width states
    std::sort(beam.begin(), beam.end());
    if ((int)beam.size() > beam_width) {
        beam.resize(beam_width);
    }
    
    BeamState best_state = beam[0];
    
    std::cout << "Initial best: obj=" << best_state.objective 
              << " (" << best_state.bbox_width << "x" << best_state.bbox_height << ")\n";
    
    // Iteratively expand beam until all tiles are placed
    int iteration = 0;
    while (beam[0].placements.size() < (size_t)n) {
        iteration++;
        std::vector<BeamState> next_beam;
        
        // Expand each state in the beam
        for (const auto& state : beam) {
            if (state.placements.size() == (size_t)n) {
                // Already complete, keep it
                next_beam.push_back(state);
                continue;
            }
            
            // Find unplaced tiles
            std::vector<int> unplaced;
            for (int i = 0; i < n; ++i) {
                if (state.placements.find(i) == state.placements.end()) {
                    unplaced.push_back(i);
                }
            }
            
            // For each unplaced tile, find all valid placements
            for (int v : unplaced) {
                // Try placing v adjacent to each placed tile
                for (const auto& [u, pos_u] : state.placements) {
                    for (const auto& offset : adjacency[u][v]) {
                        Coord new_pos = {pos_u.first + offset.first, 
                                        pos_u.second + offset.second};
                        
                        // Check if this placement is valid
                        if (is_valid_placement(state.placements, tiles, v, new_pos)) {
                            BeamState new_state = state;
                            new_state.placements[v] = new_pos;
                            new_state.placed_order.push_back(v);
                            new_state.objective = evaluate_placement(new_state.placements, tiles,
                                                                     new_state.bbox_width, 
                                                                     new_state.bbox_height, obj_type);
                            next_beam.push_back(new_state);
                            states_explored++;
                        }
                    }
                }
            }
        }
        
        if (next_beam.empty()) {
            std::cout << "Warning: No valid expansions found at iteration " << iteration << "\n";
            break;
        }
        
        // Sort and prune to beam width
        std::sort(next_beam.begin(), next_beam.end());
        
        // Remove duplicates (states with same placements)
        std::vector<BeamState> unique_beam;
        std::set<std::set<std::pair<int, Coord>>> seen;
        
        for (const auto& state : next_beam) {
            std::set<std::pair<int, Coord>> state_sig;
            for (const auto& [idx, pos] : state.placements) {
                state_sig.insert({idx, pos});
            }
            
            if (seen.find(state_sig) == seen.end()) {
                seen.insert(state_sig);
                unique_beam.push_back(state);
                if ((int)unique_beam.size() >= beam_width) break;
            }
        }
        
        beam = std::move(unique_beam);
        
        // Update best
        if (beam[0] < best_state || 
            (beam[0].placements.size() == best_state.placements.size() && 
             beam[0].objective < best_state.objective)) {
            best_state = beam[0];
            improvements_found++;
        }
        
        // Progress report
        if (iteration % 5 == 0 || beam[0].placements.size() == (size_t)n) {
            std::cout << "Iter " << std::setw(3) << iteration 
                      << " | Tiles placed: " << beam[0].placements.size() << "/" << n
                      << " | Best obj: " << best_state.objective
                      << " (" << best_state.bbox_width << "x" << best_state.bbox_height << ")"
                      << " | Beam states: " << beam.size()
                      << " | Explored: " << states_explored << "\n";
        }
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;
    
    std::cout << "\n=== Beam Search Completed ===\n";
    std::cout << "Final objective: " << best_state.objective << "\n";
    std::cout << "Final bounding box: " << best_state.bbox_width << " x " << best_state.bbox_height << "\n";
    std::cout << "Tiles placed: " << best_state.placements.size() << " / " << n << "\n";
    std::cout << "Total runtime: " << std::fixed << std::setprecision(3) << elapsed.count() << " seconds\n";
    std::cout << "States explored: " << states_explored << "\n";
    std::cout << "Improvements found: " << improvements_found << "\n\n";
    
    // Build result
    SearchResult result;
    result.best_obj = best_state.objective;
    result.bbox_width = best_state.bbox_width;
    result.bbox_height = best_state.bbox_height;
    result.bbox_area = best_state.bbox_width * best_state.bbox_height;
    result.wall_time_sec = elapsed.count();
    result.iterations = iteration;
    result.states_explored = states_explored;
    result.improvements_found = improvements_found;
    
    for (const auto& [tile_idx, pos] : best_state.placements) {
        result.placements.push_back({tile_idx, pos.first, pos.second});
    }
    
    return result;
}

// ============================================================================
// Simulated Annealing State and Moves
// ============================================================================

struct SAState {
    PlacementTree tree;
    std::unordered_map<int, Coord> positions;  // Decoded positions
    int objective;
    int bbox_width;
    int bbox_height;
    
    SAState() : objective(std::numeric_limits<int>::max()), bbox_width(0), bbox_height(0) {}
};

// Decode a PlacementTree to positions
static void decode_tree_to_positions(const PlacementTree& tree,
                                     const std::vector<Tile>& tiles,
                                     std::unordered_map<int, Coord>& positions,
                                     ObjectiveType obj_type) {
    positions.clear();
    
    if (tree.edges.empty() && tree.num_tiles == 0) {
        return;
    }
    
    const int n = tiles.size();
    std::vector<std::vector<TreeEdge>> children(n);
    
    for (const auto& edge : tree.edges) {
        if (edge.parent >= 0 && edge.parent < n && 
            edge.child >= 0 && edge.child < n) {
            children[edge.parent].push_back(edge);
        }
    }
    
    // Place root at origin
    positions[tree.root] = {0, 0};
    
    // BFS to place all tiles
    std::queue<int> q;
    q.push(tree.root);
    std::vector<bool> visited(n, false);
    visited[tree.root] = true;
    
    CellMap canvas;
    CellMap root_cells = tiles[tree.root].translate(0, 0);
    for (const auto& [coord, label] : root_cells) {
        canvas[coord] = label;
    }
    
    while (!q.empty()) {
        int u = q.front();
        q.pop();
        
        auto parent_pos = positions[u];
        
        for (const auto& edge : children[u]) {
            int v = edge.child;
            if (visited[v]) continue;
            
            Coord child_pos = {parent_pos.first + edge.dx, 
                              parent_pos.second + edge.dy};
            
            // Validate placement
            CellMap child_cells = tiles[v].translate(child_pos.first, child_pos.second);
            bool valid = true;
            
            for (const auto& [coord, label] : child_cells) {
                auto it = canvas.find(coord);
                if (it != canvas.end() && it->second != label) {
                    valid = false;
                    break;
                }
            }
            
            if (valid) {
                positions[v] = child_pos;
                for (const auto& [coord, label] : child_cells) {
                    canvas[coord] = label;
                }
                visited[v] = true;
                q.push(v);
            }
        }
    }
}

// Build initial tree from greedy solution
static PlacementTree build_initial_tree_sa(const std::vector<Tile>& tiles,
                                           std::mt19937& rng,
                                           ObjectiveType obj_type) {
    PlacementTree tree;
    tree.num_tiles = tiles.size();
    
    // Get stochastic greedy solution
    auto greedy_result = solve_greedy_stochastic(tiles, 0, rng(), obj_type);
    
    std::unordered_map<int, Coord> sol_placements;
    for (const auto& p : greedy_result.placements) {
        sol_placements[p[0]] = {p[1], p[2]};
    }
    
    if (sol_placements.empty()) {
        return tree;
    }
    
    // Extract tree structure from solution
    tree.root = sol_placements.begin()->first;
    
    const int n = tiles.size();
    std::vector<bool> in_tree(n, false);
    std::vector<int> frontier;
    
    in_tree[tree.root] = true;
    frontier.push_back(tree.root);
    
    // BFS to build spanning tree
    while (!frontier.empty() && (int)tree.edges.size() < n - 1) {
        std::vector<int> new_frontier;
        
        for (int u : frontier) {
            auto pos_u = sol_placements[u];
            
            for (const auto& [v, pos_v] : sol_placements) {
                if (in_tree[v]) continue;
                
                // Check if tiles are in contact
                if (tiles_can_contact_search(tiles[u], pos_u.first, pos_u.second,
                                            tiles[v], pos_v.first, pos_v.second)) {
                    int dx = pos_v.first - pos_u.first;
                    int dy = pos_v.second - pos_u.second;
                    tree.edges.emplace_back(u, v, dx, dy);
                    
                    in_tree[v] = true;
                    new_frontier.push_back(v);
                }
            }
        }
        
        // If no new nodes found but tiles remain, find closest unconnected
        if (new_frontier.empty() && (int)tree.edges.size() < (int)sol_placements.size() - 1) {
            int best_parent = -1;
            int best_child = -1;
            double best_dist = std::numeric_limits<double>::max();
            
            for (int u = 0; u < n; ++u) {
                if (!in_tree[u]) continue;
                if (sol_placements.find(u) == sol_placements.end()) continue;
                auto pos_u = sol_placements[u];
                
                for (const auto& [v, pos_v] : sol_placements) {
                    if (in_tree[v]) continue;
                    
                    double dist = std::sqrt((pos_v.first - pos_u.first) * (pos_v.first - pos_u.first) +
                                           (pos_v.second - pos_u.second) * (pos_v.second - pos_u.second));
                    
                    if (dist < best_dist) {
                        best_dist = dist;
                        best_parent = u;
                        best_child = v;
                    }
                }
            }
            
            if (best_child >= 0) {
                auto pos_u = sol_placements[best_parent];
                auto pos_v = sol_placements[best_child];
                int dx = pos_v.first - pos_u.first;
                int dy = pos_v.second - pos_u.second;
                tree.edges.emplace_back(best_parent, best_child, dx, dy);
                in_tree[best_child] = true;
                new_frontier.push_back(best_child);
            }
        }
        
        frontier = std::move(new_frontier);
    }
    
    return tree;
}

// Apply a random move to the tree
static PlacementTree apply_move(const PlacementTree& tree,
                                const std::vector<Tile>& tiles,
                                const std::vector<std::vector<std::vector<Coord>>>& adjacency,
                                std::mt19937& rng) {
    PlacementTree new_tree = tree;
    
    if (new_tree.edges.empty()) return new_tree;
    
    std::uniform_int_distribution<int> move_type(0, 2);
    std::uniform_int_distribution<int> edge_dist(0, new_tree.edges.size() - 1);
    
    int move = move_type(rng);
    int edge_idx = edge_dist(rng);
    TreeEdge& edge = new_tree.edges[edge_idx];
    
    const int n = tiles.size();
    
    if (move == 0) {
        // Move type 1: Perturb offset slightly
        std::uniform_int_distribution<int> delta_dist(-2, 2);
        int new_dx = edge.dx + delta_dist(rng);
        int new_dy = edge.dy + delta_dist(rng);
        
        // Check if new offset is valid
        if (!adjacency[edge.parent][edge.child].empty()) {
            // Find closest valid offset
            double best_dist = std::numeric_limits<double>::max();
            Coord best_offset = {edge.dx, edge.dy};
            
            for (const auto& off : adjacency[edge.parent][edge.child]) {
                double dist = std::sqrt((off.first - new_dx) * (off.first - new_dx) +
                                       (off.second - new_dy) * (off.second - new_dy));
                if (dist < best_dist) {
                    best_dist = dist;
                    best_offset = off;
                }
            }
            
            edge.dx = best_offset.first;
            edge.dy = best_offset.second;
        }
    } else if (move == 1) {
        // Move type 2: Random valid offset
        int u = edge.parent;
        int v = edge.child;
        
        if (!adjacency[u][v].empty()) {
            std::uniform_int_distribution<size_t> offset_dist(0, adjacency[u][v].size() - 1);
            const auto& new_offset = adjacency[u][v][offset_dist(rng)];
            edge.dx = new_offset.first;
            edge.dy = new_offset.second;
        }
    } else {
        // Move type 3: Change parent of a node
        int v = edge.child;
        
        // Find nodes in tree
        std::set<int> nodes_in_tree;
        nodes_in_tree.insert(new_tree.root);
        for (const auto& e : new_tree.edges) {
            nodes_in_tree.insert(e.parent);
            nodes_in_tree.insert(e.child);
        }
        
        // Find potential new parents
        std::vector<int> potential_parents;
        for (int u : nodes_in_tree) {
            if (u != v && !adjacency[u][v].empty()) {
                potential_parents.push_back(u);
            }
        }
        
        if (!potential_parents.empty()) {
            std::uniform_int_distribution<size_t> parent_dist(0, potential_parents.size() - 1);
            int new_parent = potential_parents[parent_dist(rng)];
            
            if (!adjacency[new_parent][v].empty()) {
                std::uniform_int_distribution<size_t> offset_dist(0, adjacency[new_parent][v].size() - 1);
                const auto& new_offset = adjacency[new_parent][v][offset_dist(rng)];
                
                edge.parent = new_parent;
                edge.dx = new_offset.first;
                edge.dy = new_offset.second;
            }
        }
    }
    
    return new_tree;
}

// ============================================================================
// Simulated Annealing Implementation
// ============================================================================

SearchResult solve_simulated_annealing(const std::vector<Tile>& tiles,
                                        double initial_temp,
                                        double cooling_rate,
                                        double min_temp,
                                        int max_iterations,
                                        unsigned int seed,
                                        ObjectiveType obj_type) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    std::cout << "\n=== Simulated Annealing Algorithm Started ===\n";
    std::cout << "Initial temperature: " << initial_temp << "\n";
    std::cout << "Cooling rate: " << cooling_rate << "\n";
    std::cout << "Min temperature: " << min_temp << "\n";
    std::cout << "Max iterations: " << max_iterations << "\n";
    std::cout << "Tiles: " << tiles.size() << "\n";
    std::cout << "Seed: " << (seed == 0 ? "random" : std::to_string(seed)) << "\n\n";
    
    std::mt19937 rng(seed == 0 ? std::random_device{}() : seed);
    
    const int n = tiles.size();
    int states_explored = 0;
    int improvements_found = 0;
    int accepted_worse = 0;
    
    // Precompute valid placements
    std::cout << "Precomputing valid placements...\n";
    std::vector<std::vector<std::vector<Coord>>> adjacency(n, std::vector<std::vector<Coord>>(n));
    
    for (int u = 0; u < n; ++u) {
        for (int v = 0; v < n; ++v) {
            if (u == v) continue;
            
            const int max_offset = std::max({tiles[u].width(), tiles[u].height(),
                                            tiles[v].width(), tiles[v].height()}) + 2;
            
            for (int dx = -max_offset; dx <= max_offset; ++dx) {
                for (int dy = -max_offset; dy <= max_offset; ++dy) {
                    if (tiles_can_contact_search(tiles[u], 0, 0, tiles[v], dx, dy)) {
                        adjacency[u][v].push_back({dx, dy});
                    }
                }
            }
        }
    }
    
    // Initialize with greedy solution
    std::cout << "Building initial solution...\n";
    SAState current;
    current.tree = build_initial_tree_sa(tiles, rng, obj_type);
    decode_tree_to_positions(current.tree, tiles, current.positions, obj_type);
    current.objective = evaluate_placement(current.positions, tiles,
                                           current.bbox_width, current.bbox_height, obj_type);
    
    SAState best = current;
    
    std::cout << "Initial solution: obj=" << current.objective 
              << " (" << current.bbox_width << "x" << current.bbox_height << ")"
              << " tiles=" << current.positions.size() << "/" << n << "\n\n";
    
    double temperature = initial_temp;
    std::uniform_real_distribution<double> prob_dist(0.0, 1.0);
    
    int last_improvement = 0;
    const int stagnation_limit = max_iterations / 5;
    
    // Main SA loop
    for (int iter = 0; iter < max_iterations && temperature > min_temp; ++iter) {
        // Generate neighbor
        PlacementTree neighbor_tree = apply_move(current.tree, tiles, adjacency, rng);
        
        std::unordered_map<int, Coord> neighbor_positions;
        decode_tree_to_positions(neighbor_tree, tiles, neighbor_positions, obj_type);
        
        int neighbor_width, neighbor_height;
        int neighbor_obj = evaluate_placement(neighbor_positions, tiles,
                                              neighbor_width, neighbor_height, obj_type);
        
        states_explored++;
        
        // Skip invalid neighbors (fewer tiles placed)
        if (neighbor_positions.size() < current.positions.size()) {
            continue;
        }
        
        // Calculate delta
        int delta = neighbor_obj - current.objective;
        
        // Accept or reject
        bool accept = false;
        if (delta < 0) {
            accept = true; // Always accept improvements
        } else if (delta == 0) {
            accept = true; // Accept equal solutions
        } else {
            // Accept worse with probability exp(-delta/T)
            double accept_prob = std::exp(-delta / temperature);
            accept = (prob_dist(rng) < accept_prob);
            if (accept) accepted_worse++;
        }
        
        if (accept) {
            current.tree = neighbor_tree;
            current.positions = neighbor_positions;
            current.objective = neighbor_obj;
            current.bbox_width = neighbor_width;
            current.bbox_height = neighbor_height;
            
            // Update best
            if (current.objective < best.objective ||
                (current.objective == best.objective && 
                 current.positions.size() > best.positions.size())) {
                best = current;
                improvements_found++;
                last_improvement = iter;
            }
        }
        
        // Cool down
        temperature *= cooling_rate;
        
        // Progress report
        if (iter % 1000 == 0 || iter == max_iterations - 1) {
            std::cout << "Iter " << std::setw(6) << iter 
                      << " | Temp: " << std::fixed << std::setprecision(2) << temperature
                      << " | Current: " << current.objective
                      << " | Best: " << best.objective 
                      << " (" << best.bbox_width << "x" << best.bbox_height << ")"
                      << " | Explored: " << states_explored
                      << " | Worse accepted: " << accepted_worse << "\n";
        }
        
        // Early termination on stagnation
        if (iter - last_improvement > stagnation_limit) {
            std::cout << "\nEarly termination due to stagnation at iteration " << iter << "\n";
            break;
        }
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;
    
    std::cout << "\n=== Simulated Annealing Completed ===\n";
    std::cout << "Final objective: " << best.objective << "\n";
    std::cout << "Final bounding box: " << best.bbox_width << " x " << best.bbox_height << "\n";
    std::cout << "Tiles placed: " << best.positions.size() << " / " << n << "\n";
    std::cout << "Total runtime: " << std::fixed << std::setprecision(3) << elapsed.count() << " seconds\n";
    std::cout << "States explored: " << states_explored << "\n";
    std::cout << "Improvements found: " << improvements_found << "\n";
    std::cout << "Worse solutions accepted: " << accepted_worse << "\n\n";
    
    // Build result
    SearchResult result;
    result.best_obj = best.objective;
    result.bbox_width = best.bbox_width;
    result.bbox_height = best.bbox_height;
    result.bbox_area = best.bbox_width * best.bbox_height;
    result.wall_time_sec = elapsed.count();
    result.iterations = states_explored;
    result.states_explored = states_explored;
    result.improvements_found = improvements_found;
    
    for (const auto& [tile_idx, pos] : best.positions) {
        result.placements.push_back({tile_idx, pos.first, pos.second});
    }
    
    return result;
}
