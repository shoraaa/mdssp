#include "genetic.hpp"
#include <chrono>
#include <random>
#include <algorithm>
#include <cmath>
#include <unordered_set>

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

static Solution crossover_solutions(const Solution& parent1, const Solution& parent2, 
                                    const std::vector<Tile>& tiles, std::mt19937& rng) {
    Solution child;
    
    // Simple crossover: take placements from parent1, fill missing with parent2
    child.placements = parent1.placements;
    
    for (const auto& [idx, pos] : parent2.placements) {
        if (!child.placements.count(idx)) {
            child.placements[idx] = pos;
        }
    }
    
    // If still incomplete, use greedy to fill
    if (child.placements.size() < tiles.size()) {
        auto greedy_sol = create_greedy_solution(tiles);
        for (size_t i = 0; i < tiles.size(); ++i) {
            if (!child.placements.count(i)) {
                child.placements[i] = greedy_sol.placements[i];
            }
        }
    }
    
    evaluate_solution(child, tiles);
    return child;
}

static Solution mutate_solution(const Solution& sol, const std::vector<Tile>& tiles, 
                                std::mt19937& rng) {
    Solution mutated = sol;
    
    // Small mutation: shift a random tile
    if (!mutated.placements.empty()) {
        std::uniform_int_distribution<int> tile_dist(0, tiles.size() - 1);
        int tile_idx = tile_dist(rng);
        
        std::uniform_int_distribution<int> shift_dist(-2, 2);
        auto& pos = mutated.placements[tile_idx];
        pos.first += shift_dist(rng);
        pos.second += shift_dist(rng);
        
        evaluate_solution(mutated, tiles);
    }
    
    return mutated;
}

// ============================================================================
// Genetic Algorithm Main Function
// ============================================================================

GeneticResult solve_genetic(const std::vector<Tile>& tiles, 
                            int population_size, 
                            int num_generations,
                            int start_index) {
    auto start_time = std::chrono::high_resolution_clock::now();
    
    std::mt19937 rng(std::random_device{}());
    
    // Initialize population with greedy solutions from different starting points
    std::vector<Solution> population;
    population.reserve(population_size);
    
    for (int i = 0; i < population_size; ++i) {
        int start = i % tiles.size();
        auto sol = create_greedy_solution(tiles, start);
        population.push_back(sol);
    }
    
    Solution best_solution = population[0];
    for (const auto& sol : population) {
        if (sol.objective < best_solution.objective) {
            best_solution = sol;
        }
    }
    
    // Evolution loop
    for (int gen = 0; gen < num_generations; ++gen) {
        // Sort population by objective
        std::sort(population.begin(), population.end(), 
                 [](const Solution& a, const Solution& b) {
                     return a.objective < b.objective;
                 });
        
        // Update best
        if (population[0].objective < best_solution.objective) {
            best_solution = population[0];
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
    std::sort(population.begin(), population.end(), 
             [](const Solution& a, const Solution& b) {
                 return a.objective < b.objective;
             });
    
    if (population[0].objective < best_solution.objective) {
        best_solution = population[0];
    }
    
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end_time - start_time;
    
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
