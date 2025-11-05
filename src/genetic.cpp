#include "genetic.hpp"
#include <chrono>
#include <random>
#include <algorithm>
#include <cmath>
#include <unordered_set>
#include <iostream>
#include <iomanip>

// ============================================================================
// Helper Functions
// ============================================================================

static bool tiles_contact(const Tile& tile_u, Coord pos_u, const Tile& tile_v, Coord pos_v) {
    std::unordered_set<Coord> coords_u;
    std::unordered_set<Coord> coords_v;
    
    for (const auto& [coord, _] : tile_u.cells) {
        coords_u.insert({coord.first + pos_u.first, coord.second + pos_u.second});
    }
    
    for (const auto& [coord, _] : tile_v.cells) {
        coords_v.insert({coord.first + pos_v.first, coord.second + pos_v.second});
    }
    
    // Check overlap
    for (const auto& cu : coords_u) {
        if (coords_v.count(cu)) return true;
    }
    
    // Check 4-adjacent
    const int dx_arr[] = {1, -1, 0, 0};
    const int dy_arr[] = {0, 0, 1, -1};
    
    for (const auto& [xu, yu] : coords_u) {
        for (int i = 0; i < 4; ++i) {
            if (coords_v.count({xu + dx_arr[i], yu + dy_arr[i]})) {
                return true;
            }
        }
    }
    
    return false;
}

static Solution create_greedy_solution(const std::vector<Tile>& tiles, int start_index = 0) {
    Solution sol;
    auto greedy_result = solve_greedy(tiles, start_index);
    
    for (const auto& p : greedy_result.placements) {
        sol.placements[p[0]] = {p[1], p[2]};
    }
    
    sol.objective = greedy_result.best_obj;
    sol.bbox_width = greedy_result.bbox_width;
    sol.bbox_height = greedy_result.bbox_height;
    sol.bbox_area = greedy_result.bbox_area;
    
    return sol;
}

static void evaluate_solution(Solution& sol, const std::vector<Tile>& tiles) {
    if (sol.placements.size() != tiles.size()) {
        sol.objective = std::numeric_limits<int>::max();
        return;
    }
    
    int xmin = std::numeric_limits<int>::max();
    int xmax = std::numeric_limits<int>::min();
    int ymin = std::numeric_limits<int>::max();
    int ymax = std::numeric_limits<int>::min();
    
    CellMap canvas;
    bool valid = true;
    
    for (size_t i = 0; i < tiles.size(); ++i) {
        auto it = sol.placements.find(i);
        if (it == sol.placements.end()) {
            valid = false;
            break;
        }
        
        auto [x, y] = it->second;
        CellMap placement = tiles[i].translate(x, y);
        
        for (const auto& [coord, label] : placement) {
            auto cit = canvas.find(coord);
            if (cit != canvas.end() && cit->second != label) {
                valid = false;
                break;
            }
            canvas[coord] = label;
            
            xmin = std::min(xmin, coord.first);
            xmax = std::max(xmax, coord.first);
            ymin = std::min(ymin, coord.second);
            ymax = std::max(ymax, coord.second);
        }
        
        if (!valid) break;
    }
    
    if (!valid || canvas.empty()) {
        sol.objective = std::numeric_limits<int>::max();
        sol.bbox_width = 0;
        sol.bbox_height = 0;
        sol.bbox_area = 0;
    } else {
        sol.bbox_width = xmax - xmin + 1;
        sol.bbox_height = ymax - ymin + 1;
        sol.bbox_area = sol.bbox_width * sol.bbox_height;
        sol.objective = std::max(sol.bbox_width, sol.bbox_height);
    }
}

// Build adjacency tree from a solution based on tile contact relationships
static Tree build_tree_from_solution(const Solution& sol, const std::vector<Tile>& tiles) {
    Tree tree;
    if (sol.placements.empty()) return tree;
    
    std::unordered_set<int> placed;
    std::vector<int> order;
    
    // Find root (first tile, or any tile)
    tree.root = sol.placements.begin()->first;
    placed.insert(tree.root);
    order.push_back(tree.root);
    
    // BFS-like traversal to build tree based on contact
    size_t idx = 0;
    while (idx < order.size() && placed.size() < sol.placements.size()) {
        int u = order[idx++];
        auto pos_u = sol.placements.at(u);
        
        // Find all tiles that contact u and haven't been placed yet
        for (const auto& [v, pos_v] : sol.placements) {
            if (placed.count(v)) continue;
            
            if (tiles_contact(tiles[u], pos_u, tiles[v], pos_v)) {
                tree.edges.push_back(Edge(u, v));
                placed.insert(v);
                order.push_back(v);
            }
        }
    }
    
    return tree;
}

static Solution crossover_solutions(const Solution& parent1, const Solution& parent2, 
                                    const std::vector<Tile>& tiles, std::mt19937& rng) {
    Solution child;
    
    // Build trees from both parents
    Tree tree1 = build_tree_from_solution(parent1, tiles);
    Tree tree2 = build_tree_from_solution(parent2, tiles);
    
    // Create maps for quick edge lookup: parent_node -> list of child nodes
    std::unordered_map<int, std::vector<int>> edges1, edges2;
    for (const auto& e : tree1.edges) {
        edges1[e.u].push_back(e.v);
    }
    for (const auto& e : tree2.edges) {
        edges2[e.u].push_back(e.v);
    }
    
    // Start with root from parent1
    std::unordered_set<int> placed;
    std::vector<int> frontier;  // Nodes that have been placed and can grow
    
    int root = tree1.root;
    if (parent1.placements.count(root)) {
        child.placements[root] = parent1.placements.at(root);
        placed.insert(root);
        frontier.push_back(root);
    }
    
    // Alternately grow from both parents
    bool use_parent1 = false;  // Start with parent2 next (since we used parent1's root)
    std::vector<int> tried_frontier_nodes;
    
    while (placed.size() < tiles.size() && !frontier.empty()) {
        // Choose which parent's edges to use
        auto& current_edges = use_parent1 ? edges1 : edges2;
        auto& current_parent = use_parent1 ? parent1 : parent2;
        
        bool found = false;
        tried_frontier_nodes.clear();
        
        // Try to find a valid edge from current parent
        while (!frontier.empty() && !found) {
            // Pick a random frontier node
            std::uniform_int_distribution<size_t> dist(0, frontier.size() - 1);
            size_t pick_idx = dist(rng);
            int u = frontier[pick_idx];
            
            // Try all edges from this node
            if (current_edges.count(u)) {
                for (int v : current_edges[u]) {
                    if (placed.count(v)) continue;
                    
                    // Try to place v using position from current parent
                    if (!current_parent.placements.count(v)) continue;
                    
                    auto pos_v = current_parent.placements.at(v);
                    CellMap placement_v = tiles[v].translate(pos_v.first, pos_v.second);
                    
                    // Check if placement is valid (no conflicts with already placed tiles)
                    bool valid = true;
                    for (const auto& [coord, label] : placement_v) {
                        for (const auto& [placed_idx, placed_pos] : child.placements) {
                            CellMap placed_placement = tiles[placed_idx].translate(placed_pos.first, placed_pos.second);
                            auto it = placed_placement.find(coord);
                            if (it != placed_placement.end() && it->second != label) {
                                valid = false;
                                break;
                            }
                        }
                        if (!valid) break;
                    }
                    
                    if (valid) {
                        child.placements[v] = pos_v;
                        placed.insert(v);
                        frontier.push_back(v);
                        found = true;
                        break;
                    }
                }
            }
            
            // If no valid edge from this node, remove it from frontier and try another
            if (!found) {
                tried_frontier_nodes.push_back(u);
                frontier.erase(frontier.begin() + pick_idx);
            }
        }
        
        // Restore tried nodes if we found something
        if (found) {
            frontier.insert(frontier.end(), tried_frontier_nodes.begin(), tried_frontier_nodes.end());
        }
        
        // Alternate to other parent
        use_parent1 = !use_parent1;
    }
    
    // If one parent runs out of edges, use edges from the other parent
    for (int pass = 0; pass < 2 && placed.size() < tiles.size(); ++pass) {
        auto& remaining_edges = pass == 0 ? edges1 : edges2;
        auto& remaining_parent = pass == 0 ? parent1 : parent2;
        
        bool found_any = true;
        while (found_any && placed.size() < tiles.size()) {
            found_any = false;
            
            for (const auto& [u, children] : remaining_edges) {
                if (!placed.count(u)) continue;
                
                for (int v : children) {
                    if (placed.count(v)) continue;
                    if (!remaining_parent.placements.count(v)) continue;
                    
                    auto pos_v = remaining_parent.placements.at(v);
                    CellMap placement_v = tiles[v].translate(pos_v.first, pos_v.second);
                    
                    bool valid = true;
                    for (const auto& [coord, label] : placement_v) {
                        for (const auto& [placed_idx, placed_pos] : child.placements) {
                            CellMap placed_placement = tiles[placed_idx].translate(placed_pos.first, placed_pos.second);
                            auto it = placed_placement.find(coord);
                            if (it != placed_placement.end() && it->second != label) {
                                valid = false;
                                break;
                            }
                        }
                        if (!valid) break;
                    }
                    
                    if (valid) {
                        child.placements[v] = pos_v;
                        placed.insert(v);
                        found_any = true;
                    }
                }
            }
        }
    }
    
    // Greedily add remaining unplaced tiles
    if (placed.size() < tiles.size()) {
        std::vector<int> unplaced;
        for (size_t i = 0; i < tiles.size(); ++i) {
            if (!placed.count(i)) {
                unplaced.push_back(i);
            }
        }
        
        // Use greedy solver to place remaining tiles
        std::vector<Tile> remaining_tiles;
        std::unordered_map<int, int> remaining_idx_map;  // new_idx -> original_idx
        
        for (int idx : unplaced) {
            remaining_idx_map[remaining_tiles.size()] = idx;
            remaining_tiles.push_back(tiles[idx]);
        }
        
        if (!remaining_tiles.empty()) {
            GreedySolver greedy_solver(remaining_tiles);
            
            // Build initial canvas from already placed tiles
            for (const auto& [placed_idx, placed_pos] : child.placements) {
                CellMap pm = tiles[placed_idx].translate(placed_pos.first, placed_pos.second);
                greedy_solver.canvas.add_placement(pm);
            }
            
            // Place remaining tiles one by one using greedy logic
            for (size_t i = 0; i < remaining_tiles.size(); ++i) {
                const Tile& tile = remaining_tiles[i];
                int original_idx = remaining_idx_map[i];
                
                int current_size = greedy_solver.canvas.is_empty() ? 0 : 
                                   std::max(greedy_solver.canvas.xmax - greedy_solver.canvas.xmin + 1, 
                                           greedy_solver.canvas.ymax - greedy_solver.canvas.ymin + 1);
                int max_tile_size = std::max(tile.width(), tile.height());
                
                std::optional<PlacementChoice> best_placement;
                
                // Try increasing sizes until we find a valid placement
                for (int target_size = std::max(current_size, max_tile_size); 
                     target_size <= current_size + max_tile_size * 2; 
                     ++target_size) {
                    
                    // Generate candidate positions for this size
                    std::vector<Coord> positions;
                    
                    if (greedy_solver.canvas.is_empty()) {
                        if (std::max(tile.width(), tile.height()) <= target_size) {
                            positions.push_back({0, 0});
                        }
                    } else {
                        // Try positions around the current bounding box
                        int search_range = target_size;
                        for (int dx = greedy_solver.canvas.xmin - search_range; 
                             dx <= greedy_solver.canvas.xmax + search_range; ++dx) {
                            for (int dy = greedy_solver.canvas.ymin - search_range; 
                                 dy <= greedy_solver.canvas.ymax + search_range; ++dy) {
                                positions.push_back({dx, dy});
                            }
                        }
                    }
                    
                    for (const auto& [dx, dy] : positions) {
                        CellMap placement = tile.translate(dx, dy);
                        auto [ok, overlap] = greedy_solver.canvas.overlap_check(placement);
                        
                        if (ok) {
                            int new_size = std::max(tile.width(), tile.height());
                            if (!greedy_solver.canvas.is_empty()) {
                                int nxmin = std::min(greedy_solver.canvas.xmin, tile.min_x() + dx);
                                int nxmax = std::max(greedy_solver.canvas.xmax, tile.max_x() + dx);
                                int nymin = std::min(greedy_solver.canvas.ymin, tile.min_y() + dy);
                                int nymax = std::max(greedy_solver.canvas.ymax, tile.max_y() + dy);
                                new_size = std::max(nxmax - nxmin + 1, nymax - nymin + 1);
                            }
                            
                            if (new_size <= target_size) {
                                if (!best_placement.has_value() || overlap > best_placement->overlap) {
                                    best_placement = PlacementChoice(i, dx, dy, new_size - current_size, 
                                                                     overlap, std::move(placement));
                                }
                            }
                        }
                    }
                    
                    if (best_placement.has_value()) break;
                }
                
                if (best_placement.has_value()) {
                    child.placements[original_idx] = {best_placement->dx, best_placement->dy};
                    greedy_solver.canvas.add_placement(best_placement->placement);
                }
            }
        }
    }
    
    evaluate_solution(child, tiles);
    return child;
}

// ============================================================================
// Genetic Algorithm Main Function
// ============================================================================

GeneticResult solve_genetic(const std::vector<Tile>& tiles, 
                            int population_size, 
                            int num_generations,
                            int start_index) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    std::cout << "\n=== Genetic Algorithm Started ===\n";
    std::cout << "Population size: " << population_size << "\n";
    std::cout << "Generations: " << num_generations << "\n";
    std::cout << "Tiles: " << tiles.size() << "\n\n";
    
    std::mt19937 rng(std::random_device{}());
    
    // Initialize population with greedy solutions from different starting points
    std::cout << "Initializing population...\n";
    std::vector<Solution> population;
    population.reserve(population_size);
    
    for (int i = 0; i < population_size; ++i) {
        int start = i % tiles.size();
        auto sol = create_greedy_solution(tiles, start);
        population.push_back(sol);
        if ((i + 1) % 10 == 0 || i == population_size - 1) {
            std::cout << "  Created " << (i + 1) << "/" << population_size << " solutions\n";
        }
    }
    
    Solution best_solution = population[0];
    for (const auto& sol : population) {
        if (sol.objective < best_solution.objective) {
            best_solution = sol;
        }
    }
    
    std::cout << "Initial best objective: " << best_solution.objective << "\n";
    std::cout << "Initial best bounding box: " << best_solution.bbox_width << " × " << best_solution.bbox_height << "\n\n";
    
    // Evolution loop
    std::cout << "Starting evolution...\n";
    for (int gen = 0; gen < num_generations; ++gen) {
        // Sort population by objective
        std::sort(population.begin(), population.end(), 
                 [](const Solution& a, const Solution& b) {
                     return a.objective < b.objective;
                 });
        
        // Update best
        bool improved = false;
        if (population[0].objective < best_solution.objective) {
            best_solution = population[0];
            improved = true;
        }
        
        // Log generation progress
        if (true) {
            auto current_time = std::chrono::high_resolution_clock::now();
            std::chrono::duration<double> elapsed = current_time - start_time;
            
            std::cout << "Generation " << (gen + 1) << "/" << num_generations;
            std::cout << " | Best: " << best_solution.objective;
            std::cout << " (" << best_solution.bbox_width << "×" << best_solution.bbox_height << ")";
            std::cout << " | Pop avg: " << std::fixed << std::setprecision(2);
            
            double avg_obj = 0.0;
            for (const auto& sol : population) {
                avg_obj += sol.objective;
            }
            avg_obj /= population.size();
            std::cout << avg_obj;
            
            std::cout << " | Time: " << std::fixed << std::setprecision(2) << elapsed.count() << "s";
            if (improved) std::cout << " [IMPROVED]";
            std::cout << "\n";
        }
        
        // Create new generation
        std::vector<Solution> new_population;
        new_population.reserve(population_size);
        
        // Crossover: create rest of population
        while (new_population.size() < (size_t)population_size) {
            std::uniform_int_distribution<int> parent_dist(0, population_size / 2);
            int p1_idx = parent_dist(rng);
            int p2_idx = parent_dist(rng);
            
            auto child = crossover_solutions(population[p1_idx], population[p2_idx], tiles, rng);
            
            new_population.push_back(child);
        }
        
        population = std::move(new_population);
    }
    
    // Final evaluation
    std::cout << "\nFinal evaluation...\n";
    std::sort(population.begin(), population.end(), 
             [](const Solution& a, const Solution& b) {
                 return a.objective < b.objective;
             });
    
    if (population[0].objective < best_solution.objective) {
        best_solution = population[0];
        std::cout << "Final improvement found!\n";
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;
    
    std::cout << "\n=== Genetic Algorithm Completed ===\n";
    std::cout << "Final best objective: " << best_solution.objective << "\n";
    std::cout << "Final bounding box: " << best_solution.bbox_width << " × " << best_solution.bbox_height << "\n";
    std::cout << "Total runtime: " << std::fixed << std::setprecision(3) << elapsed.count() << " seconds\n\n";
    
    // Convert to result format
    GeneticResult result;
    result.best_obj = best_solution.objective;
    result.bbox_width = best_solution.bbox_width;
    result.bbox_height = best_solution.bbox_height;
    result.bbox_area = best_solution.bbox_area;
    result.wall_time_sec = elapsed.count();
    result.generations = num_generations;
    result.population_size = population_size;
    
    for (const auto& [idx, pos] : best_solution.placements) {
        result.placements.push_back({(int)idx, pos.first, pos.second});
    }
    
    return result;
}
