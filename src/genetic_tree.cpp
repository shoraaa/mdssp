#include "genetic.hpp"
#include <chrono>
#include <random>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <queue>
#include <set>
#include <limits>
#include <mutex>

// ============================================================================
// Tree-Based Genetic Algorithm Implementation
// ============================================================================

// Helper: Check if two tiles can be placed adjacent/overlapping
static bool tiles_can_contact(const Tile& tile_u, int dx_u, int dy_u,
                              const Tile& tile_v, int dx_v, int dy_v) {
    // Translate tiles to absolute positions
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
                return true; // Adjacent
            }
        }
    }
    
    return false;
}

// Build placement graph: pre-compute valid placements between all tile pairs
PlacementGraph build_placement_graph(const std::vector<Tile>& tiles) {
    const int n = tiles.size();
    PlacementGraph graph(n);
    
    std::cout << "Building placement graph...\n";
    
    // For each pair of tiles, find all valid relative placements
    #pragma omp parallel for schedule(dynamic) collapse(2)
    for (int u = 0; u < n; ++u) {
        for (int v = 0; v < n; ++v) {
            if (u == v) continue;
            
            std::vector<PlacementGraph::ValidPlacement> valid_placements;
            
            // Sample search space: relative offsets
            const int max_offset = std::max({tiles[u].width(), tiles[u].height(),
                                            tiles[v].width(), tiles[v].height()}) + 2;
            
            for (int dx = -max_offset; dx <= max_offset; ++dx) {
                for (int dy = -max_offset; dy <= max_offset; ++dy) {
                    // Place u at (0, 0) and v at (dx, dy)
                    if (tiles_can_contact(tiles[u], 0, 0, tiles[v], dx, dy)) {
                        valid_placements.push_back({dx, dy});
                    }
                }
            }
            
            #pragma omp critical
            {
                graph.adjacency[u][v] = std::move(valid_placements);
            }
        }
    }
    
    // Print statistics
    int total_valid = 0;
    int max_valid = 0;
    int min_valid = std::numeric_limits<int>::max();
    
    for (int u = 0; u < n; ++u) {
        for (int v = 0; v < n; ++v) {
            if (u == v) continue;
            int count = graph.adjacency[u][v].size();
            total_valid += count;
            max_valid = std::max(max_valid, count);
            min_valid = std::min(min_valid, count);
        }
    }
    
    double avg_valid = (n * (n - 1) > 0) ? (double)total_valid / (n * (n - 1)) : 0.0;
    
    std::cout << "  Valid placements per tile pair: "
              << "avg=" << std::fixed << std::setprecision(1) << avg_valid
              << ", min=" << min_valid << ", max=" << max_valid << "\n";
    std::cout << "  Total valid placements in graph: " << total_valid << "\n\n";
    
    return graph;
}

// Decode PlacementTree to Solution
Solution decode_tree(const PlacementTree& tree, const std::vector<Tile>& tiles, ObjectiveType obj_type = ObjectiveType::BOUNDING_SQUARE) {
    Solution sol;
    
    if (tree.edges.empty() && tree.num_tiles == 0) {
        return sol; // Empty tree
    }
    
    // Build adjacency list for tree traversal
    const int n = tiles.size();
    std::vector<std::vector<TreeEdge>> children(n);
    
    for (const auto& edge : tree.edges) {
        if (edge.parent >= 0 && edge.parent < n && 
            edge.child >= 0 && edge.child < n) {
            children[edge.parent].push_back(edge);
        }
    }
    
    // Place root at origin
    sol.placements[tree.root] = {0, 0};
    
    // BFS to place all tiles using relative offsets
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
        
        auto parent_pos = sol.placements[u];
        
        for (const auto& edge : children[u]) {
            int v = edge.child;
            if (visited[v]) continue;
            
            // Calculate absolute position for child
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
                sol.placements[v] = child_pos;
                for (const auto& [coord, label] : child_cells) {
                    canvas[coord] = label;
                }
                visited[v] = true;
                q.push(v);
            }
        }
    }
    
    // Evaluate solution
    if (!sol.placements.empty()) {
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
        
        sol.bbox_width = xmax - xmin + 1;
        sol.bbox_height = ymax - ymin + 1;
        sol.bbox_area = sol.bbox_width * sol.bbox_height;
        sol.objective = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                        ? std::max(sol.bbox_width, sol.bbox_height)
                        : sol.bbox_width * sol.bbox_height;
    } else {
        sol.objective = std::numeric_limits<int>::max();
    }
    
    return sol;
}

// Build initial placement tree from greedy solution
static PlacementTree build_tree_from_greedy(const std::vector<Tile>& tiles, 
                                           int start_index, 
                                           std::mt19937& rng,
                                           bool stochastic = false,
                                           ObjectiveType obj_type = ObjectiveType::BOUNDING_SQUARE) {
    PlacementTree tree;
    tree.num_tiles = tiles.size();
    
    // Get greedy solution
    Solution sol;
    if (stochastic) {
        sol = [&]() {
            Solution s;
            auto greedy_result = solve_greedy_stochastic(tiles, start_index, rng(), obj_type);
            for (const auto& p : greedy_result.placements) {
                s.placements[p[0]] = {p[1], p[2]};
            }
            s.objective = greedy_result.best_obj;
            s.bbox_width = greedy_result.bbox_width;
            s.bbox_height = greedy_result.bbox_height;
            s.bbox_area = greedy_result.bbox_area;
            return s;
        }();
    } else {
        auto greedy_result = solve_greedy(tiles, start_index, obj_type);
        for (const auto& p : greedy_result.placements) {
            sol.placements[p[0]] = {p[1], p[2]};
        }
        sol.objective = greedy_result.best_obj;
        sol.bbox_width = greedy_result.bbox_width;
        sol.bbox_height = greedy_result.bbox_height;
        sol.bbox_area = greedy_result.bbox_area;
    }
    
    if (sol.placements.empty()) {
        return tree;
    }
    
    // Extract tree structure from solution
    tree.root = sol.placements.begin()->first;
    
    const int n = tiles.size();
    std::vector<bool> in_tree(n, false);
    std::vector<int> frontier;
    
    in_tree[tree.root] = true;
    frontier.push_back(tree.root);
    

    
    // BFS to build spanning tree
    while (!frontier.empty() && (int)tree.edges.size() < n - 1) {
        std::vector<int> new_frontier;
        
        for (int u : frontier) {
            auto pos_u = sol.placements[u];
            
            for (const auto& [v, pos_v] : sol.placements) {
                if (in_tree[v]) continue;
                
                // Check if tiles are in contact
                if (tiles_can_contact(tiles[u], pos_u.first, pos_u.second,
                                     tiles[v], pos_v.first, pos_v.second)) {
                    // Add edge with relative offset
                    int dx = pos_v.first - pos_u.first;
                    int dy = pos_v.second - pos_u.second;
                    tree.edges.emplace_back(u, v, dx, dy);
                    
                    in_tree[v] = true;
                    new_frontier.push_back(v);
                }
            }
        }
        
        // If no new nodes were added but there are still unconnected tiles,
        // find the closest unconnected tile and add it
        if (new_frontier.empty() && (int)tree.edges.size() < (int)sol.placements.size() - 1) {
            int best_parent = -1;
            int best_child = -1;
            double best_dist = std::numeric_limits<double>::max();
            
            // Find closest unconnected tile to any tile in tree
            for (int u = 0; u < n; ++u) {
                if (!in_tree[u]) continue;
                auto pos_u = sol.placements[u];
                
                for (const auto& [v, pos_v] : sol.placements) {
                    if (in_tree[v]) continue;
                    
                    // Calculate distance
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
                auto pos_u = sol.placements[best_parent];
                auto pos_v = sol.placements[best_child];
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

// Statistics from crossover operation
struct CrossoverStats {
    PlacementTree child;
    int tiles_from_parents;
    int tiles_completed_greedily;
};

// Tree-based crossover: swap subtrees between parent trees
static CrossoverStats crossover_trees(const PlacementTree& parent1,
                                      const PlacementTree& parent2,
                                      const PlacementGraph& graph,
                                      const std::vector<Tile>& tiles,
                                      std::mt19937& rng) {
    PlacementTree child;
    child.num_tiles = tiles.size();
    const int n = tiles.size();
    
    // Build adjacency lists for both parents
    std::vector<std::vector<int>> adj1(n), adj2(n);
    std::vector<std::unordered_map<int, TreeEdge>> edges1(n), edges2(n);
    
    for (const auto& edge : parent1.edges) {
        adj1[edge.parent].push_back(edge.child);
        edges1[edge.parent][edge.child] = edge;
    }
    
    for (const auto& edge : parent2.edges) {
        adj2[edge.parent].push_back(edge.child);
        edges2[edge.parent][edge.child] = edge;
    }
    
    // Choose root (prefer parent1's root)
    child.root = parent1.root;
    
    // Build child tree by alternating between parents
    std::vector<bool> in_child(n, false);
    std::vector<int> frontier;
    std::unordered_map<int, Coord> positions; // Track absolute positions during construction
    
    in_child[child.root] = true;
    frontier.push_back(child.root);
    positions[child.root] = {0, 0};
    
    bool use_parent1 = true;
    
    while (!frontier.empty() && (int)child.edges.size() < n - 1) {
        std::vector<int> new_frontier;
        std::shuffle(frontier.begin(), frontier.end(), rng);
        
        for (int u : frontier) {
            auto& adj = use_parent1 ? adj1[u] : adj2[u];
            auto& edge_map = use_parent1 ? edges1[u] : edges2[u];
            
            // Shuffle children for variety
            std::vector<int> children = adj;
            std::shuffle(children.begin(), children.end(), rng);
            
            for (int v : children) {
                if (in_child[v]) continue;
                
                // Get edge from parent
                const auto& parent_edge = edge_map[v];
                
                // Check if this placement is valid given current positions
                Coord parent_pos = positions[u];
                Coord child_pos = {parent_pos.first + parent_edge.dx,
                                  parent_pos.second + parent_edge.dy};
                
                // Validate against already placed tiles
                CellMap child_cells = tiles[v].translate(child_pos.first, child_pos.second);
                bool valid = true;
                
                // Build current canvas
                CellMap canvas;
                for (const auto& [tile_idx, pos] : positions) {
                    CellMap tile_cells = tiles[tile_idx].translate(pos.first, pos.second);
                    for (const auto& [coord, label] : tile_cells) {
                        auto it = canvas.find(coord);
                        if (it != canvas.end() && it->second != label) {
                            valid = false;
                            break;
                        }
                        canvas[coord] = label;
                    }
                    if (!valid) break;
                }
                
                // Check child against canvas
                if (valid) {
                    for (const auto& [coord, label] : child_cells) {
                        auto it = canvas.find(coord);
                        if (it != canvas.end() && it->second != label) {
                            valid = false;
                            break;
                        }
                    }
                }
                
                if (valid) {
                    child.edges.emplace_back(u, v, parent_edge.dx, parent_edge.dy);
                    in_child[v] = true;
                    positions[v] = child_pos;
                    new_frontier.push_back(v);
                }
            }
        }
        
        frontier = std::move(new_frontier);
        use_parent1 = !use_parent1; // Alternate between parents
    }
    
    int tiles_from_parents = child.edges.size() + 1; // +1 for root
    int tiles_completed = 0;
    
    // If some tiles weren't connected, try to add them using any valid placement from graph
    // This ensures we always get complete solutions
    // Greedy completion: use greedy solver to place remaining tiles
    if ((int)child.edges.size() < n - 1) {
        // Collect unplaced tiles
        std::vector<int> unplaced;
        for (int i = 0; i < n; ++i) {
            if (!in_child[i]) {
                unplaced.push_back(i);
            }
        }
        
        tiles_completed = unplaced.size();
        
        if (!unplaced.empty()) {
            // Build reduced tile set for greedy
            std::vector<Tile> remaining_tiles;
            std::vector<int> new2orig;
            for (int idx : unplaced) {
                new2orig.push_back(idx);
                remaining_tiles.push_back(tiles[idx]);
            }
            
            // Create greedy solver and seed with already placed tiles
            GreedySolver greedy_solver(remaining_tiles);
            for (const auto& [tile_idx, pos] : positions) {
                CellMap pm = tiles[tile_idx].translate(pos.first, pos.second);
                greedy_solver.canvas.add_placement(pm);
            }
            
            // Greedily place remaining tiles
            std::vector<int> local_remaining;
            for (size_t i = 0; i < remaining_tiles.size(); ++i) {
                local_remaining.push_back(i);
            }
            
            while (!local_remaining.empty()) {
                std::optional<PlacementChoice> best_global;
                int current_size = greedy_solver.canvas.is_empty() ? 0 :
                    std::max(greedy_solver.canvas.xmax - greedy_solver.canvas.xmin + 1,
                             greedy_solver.canvas.ymax - greedy_solver.canvas.ymin + 1);
                
                int max_tile_size = 0;
                for (int idx : local_remaining) {
                    max_tile_size = std::max(max_tile_size, 
                        std::max(remaining_tiles[idx].width(), remaining_tiles[idx].height()));
                }
                
                bool found = false;
                for (int target = std::max(current_size, max_tile_size); !found; ++target) {
                    for (size_t j = 0; j < local_remaining.size(); ++j) {
                        int idx = local_remaining[j];
                        const Tile& tile = remaining_tiles[idx];
                        
                        // Generate candidate positions
                        std::vector<Coord> positions_to_try;
                        if (greedy_solver.canvas.is_empty()) {
                            if (std::max(tile.width(), tile.height()) <= target) {
                                positions_to_try.push_back({0, 0});
                            }
                        } else {
                            int sr = target;
                            for (int dx = greedy_solver.canvas.xmin - sr; dx <= greedy_solver.canvas.xmax + sr; ++dx) {
                                for (int dy = greedy_solver.canvas.ymin - sr; dy <= greedy_solver.canvas.ymax + sr; ++dy) {
                                    positions_to_try.push_back({dx, dy});
                                }
                            }
                        }
                        
                        for (const auto& p : positions_to_try) {
                            int dx = p.first, dy = p.second;
                            CellMap placement = tile.translate(dx, dy);
                            auto [ok, overlap] = greedy_solver.canvas.overlap_check(placement);
                            if (!ok) continue;
                            
                            int new_size = std::max(tile.width(), tile.height());
                            if (!greedy_solver.canvas.is_empty()) {
                                int nxmin = std::min(greedy_solver.canvas.xmin, tile.min_x() + dx);
                                int nxmax = std::max(greedy_solver.canvas.xmax, tile.max_x() + dx);
                                int nymin = std::min(greedy_solver.canvas.ymin, tile.min_y() + dy);
                                int nymax = std::max(greedy_solver.canvas.ymax, tile.max_y() + dy);
                                new_size = std::max(nxmax - nxmin + 1, nymax - nymin + 1);
                            }
                            
                            if (new_size <= target) {
                                int delta = new_size - current_size;
                                if (!best_global.has_value() || overlap > best_global->overlap) {
                                    best_global = PlacementChoice(idx, dx, dy, delta, overlap, std::move(placement));
                                    found = true;
                                }
                            }
                        }
                        if (found) break;
                    }
                    if (found) break;
                }
                
                if (best_global.has_value()) {
                    int original_idx = new2orig[best_global->tile_idx];
                    
                    // Find a parent for this tile in the tree (closest tile)
                    int best_parent = child.root;
                    double best_dist = std::numeric_limits<double>::max();
                    for (int u = 0; u < n; ++u) {
                        if (!in_child[u]) continue;
                        auto pos_u = positions[u];
                        double dist = std::sqrt((double)((best_global->dx - pos_u.first) * (best_global->dx - pos_u.first) +
                                                         (best_global->dy - pos_u.second) * (best_global->dy - pos_u.second)));
                        if (dist < best_dist) {
                            best_dist = dist;
                            best_parent = u;
                        }
                    }
                    
                    // Add edge to tree with relative offset
                    auto parent_pos = positions[best_parent];
                    int rel_dx = best_global->dx - parent_pos.first;
                    int rel_dy = best_global->dy - parent_pos.second;
                    child.edges.emplace_back(best_parent, original_idx, rel_dx, rel_dy);
                    
                    // Update state
                    in_child[original_idx] = true;
                    positions[original_idx] = {best_global->dx, best_global->dy};
                    greedy_solver.canvas.add_placement(best_global->placement);
                    
                    local_remaining.erase(
                        std::remove(local_remaining.begin(), local_remaining.end(), best_global->tile_idx),
                        local_remaining.end()
                    );
                } else {
                    // Cannot place any more tiles
                    break;
                }
            }
        }
    }
    
    return CrossoverStats{child, tiles_from_parents, tiles_completed};
}

// Tree-based mutation: change parent or offset of a random edge
static void mutate_tree(PlacementTree& tree,
                       const PlacementGraph& graph,
                       const std::vector<Tile>& tiles,
                       std::mt19937& rng,
                       double mutation_rate) {
    if (tree.edges.empty()) return;
    
    std::uniform_real_distribution<double> prob_dist(0.0, 1.0);
    if (prob_dist(rng) > mutation_rate) return;
    
    std::uniform_int_distribution<int> edge_dist(0, tree.edges.size() - 1);
    int edge_idx = edge_dist(rng);
    
    std::uniform_int_distribution<int> mutation_type(0, 1);
    
    if (mutation_type(rng) == 0) {
        // Mutation type 1: Change offset for existing edge
        TreeEdge& edge = tree.edges[edge_idx];
        int u = edge.parent;
        int v = edge.child;
        
        if (!graph.adjacency[u][v].empty()) {
            std::uniform_int_distribution<size_t> offset_dist(0, graph.adjacency[u][v].size() - 1);
            const auto& new_placement = graph.adjacency[u][v][offset_dist(rng)];
            edge.dx = new_placement.dx;
            edge.dy = new_placement.dy;
        }
    } else {
        // Mutation type 2: Change parent of a node (rewire tree)
        TreeEdge& edge = tree.edges[edge_idx];
        int v = edge.child;
        
        // Find potential new parents (tiles already in tree)
        std::vector<int> potential_parents;
        std::set<int> nodes_in_tree;
        nodes_in_tree.insert(tree.root);
        for (const auto& e : tree.edges) {
            nodes_in_tree.insert(e.parent);
            nodes_in_tree.insert(e.child);
        }
        
        for (int u : nodes_in_tree) {
            if (u != v && !graph.adjacency[u][v].empty()) {
                potential_parents.push_back(u);
            }
        }
        
        if (!potential_parents.empty()) {
            std::uniform_int_distribution<size_t> parent_dist(0, potential_parents.size() - 1);
            int new_parent = potential_parents[parent_dist(rng)];
            
            // Choose random valid offset for new parent-child pair
            if (!graph.adjacency[new_parent][v].empty()) {
                std::uniform_int_distribution<size_t> offset_dist(0, graph.adjacency[new_parent][v].size() - 1);
                const auto& new_placement = graph.adjacency[new_parent][v][offset_dist(rng)];
                
                edge.parent = new_parent;
                edge.dx = new_placement.dx;
                edge.dy = new_placement.dy;
            }
        }
    }
}

// Main tree-based genetic algorithm
GeneticResult solve_genetic_tree(const std::vector<Tile>& tiles,
                                 int population_size,
                                 int num_generations,
                                 int start_index,
                                 InitMode init_mode,
                                 unsigned int seed,
                                 ObjectiveType obj_type) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    std::cout << "\n=== Tree-Based Genetic Algorithm Started ===\n";
    std::cout << "Population size: " << population_size << "\n";
    std::cout << "Generations: " << num_generations << "\n";
    std::cout << "Tiles: " << tiles.size() << "\n";
    std::cout << "Initialization: " << (init_mode == InitMode::GREEDY ? "Greedy" : "Stochastic Greedy") << "\n";
    std::cout << "Seed: " << (seed == 0 ? "random" : std::to_string(seed)) << "\n\n";
    
    // Build placement graph
    PlacementGraph graph = build_placement_graph(tiles);
    
    // Initialize population
    std::cout << "Initializing population...\n";
    std::vector<PlacementTree> population(population_size);
    
    // Use provided seed or random_device if seed is 0
    std::mt19937 rng(seed == 0 ? std::random_device{}() : seed);
    
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < population_size; ++i) {
        std::mt19937 local_rng(rng() + i);
        int local_start = (start_index + i) % tiles.size();
        population[i] = build_tree_from_greedy(tiles, local_start, local_rng, 
                                               init_mode == InitMode::STOCHASTIC_GREEDY, obj_type);
    }
    
    // Evaluate initial population
    Solution best_solution;
    best_solution.objective = std::numeric_limits<int>::max();
    
    for (const auto& tree : population) {
        Solution sol = decode_tree(tree, tiles, obj_type);
        if (sol.objective < best_solution.objective) {
            best_solution = sol;
        }
    }
    
    std::cout << "Initial best objective: " << best_solution.objective << "\n";
    std::cout << "Initial best bounding box: " << best_solution.bbox_width 
              << " × " << best_solution.bbox_height << "\n";
    std::cout << "Initial placed tiles: " << best_solution.placements.size() 
              << " / " << tiles.size() << "\n\n";
    
    // Evolution parameters
    const double crossover_rate = 0.7;
    const double mutation_rate = 0.15;
    const int elite_size = std::max(1, population_size / 10);
    
    // Statistics tracking
    int total_crossovers = 0;
    int crossovers_needing_completion = 0;
    int total_tiles_completed = 0;
    std::mutex stats_mutex;
    
    std::cout << "Starting evolution...\n";
    std::cout << "Crossover rate: " << crossover_rate << "\n";
    std::cout << "Mutation rate: " << mutation_rate << "\n";
    std::cout << "Elite size: " << elite_size << "\n\n";
    
    // Evolution loop
    for (int gen = 0; gen < num_generations; ++gen) {
        // Decode all trees to solutions for evaluation
        std::vector<std::pair<int, Solution>> evaluated(population_size);
        
        #pragma omp parallel for schedule(static)
        for (int i = 0; i < population_size; ++i) {
            evaluated[i] = {i, decode_tree(population[i], tiles, obj_type)};
        }
        
        // Sort by fitness
        std::sort(evaluated.begin(), evaluated.end(),
                 [](const auto& a, const auto& b) {
                     return a.second.objective < b.second.objective;
                 });
        
        // Update best solution
        if (evaluated[0].second.objective < best_solution.objective) {
            best_solution = evaluated[0].second;
        }
        
        // Create new population
        std::vector<PlacementTree> new_population(population_size);
        
        // Elitism: copy best trees
        for (int i = 0; i < elite_size; ++i) {
            new_population[i] = population[evaluated[i].first];
        }
        
        // Generate rest through crossover only (no mutation)
        std::uniform_real_distribution<double> prob_dist(0.0, 1.0);
        std::uniform_int_distribution<int> parent_dist(0, population_size / 2);
        
        #pragma omp parallel for schedule(static)
        for (int i = elite_size; i < population_size; ++i) {
            std::mt19937 local_rng(rng() + gen * population_size + i);
            
            if (prob_dist(local_rng) < crossover_rate) {
                // Crossover
                int p1_idx = evaluated[parent_dist(local_rng)].first;
                int p2_idx = evaluated[parent_dist(local_rng)].first;
                auto stats = crossover_trees(population[p1_idx], population[p2_idx],
                                             graph, tiles, local_rng);
                new_population[i] = stats.child;
                
                // Collect statistics
                {
                    std::lock_guard<std::mutex> lock(stats_mutex);
                    total_crossovers++;
                    if (stats.tiles_completed_greedily > 0) {
                        crossovers_needing_completion++;
                        total_tiles_completed += stats.tiles_completed_greedily;
                    }
                }
            } else {
                // Copy from tournament selection
                int p_idx = evaluated[parent_dist(local_rng)].first;
                new_population[i] = population[p_idx];
            }
            
            // No mutation
        }
        
        population = std::move(new_population);
        
        // Print generation statistics
        auto now = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = now - start_time;
        
        double avg_obj = 0.0;
        for (const auto& [_, sol] : evaluated) {
            avg_obj += sol.objective;
        }
        avg_obj /= population_size;
        
        std::cout << "Gen " << std::setw(3) << (gen + 1) << "/" << num_generations
                  << " | Best: " << best_solution.objective
                  << " (" << best_solution.bbox_width << "×" << best_solution.bbox_height << ")"
                  << " [" << best_solution.placements.size() << " tiles]"
                  << " | Pop avg: " << std::fixed << std::setprecision(1) << avg_obj
                  << " | Time: " << std::fixed << std::setprecision(1) << elapsed.count() << "s\n";
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;
    
    std::cout << "\n=== Tree-Based Genetic Algorithm Completed ===\n";
    std::cout << "Final best objective: " << best_solution.objective << "\n";
    std::cout << "Final bounding box: " << best_solution.bbox_width << " × " << best_solution.bbox_height << "\n";
    std::cout << "Final placed tiles: " << best_solution.placements.size() << " / " << tiles.size() << "\n";
    std::cout << "Total runtime: " << std::fixed << std::setprecision(3) << elapsed.count() << " seconds\n";
    std::cout << "Crossover completion stats:\n";
    std::cout << "  Total crossovers: " << total_crossovers << "\n";
    std::cout << "  Crossovers needing greedy completion: " << crossovers_needing_completion 
              << " (" << std::fixed << std::setprecision(1) 
              << (100.0 * crossovers_needing_completion / std::max(1, total_crossovers)) << "%)\n";
    std::cout << "  Total tiles placed by greedy completion: " << total_tiles_completed << "\n";
    std::cout << "  Average tiles per incomplete crossover: " << std::fixed << std::setprecision(2)
              << (total_tiles_completed / std::max(1.0, (double)crossovers_needing_completion)) << "\n\n";
    
    GeneticResult result;
    result.best_obj = best_solution.objective;
    result.bbox_width = best_solution.bbox_width;
    result.bbox_height = best_solution.bbox_height;
    result.bbox_area = best_solution.bbox_area;
    result.wall_time_sec = elapsed.count();
    result.generations = num_generations;
    result.population_size = population_size;
    result.total_crossovers = total_crossovers;
    result.crossovers_needing_completion = crossovers_needing_completion;
    result.total_tiles_completed = total_tiles_completed;
    
    for (const auto& [tile_idx, pos] : best_solution.placements) {
        result.placements.push_back({tile_idx, pos.first, pos.second});
    }
    
    return result;
}
