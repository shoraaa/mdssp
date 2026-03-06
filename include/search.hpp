#ifndef MDSSP_SEARCH_HPP
#define MDSSP_SEARCH_HPP

#include "common.hpp"
#include "greedy.hpp"
#include "genetic.hpp"
#include <optional>

// ============================================================================
// Search Algorithm Results
// ============================================================================

struct SearchResult {
    int best_obj;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    double wall_time_sec;
    std::vector<std::vector<int>> placements;
    
    // Algorithm-specific stats
    int iterations;
    int states_explored;
    int improvements_found;
    
    SearchResult() : best_obj(0), bbox_width(0), bbox_height(0), 
                     bbox_area(0), wall_time_sec(0.0),
                     iterations(0), states_explored(0), improvements_found(0) {}
};

// ============================================================================
// Beam Search Algorithm
// ============================================================================

/**
 * Beam Search for MDSSP
 * 
 * Maintains a beam of the k best partial solutions at each step.
 * Uses the tree-based representation where each state is a PlacementTree
 * being constructed incrementally by adding tiles one at a time.
 * 
 * @param tiles The tiles to place
 * @param beam_width Number of best states to keep at each step (default 10)
 * @param seed Random seed for tie-breaking (0 = random)
 * @param obj_type Objective function type
 * @return SearchResult containing the best solution found
 */
SearchResult solve_beam_search(const std::vector<Tile>& tiles,
                               int beam_width = 10,
                               unsigned int seed = 0,
                               ObjectiveType obj_type = ObjectiveType::BOUNDING_SQUARE);

// ============================================================================
// Simulated Annealing Algorithm
// ============================================================================

/**
 * Simulated Annealing for MDSSP
 * 
 * Uses the tree-based representation. Starts from a greedy solution and
 * applies local moves (edge rewiring, offset changes) with acceptance
 * probability based on temperature schedule.
 * 
 * @param tiles The tiles to place
 * @param initial_temp Initial temperature (default 100.0)
 * @param cooling_rate Temperature decay per iteration (default 0.995)
 * @param min_temp Minimum temperature to stop (default 0.1)
 * @param max_iterations Maximum iterations (default 10000)
 * @param seed Random seed (0 = random)
 * @param obj_type Objective function type
 * @return SearchResult containing the best solution found
 */
SearchResult solve_simulated_annealing(const std::vector<Tile>& tiles,
                                        double initial_temp = 100.0,
                                        double cooling_rate = 0.995,
                                        double min_temp = 0.1,
                                        int max_iterations = 10000,
                                        unsigned int seed = 0,
                                        ObjectiveType obj_type = ObjectiveType::BOUNDING_SQUARE);

#endif // MDSSP_SEARCH_HPP
