#ifndef MDSSP_GREEDY_HPP
#define MDSSP_GREEDY_HPP

#include "common.hpp"
#include <optional>
#include <sstream>
#include <random>

// ============================================================================
// Canvas Class
// ============================================================================

class Canvas {
public:
    CellMap cells;
    int xmin, xmax, ymin, ymax;
    
    Canvas();
    
    bool is_empty() const;
    int bbox_area() const;
    void add_placement(const CellMap& placement);
    std::pair<bool, int> overlap_check(const CellMap& placement) const;
    std::string render_ascii(int pad = 1) const;
};

// ============================================================================
// Placement Choice
// ============================================================================

struct PlacementChoice {
    int tile_idx;
    int dx, dy;
    int delta_area;
    int overlap;
    CellMap placement;
    
    PlacementChoice(int idx, int dx_, int dy_, int da, int ov, CellMap pl);
};

// ============================================================================
// Greedy Solver
// ============================================================================

class GreedySolver {
public:
    std::vector<Tile> tiles;
    int n;
    Canvas canvas;
    std::vector<std::optional<std::pair<int, int>>> placed;
    std::vector<int> order;
    
    explicit GreedySolver(std::vector<Tile> tiles_);
    
    Canvas solve(int start_index = 0);
};

// ============================================================================
// Stochastic Greedy Solver
// ============================================================================

class StochasticGreedySolver {
public:
    std::vector<Tile> tiles;
    int n;
    Canvas canvas;
    std::vector<std::optional<std::pair<int, int>>> placed;
    std::vector<int> order;
    std::mt19937 rng;
    
    explicit StochasticGreedySolver(std::vector<Tile> tiles_, unsigned int seed);
    
    Canvas solve(int start_index = 0);
};

// ============================================================================
// Solve Result
// ============================================================================

struct GreedyResult {
    int best_obj;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    double wall_time_sec;
    std::vector<std::vector<int>> placements;
    std::vector<int> order;
    int canvas_xmin, canvas_xmax, canvas_ymin, canvas_ymax;
};

GreedyResult solve_greedy(const std::vector<Tile>& tiles, int start_index = 0);
GreedyResult solve_greedy_stochastic(const std::vector<Tile>& tiles, int start_index = 0, unsigned int seed = 0);
GreedyResult solve_greedy_merge(const std::vector<Tile>& tiles);

// Partial greedy solver (places only a subset of tiles)
GreedyResult solve_greedy_partial(const std::vector<Tile>& tiles, int start_index, int max_tiles);
GreedyResult solve_greedy_stochastic_partial(const std::vector<Tile>& tiles, int start_index, unsigned int seed, int max_tiles);

#endif // MDSSP_GREEDY_HPP
