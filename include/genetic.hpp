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

// TreeEdge: Represents parent-child relationship with relative offset
struct TreeEdge {
    int parent;      // parent tile index
    int child;       // child tile index
    int dx;          // relative x offset from parent
    int dy;          // relative y offset from parent
    
    TreeEdge() : parent(-1), child(-1), dx(0), dy(0) {}
    TreeEdge(int p, int c, int dx_, int dy_) 
        : parent(p), child(c), dx(dx_), dy(dy_) {}
};

// PlacementTree: The genotype for the genetic algorithm
// Represents a spanning tree of tile placements with relative offsets
struct PlacementTree {
    int root;                      // root tile index
    std::vector<TreeEdge> edges;   // parent-child edges with offsets
    int num_tiles;                 // number of tiles in the tree
    
    PlacementTree() : root(0), num_tiles(0) {}
    PlacementTree(int r, int n) : root(r), num_tiles(n) {}
};

// Solution: Decoded phenotype from a PlacementTree
struct Solution {
    std::unordered_map<int, Coord> placements;  // tile_idx -> (x, y)
    int objective;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    
    Solution() : objective(0), bbox_width(0), bbox_height(0), bbox_area(0) {}
};

// PlacementGraph: Pre-computed valid placements between tiles
struct PlacementGraph {
    struct ValidPlacement {
        int dx;  // offset x
        int dy;  // offset y
    };
    
    // adjacency[u][v] = list of valid offsets to place v relative to u
    std::vector<std::vector<std::vector<ValidPlacement>>> adjacency;
    int num_tiles;
    
    PlacementGraph(int n) : num_tiles(n) {
        adjacency.resize(n, std::vector<std::vector<ValidPlacement>>(n));
    }
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
    int total_crossovers;
    int crossovers_needing_completion;
    int total_tiles_completed;
    
    GeneticResult() : best_obj(0), bbox_width(0), bbox_height(0), 
                      bbox_area(0), wall_time_sec(0.0), 
                      generations(0), population_size(0),
                      total_crossovers(0), crossovers_needing_completion(0),
                      total_tiles_completed(0) {}
};

// ============================================================================
// Population Initialization Mode
// ============================================================================

enum class InitMode {
    STOCHASTIC_GREEDY,  // Default: Use stochastic greedy for initialization
    GREEDY,             // Use deterministic greedy with different start indices
    RANDOM              // Use random placement (future implementation)
};

// ============================================================================
// Genetic Solver Functions
// ============================================================================

// Build placement graph (pre-compute valid tile placements)
PlacementGraph build_placement_graph(const std::vector<Tile>& tiles);

// Convert PlacementTree to Solution (decode genotype to phenotype)
Solution decode_tree(const PlacementTree& tree, const std::vector<Tile>& tiles);

// Tree-based genetic algorithm solver
GeneticResult solve_genetic(const std::vector<Tile>& tiles, 
                            int population_size = 10, 
                            int num_generations = 20,
                            int start_index = 0,
                            InitMode init_mode = InitMode::STOCHASTIC_GREEDY);

#endif // MDSSP_GENETIC_HPP
