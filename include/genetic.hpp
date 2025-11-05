#ifndef MDSSP_GENETIC_HPP
#define MDSSP_GENETIC_HPP

#include "common.hpp"
#include "greedy.hpp"
#include <set>
#include <tuple>
#include <optional>

// ============================================================================
// Genetic Algorithm Data Structures
// ============================================================================

struct Solution {
    std::unordered_map<int, Coord> placements;  // tile_idx -> (x, y)
    int objective;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    
    Solution() : objective(0), bbox_width(0), bbox_height(0), bbox_area(0) {}
};

struct Edge {
    int u;  // parent tile
    int v;  // child tile
    
    Edge(int u_, int v_) : u(u_), v(v_) {}
};

struct Tree {
    std::vector<Edge> edges;
    int root;
    
    Tree() : root(0) {}
};

// ============================================================================
// Genetic Algorithm Result
// ============================================================================

struct GeneticResult {
    int best_obj;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    double wall_time_sec;
    std::vector<std::vector<int>> placements;
    int generations;
    int population_size;
    
    GeneticResult() : best_obj(0), bbox_width(0), bbox_height(0), 
                      bbox_area(0), wall_time_sec(0.0), 
                      generations(0), population_size(0) {}
};

// ============================================================================
// Genetic Solver Function
// ============================================================================

GeneticResult solve_genetic(const std::vector<Tile>& tiles, 
                            int population_size = 10, 
                            int num_generations = 20,
                            int start_index = 0);

#endif // MDSSP_GENETIC_HPP
