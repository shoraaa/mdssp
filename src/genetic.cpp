#include "genetic.hpp"
#include <chrono>
#include <random>
#include <algorithm>
#include <cmath>
#include <mutex>
// #include <unordered_set>   // removed
// #include <unordered_map>   // removed
#include <iostream>
#include <iomanip>

// ============================================================================
// Small helpers (no unordered_*)
// ============================================================================

// Build a sorted vector of absolute cell coords for a tile at position pos.
static std::vector<Coord> make_coords(const Tile& t, Coord pos) {
    std::vector<Coord> out;
    out.reserve(t.cells.size());
    for (const auto& kv : t.cells) {
        const auto& c = kv.first;
        out.push_back({c.first + pos.first, c.second + pos.second});
    }
    std::sort(out.begin(), out.end()); // pair<int,int> has lexicographic operator<
    out.erase(std::unique(out.begin(), out.end()), out.end());
    return out;
}

// Fast test whether any coord in A equals any coord in B (A,B sorted)
static bool any_overlap_sorted(const std::vector<Coord>& A, const std::vector<Coord>& B) {
    size_t i = 0, j = 0;
    while (i < A.size() && j < B.size()) {
        if (A[i] == B[j]) return true;
        if (A[i] < B[j]) ++i; else ++j;
    }
    return false;
}

// ============================================================================
// Helper Functions
// ============================================================================

static bool tiles_contact(const Tile& tile_u, Coord pos_u, const Tile& tile_v, Coord pos_v) {
    // Build sorted coordinate lists
    std::vector<Coord> coords_u = make_coords(tile_u, pos_u);
    std::vector<Coord> coords_v = make_coords(tile_v, pos_v);

    // Overlap?
    if (any_overlap_sorted(coords_u, coords_v)) return true;

    // 4-adjacent? (binary_search on coords_v)
    static const int dx_arr[4] = {1, -1, 0, 0};
    static const int dy_arr[4] = {0,  0, 1, -1};
    for (const auto& cu : coords_u) {
        for (int k = 0; k < 4; ++k) {
            Coord n{cu.first + dx_arr[k], cu.second + dy_arr[k]};
            if (std::binary_search(coords_v.begin(), coords_v.end(), n)) return true;
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
    sol.objective   = greedy_result.best_obj;
    sol.bbox_width  = greedy_result.bbox_width;
    sol.bbox_height = greedy_result.bbox_height;
    sol.bbox_area   = greedy_result.bbox_area;
    return sol;
}

static Solution create_stochastic_greedy_solution(const std::vector<Tile>& tiles, int start_index, unsigned int seed) {
    Solution sol;
    auto greedy_result = solve_greedy_stochastic(tiles, start_index, seed);

    for (const auto& p : greedy_result.placements) {
        sol.placements[p[0]] = {p[1], p[2]};
    }
    sol.objective   = greedy_result.best_obj;
    sol.bbox_width  = greedy_result.bbox_width;
    sol.bbox_height = greedy_result.bbox_height;
    sol.bbox_area   = greedy_result.bbox_area;
    return sol;
}

static Solution create_partial_stochastic_greedy_solution(const std::vector<Tile>& tiles, int start_index, unsigned int seed, int max_tiles) {
    Solution sol;
    auto greedy_result = solve_greedy_stochastic_partial(tiles, start_index, seed, max_tiles);

    for (const auto& p : greedy_result.placements) {
        sol.placements[p[0]] = {p[1], p[2]};
    }
    sol.objective   = greedy_result.best_obj;
    sol.bbox_width  = greedy_result.bbox_width;
    sol.bbox_height = greedy_result.bbox_height;
    sol.bbox_area   = greedy_result.bbox_area;
    return sol;
}

static void evaluate_solution(Solution& sol, const std::vector<Tile>& tiles) {
    // Allow partial solutions - don't require all tiles to be placed
    // if (sol.placements.size() != tiles.size()) {
    //     sol.objective = std::numeric_limits<int>::max();
    //     return;
    // }
    
    if (sol.placements.empty()) {
        sol.objective = std::numeric_limits<int>::max();
        sol.bbox_width = sol.bbox_height = sol.bbox_area = 0;
        return;
    }

    int xmin = std::numeric_limits<int>::max();
    int xmax = std::numeric_limits<int>::min();
    int ymin = std::numeric_limits<int>::max();
    int ymax = std::numeric_limits<int>::min();

    CellMap canvas;
    bool valid = true;

    // Only evaluate the tiles that are placed
    for (const auto& kv : sol.placements) {
        int i = kv.first;
        if (i < 0 || i >= (int)tiles.size()) { valid = false; break; }
        
        auto [x, y] = kv.second;
        CellMap placement = tiles[i].translate(x, y);

        for (const auto& cell_kv : placement) {
            const auto& coord = cell_kv.first;
            const auto& label = cell_kv.second;
            auto cit = canvas.find(coord);
            if (cit != canvas.end() && cit->second != label) { valid = false; break; }
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
        sol.bbox_width = sol.bbox_height = sol.bbox_area = 0;
    } else {
        sol.bbox_width  = xmax - xmin + 1;
        sol.bbox_height = ymax - ymin + 1;
        sol.bbox_area   = sol.bbox_width * sol.bbox_height;
        sol.objective   = std::max(sol.bbox_width, sol.bbox_height);
    }
}

// Build adjacency tree from a solution based on tile contact relationships
static Tree build_tree_from_solution(const Solution& sol, const std::vector<Tile>& tiles) {
    Tree tree;
    if (sol.placements.empty()) return tree;

    tree.root = sol.placements.begin()->first;

    const int n = (int)tiles.size();
    std::vector<char> placed(n, 0);
    std::vector<int>  order;

    if (tree.root >= 0 && tree.root < n) {
        placed[tree.root] = 1;
        order.push_back(tree.root);
    }

    size_t idx = 0;
    while (idx < order.size() && (int)order.size() < (int)sol.placements.size()) {
        int u = order[idx++];
        auto pos_u = sol.placements.at(u);

        for (const auto& pv : sol.placements) {
            int v = pv.first;
            if (v == u || placed[v]) continue;
            if (tiles_contact(tiles[u], pos_u, tiles[v], pv.second)) {
                tree.edges.emplace_back(u, v);
                placed[v] = 1;
                order.push_back(v);
            }
        }
    }
    return tree;
}

static Solution crossover_solutions(const Solution& parent1, const Solution& parent2,
                                    const std::vector<Tile>& tiles, std::mt19937& rng, int max_tiles_to_place = -1) {
    const int n = (int)tiles.size();
    Solution child;

    // If max_tiles_to_place is -1, place all tiles (default behavior)
    if (max_tiles_to_place < 0) max_tiles_to_place = n;

    // Build trees
    Tree t1 = build_tree_from_solution(parent1, tiles);
    Tree t2 = build_tree_from_solution(parent2, tiles);

    std::vector<int> visited(n, -1);
    int root = -1, root2 = -1;

    // Build adjacency as vectors (index by tile id) and shuffle for randomness
    std::vector<std::vector<int>> edges1(n), edges2(n);
    for (const auto& e : t1.edges) if (e.u>=0 && e.u<n) {
        edges1[e.u].push_back(e.v);
        visited[e.v] = e.v;
    }
    for (const auto& e : t2.edges) if (e.u>=0 && e.u<n) {
        edges2[e.u].push_back(e.v);
        if (visited[e.u] == e.v || visited[e.v] == e.u) {
            root = e.u;
            root2 = e.v;
        }
        
    }
    
    // Shuffle edges for more randomness in crossover
    for (int i = 0; i < n; ++i) {
        if (!edges1[i].empty()) std::shuffle(edges1[i].begin(), edges1[i].end(), rng);
        if (!edges2[i].empty()) std::shuffle(edges2[i].begin(), edges2[i].end(), rng);
    }

    // Placement bookkeeping (bitset + frontier)
    std::vector<char> placed(n, 0);
    std::vector<int>  frontier;
    CellMap child_canvas; // keep a running canvas for fast conflict checks

    // Seed root from parent1 (if present)
    if (root == -1) root = t1.root;
    auto itRoot = parent1.placements.find(root);
    if (itRoot != parent1.placements.end()) {
        child.placements[root] = itRoot->second;
        placed[root] = 1;
        frontier.push_back(root);

        // paint root
        CellMap pm = tiles[root].translate(itRoot->second.first, itRoot->second.second);
        for (const auto& kv : pm) child_canvas[kv.first] = kv.second;
    }

    // NEW: place v using u + (par[v] - par[u]) instead of absolute par[v]
    auto try_place_by_offset = [&](int u, int v, const Solution& par, CellMap& canvas) -> bool {
        if (!placed[u]) return false; // need u already placed in the child

        auto itu = par.placements.find(u);
        auto itv = par.placements.find(v);
        if (itu == par.placements.end() || itv == par.placements.end()) return false;

        // Δ from u -> v in the parent
        const int dx_rel = itv->second.first  - itu->second.first;
        const int dy_rel = itv->second.second - itu->second.second;

        // target position in the child
        const auto pu = child.placements[u];
        const std::pair<int,int> pos_v = { pu.first + dx_rel, pu.second + dy_rel };

        // translate and validate
        CellMap placement_v = tiles[v].translate(pos_v.first, pos_v.second);
        for (const auto& kv : placement_v) {
            auto cit = canvas.find(kv.first);
            if (cit != canvas.end() && cit->second != kv.second) return false; // conflict
        }

        // commit
        for (const auto& kv : placement_v) canvas[kv.first] = kv.second;
        child.placements[v] = pos_v;
        placed[v] = 1;
        frontier.push_back(v);
        return true;
    };

    if (root2 != -1) {
        // Try to seed root2 from parent2
        try_place_by_offset(root, root2, parent2, child_canvas);
        frontier.push_back(root2);
    }

    bool use_p1 = false; // we started with p1's root; next use p2
    std::vector<int> tried;

    while ((int)child.placements.size() < n && !frontier.empty()) {
        auto& cur_edges  = use_p1 ? edges1 : edges2;
        auto& cur_parent = use_p1 ? parent1 : parent2;

        bool found = false;
        tried.clear();

        while (!frontier.empty() && !found) {
            std::uniform_int_distribution<size_t> dist(0, frontier.size() - 1);
            size_t idx = dist(rng);
            int u = frontier[idx];

            if (!cur_edges[u].empty()) {
                for (int v : cur_edges[u]) {
                    if (v < 0 || v >= n) continue;
                    if (placed[v]) continue;
                    if (try_place_by_offset(u, v, cur_parent, child_canvas)) {
                        found = true;
                        break;
                    }
                }
            }
            if (!found) {
                tried.push_back(u);
                // Efficient removal using swap-pop
                std::swap(frontier[idx], frontier.back());
                frontier.pop_back();
            }
        }
        if (found) {
            frontier.insert(frontier.end(), tried.begin(), tried.end());
        }
        use_p1 = !use_p1;
    }

    // If one parent ran out of usable edges, sweep remaining edges from both parents
    auto sweep_parent = [&](const std::vector<std::vector<int>>& edges, const Solution& par) {
        bool made_progress = true;
        while (made_progress && (int)child.placements.size() < n) {
            made_progress = false;
            for (int u = 0; u < n; ++u) {
                if (!placed[u]) continue;
                for (int v : edges[u]) {
                    if (v < 0 || v >= n) continue;
                    if (placed[v]) continue;
                    if (try_place_by_offset(u, v, par, child_canvas)) {
                        made_progress = true;
                    }
                }
            }
        }
    };
    if ((int)child.placements.size() < n) sweep_parent(edges1, parent1);
    if ((int)child.placements.size() < n) sweep_parent(edges2, parent2);

    // Greedily add remaining tiles (no unordered_*; use vectors)
    // But respect max_tiles_to_place limit
    if ((int)child.placements.size() < n && (int)child.placements.size() < max_tiles_to_place) {
        std::vector<int> unplaced;
        unplaced.reserve(n);
        for (int i = 0; i < n; ++i) if (!placed[i]) unplaced.push_back(i);

        // Limit to max_tiles_to_place
        int tiles_to_add = max_tiles_to_place - (int)child.placements.size();
        tiles_to_add = std::min(tiles_to_add, (int)unplaced.size());

        if (tiles_to_add > 0) {
            // Build a reduced list & a direct map new_idx -> original_idx
            std::vector<Tile> remaining_tiles;
            remaining_tiles.reserve(unplaced.size());
            std::vector<int> new2orig; new2orig.reserve(unplaced.size());

            for (int idx : unplaced) {
                new2orig.push_back(idx);
                remaining_tiles.push_back(tiles[idx]);
            }

            if (!remaining_tiles.empty()) {
                GreedySolver greedy_solver(remaining_tiles);

                // Seed canvas from already placed tiles
                for (const auto& kv : child.placements) {
                    int idx = kv.first;
                    auto pos = kv.second;
                    CellMap pm = tiles[idx].translate(pos.first, pos.second);
                    greedy_solver.canvas.add_placement(pm);
                }

                // Add tiles greedily, selecting the best tile at each iteration
                std::vector<int> local_remaining;
                for (size_t i = 0; i < remaining_tiles.size(); ++i) {
                    local_remaining.push_back(i);
                }

                int added = 0;
                while (!local_remaining.empty() && added < tiles_to_add) {
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
                    // Keep expanding target until we find a placement - this guarantees we always place tiles
                    for (int target = std::max(current_size, max_tile_size); !found; ++target) {
                        
                        for (size_t j = 0; j < local_remaining.size(); ++j) {
                            int idx = local_remaining[j];
                            const Tile& tile = remaining_tiles[idx];
                            
                            std::vector<Coord> positions;
                            if (greedy_solver.canvas.is_empty()) {
                                if (std::max(tile.width(), tile.height()) <= target) positions.push_back({0, 0});
                            } else {
                                int sr = target;
                                for (int dx = greedy_solver.canvas.xmin - sr; dx <= greedy_solver.canvas.xmax + sr; ++dx) {
                                    for (int dy = greedy_solver.canvas.ymin - sr; dy <= greedy_solver.canvas.ymax + sr; ++dy) {
                                        positions.push_back({dx, dy});
                                    }
                                }
                            }
                            
                            for (const auto& p : positions) {
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
                                        best_global = PlacementChoice((int)idx, dx, dy, delta, overlap, std::move(placement));
                                        found = true;
                                    }
                                }
                            }
                            if (found) break;
                        }
                    }
                    
                    // best_global will always have a value now due to unlimited target expansion
                    int original_idx = new2orig[best_global->tile_idx];
                    child.placements[original_idx] = {best_global->dx, best_global->dy};
                    greedy_solver.canvas.add_placement(best_global->placement);
                    // also paint to child_canvas to keep consistency
                    for (const auto& kv : best_global->placement) child_canvas[kv.first] = kv.second;
                    local_remaining.erase(
                        std::remove(local_remaining.begin(), local_remaining.end(), best_global->tile_idx),
                        local_remaining.end()
                    );
                    added++;
                }
        }
        }  // close if (tiles_to_add > 0)
    }  // close if ((int)child.placements.size() < n && ...)

    evaluate_solution(child, tiles);
    return child;
}

// ============================================================================
// Genetic Algorithm Main Function (unchanged except we didn’t use unordered_*)
// ============================================================================

GeneticResult solve_genetic(const std::vector<Tile>& tiles,
                            int population_size,
                            int num_generations,
                            int start_index) {
    auto start_time = std::chrono::high_resolution_clock::now();

    std::cout << "\n=== Genetic Algorithm Started (Partial Population Mode) ===\n";
    std::cout << "Population size: " << population_size << "\n";
    std::cout << "Generations: " << num_generations << "\n";
    std::cout << "Tiles: " << tiles.size() << "\n\n";

    std::mt19937 rng(std::random_device{}());

    // Calculate progressive tile placement schedule
    // Start with a fraction of tiles and gradually increase to all tiles
    int total_tiles = tiles.size();
    int initial_tiles = std::max(5, total_tiles / 4);  // Start with 25% of tiles (min 5)
    
    std::cout << "Progressive tile placement schedule:\n";
    std::cout << "  Initial tiles: " << initial_tiles << " / " << total_tiles << "\n";
    std::cout << "  Gradual linear increase across all generations\n";
    std::cout << "  Final generation will require all " << total_tiles << " tiles\n\n";

    // Initialize population with partial stochastic greedy solutions
    std::cout << "Initializing population with partial stochastic greedy (parallel)...\n";
    std::vector<Solution> population(population_size);
    
    // Pre-generate seeds and starting indices
    std::vector<unsigned int> seeds(population_size);
    std::vector<int> start_indices(population_size);
    for (int i = 0; i < population_size; ++i) {
        seeds[i] = rng();
        start_indices[i] = (start_index >= 0 ? (start_index + i) : i) % std::max<int>(1, (int)tiles.size());
    }
    
    // Progress tracking
    std::mutex progress_mutex;
    int completed = 0;
    
    // Generate initial partial solutions in parallel using OpenMP
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < population_size; ++i) {
        population[i] = create_partial_stochastic_greedy_solution(tiles, start_indices[i], seeds[i], initial_tiles);
        
        // Thread-safe progress update
        {
            std::lock_guard<std::mutex> lock(progress_mutex);
            completed++;
            if (completed % 16 == 0 || completed == population_size) {
                std::cout << "  Created " << completed << "/" << population_size << " partial solutions\n";
            }
        }
    }

    Solution best_solution = population[0];
    for (const auto& s : population) if (s.objective < best_solution.objective) best_solution = s;

    std::cout << "Initial best objective: " << best_solution.objective << "\n";
    std::cout << "Initial best bounding box: " << best_solution.bbox_width << " × " << best_solution.bbox_height << "\n";
    std::cout << "Initial placed tiles: " << best_solution.placements.size() << " / " << total_tiles << "\n\n";

    // Evolution loop with progressive tile placement
    std::cout << "Starting evolution with progressive tile placement...\n";
    for (int gen = 0; gen < num_generations; ++gen) {
        // Calculate target number of tiles for this generation
        // Linear progression from initial_tiles to total_tiles across all generations
        double progress = (double)(gen + 1) / num_generations;
        int target_tiles = initial_tiles + (int)(progress * (total_tiles - initial_tiles));
        // make target_tiles multiple of 16
        target_tiles = ((target_tiles + 15) / 16) * 16;
        
        // Ensure we reach all tiles by the final generation
        if (gen == num_generations - 1) {
            target_tiles = total_tiles;
        }
        
        std::vector<Solution> new_population(population_size);
        
        // Pre-generate parent pairs using stochastic tournament selection
        std::vector<std::pair<int, int>> parent_pairs(population_size);
        std::vector<bool> do_crossover(population_size);
        std::uniform_real_distribution<double> crossover_prob(0.0, 1.0);
        const double crossover_rate = 0.5; // 50% crossover probability
        const int tournament_size = 3; // Tournament selection with 3 individuals
        
        for (int i = 0; i < population_size; ++i) {
            // Tournament selection for parent 1
            std::uniform_int_distribution<int> pop_dist(0, population_size - 1);
            int best_p1 = pop_dist(rng);
            for (int t = 1; t < tournament_size; ++t) {
                int candidate = pop_dist(rng);
                if (population[candidate].objective < population[best_p1].objective) {
                    best_p1 = candidate;
                }
            }
            
            // Tournament selection for parent 2
            int best_p2 = pop_dist(rng);
            for (int t = 1; t < tournament_size; ++t) {
                int candidate = pop_dist(rng);
                if (population[candidate].objective < population[best_p2].objective) {
                    best_p2 = candidate;
                }
            }
            
            parent_pairs[i] = {best_p1, best_p2};
            do_crossover[i] = crossover_prob(rng) < crossover_rate;
        }
        
        // Parallel crossover with reduced probability
        #pragma omp parallel for schedule(static)
        for (int i = 0; i < population_size; ++i) {
            if (do_crossover[i]) {
                // Create a thread-local RNG with a unique seed for this iteration
                std::mt19937 local_rng(rng() + i);
                int p1 = parent_pairs[i].first;
                int p2 = parent_pairs[i].second;
                new_population[i] = crossover_solutions(population[p1], population[p2], tiles, local_rng, target_tiles);
            } else {
                // Direct copy from elite parent (no crossover)
                int p1 = parent_pairs[i].first;
                new_population[i] = population[p1];
            }
        }
        
        // Apply greedy completion to ALL solutions to reach target_tiles
        // In the final generation, ensure all solutions have all tiles
        bool is_final_generation = (gen == num_generations - 1);
        int completion_target = is_final_generation ? total_tiles : target_tiles;
        std::vector<int> tiles_added_per_solution(population_size, 0);
        
        #pragma omp parallel for schedule(static)
        for (int i = 0; i < population_size; ++i) {
            if ((int)new_population[i].placements.size() < completion_target) {
                // Build list of unplaced tiles
                std::vector<int> unplaced;
                std::vector<char> is_placed(tiles.size(), 0);
                for (const auto& kv : new_population[i].placements) {
                    is_placed[kv.first] = 1;
                }
                for (size_t j = 0; j < tiles.size(); ++j) {
                    if (!is_placed[j]) unplaced.push_back(j);
                }
                
                int tiles_to_add = completion_target - new_population[i].placements.size();
                tiles_to_add = std::min(tiles_to_add, (int)unplaced.size());
                
                if (tiles_to_add > 0 && !unplaced.empty()) {
                    // Use greedy to add more tiles
                    std::vector<Tile> remaining_tiles;
                    std::vector<int> new2orig;
                    for (int idx : unplaced) {
                        new2orig.push_back(idx);
                        remaining_tiles.push_back(tiles[idx]);
                    }
                    
                    if (!remaining_tiles.empty()) {
                        GreedySolver greedy_solver(remaining_tiles);
                        
                        // Seed canvas from already placed tiles
                        for (const auto& kv : new_population[i].placements) {
                            int idx = kv.first;
                            auto pos = kv.second;
                            CellMap pm = tiles[idx].translate(pos.first, pos.second);
                            greedy_solver.canvas.add_placement(pm);
                        }
                        
                        // Add tiles up to the limit
                        std::vector<int> local_remaining;
                        for (size_t j = 0; j < remaining_tiles.size(); ++j) {
                            local_remaining.push_back(j);
                        }
                        
                        int added = 0;
                        while (!local_remaining.empty() && added < tiles_to_add) {
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
                            for (int target = std::max(current_size, max_tile_size);
                                 target <= current_size + max_tile_size * 2 && !found; ++target) {
                                
                                for (size_t j = 0; j < local_remaining.size(); ++j) {
                                    int idx = local_remaining[j];
                                    const Tile& tile = remaining_tiles[idx];
                                    
                                    std::vector<Coord> positions;
                                    if (greedy_solver.canvas.is_empty()) {
                                        if (std::max(tile.width(), tile.height()) <= target) positions.push_back({0, 0});
                                    } else {
                                        int sr = target;
                                        for (int dx = greedy_solver.canvas.xmin - sr; dx <= greedy_solver.canvas.xmax + sr; ++dx) {
                                            for (int dy = greedy_solver.canvas.ymin - sr; dy <= greedy_solver.canvas.ymax + sr; ++dy) {
                                                positions.push_back({dx, dy});
                                            }
                                        }
                                    }
                                    
                                    for (const auto& p : positions) {
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
                                                best_global = PlacementChoice((int)idx, dx, dy, delta, overlap, std::move(placement));
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
                                new_population[i].placements[original_idx] = {best_global->dx, best_global->dy};
                                greedy_solver.canvas.add_placement(best_global->placement);
                                local_remaining.erase(
                                    std::remove(local_remaining.begin(), local_remaining.end(), best_global->tile_idx),
                                    local_remaining.end()
                                );
                                added++;
                                tiles_added_per_solution[i]++;
                            } else {
                                break;
                            }
                        }
                        
                        // Re-evaluate the solution
                        evaluate_solution(new_population[i], tiles);
                    }
                }
            }
        }
        
        // Calculate and log statistics about greedy tile additions
        int solutions_needing_tiles = 0;
        int total_tiles_added = 0;
        for (int i = 0; i < population_size; ++i) {
            if (tiles_added_per_solution[i] > 0) {
                solutions_needing_tiles++;
                total_tiles_added += tiles_added_per_solution[i];
            }
        }
        
        if (solutions_needing_tiles > 0) {
            double avg_tiles_added = (double)total_tiles_added / solutions_needing_tiles;
            double avg_pct_of_target = (completion_target > 0) ? (avg_tiles_added / completion_target * 100.0) : 0.0;
            std::cout << "  Greedy completion: " << solutions_needing_tiles << "/" << population_size 
                      << " solutions needed tiles, avg " << std::fixed << std::setprecision(1) 
                      << avg_tiles_added << " tiles/solution"
                      << " (" << std::fixed << std::setprecision(1) << avg_pct_of_target << "% of target)\n";
        }
        
        population.swap(new_population);
        
        // Update best_solution after swap (check the new population)
        std::sort(population.begin(), population.end(), [](const Solution& a, const Solution& b) {
            return a.objective < b.objective;
        });
        bool improved = false;
        if (population[0].objective < best_solution.objective) {
            best_solution = population[0];
            improved = true;
        }
        
        // Print generation statistics
        {
            auto now = std::chrono::high_resolution_clock::now();
            std::chrono::duration<double> elapsed = now - start_time;
            double avg = 0.0; for (const auto& s : population) avg += s.objective; avg /= population.size();
            double avg_placed = 0.0; for (const auto& s : population) avg_placed += s.placements.size(); avg_placed /= population.size();
            
            // Best in current population (population is already sorted, so population[0] is best)
            const Solution& pop_best = population[0];

            std::cout << "Gen " << std::setw(3) << (gen + 1) << "/" << num_generations
                      << " | Target tiles: " << std::setw(3) << target_tiles << "/" << total_tiles
                      << " | Best: " << pop_best.objective
                      << " (" << pop_best.bbox_width << "×" << pop_best.bbox_height << ")"
                      << " [" << pop_best.placements.size() << " tiles]"
                      << " | Pop avg: " << std::fixed << std::setprecision(1) << avg
                      << " | Avg placed: " << std::fixed << std::setprecision(1) << avg_placed
                      << " | Time: " << std::fixed << std::setprecision(1) << elapsed.count() << "s"
                      << (improved ? " [IMPROVED]" : "") << "\n";
        }
    }

    // Final evaluation
    std::cout << "\nFinal evaluation...\n";
    std::sort(population.begin(), population.end(),
              [](const Solution& a, const Solution& b){ return a.objective < b.objective; });
    if (population[0].objective < best_solution.objective) {
        best_solution = population[0];
        std::cout << "Final improvement found!\n";
    }

    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;

    std::cout << "\n=== Genetic Algorithm Completed ===\n";
    std::cout << "Final best objective: " << best_solution.objective << "\n";
    std::cout << "Final bounding box: " << best_solution.bbox_width << " × " << best_solution.bbox_height << "\n";
    std::cout << "Final placed tiles: " << best_solution.placements.size() << " / " << tiles.size() << "\n";
    std::cout << "Total runtime: " << std::fixed << std::setprecision(3) << elapsed.count() << " seconds\n\n";

    GeneticResult result;
    result.best_obj        = best_solution.objective;
    result.bbox_width      = best_solution.bbox_width;
    result.bbox_height     = best_solution.bbox_height;
    result.bbox_area       = best_solution.bbox_area;
    result.wall_time_sec   = elapsed.count();
    result.generations     = num_generations;
    result.population_size = population_size;

    for (const auto& kv : best_solution.placements) {
        result.placements.push_back({kv.first, kv.second.first, kv.second.second});
    }
    return result;
}
