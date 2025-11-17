#ifndef MDSSP_BRANCH_AND_BOUND_HPP
#define MDSSP_BRANCH_AND_BOUND_HPP

#include "common.hpp"
#include <vector>
#include <unordered_map>
#include <set>
#include <limits>

// ============================================================================
// Branch and Bound Data Structures
// ============================================================================

// Edge in adjacency list: (tile_index, offset_x, offset_y)
struct AdjEdge {
    int tile_idx;
    int offset_x;
    int offset_y;
    
    AdjEdge(int idx, int ox, int oy) : tile_idx(idx), offset_x(ox), offset_y(oy) {}
};

// Tree edge: (parent, child, offset)
struct TreeEdge {
    int parent;
    int child;
    int offset_x;
    int offset_y;
    
    TreeEdge(int p, int c, int ox, int oy) : parent(p), child(c), offset_x(ox), offset_y(oy) {}
};

// Bounding box
struct BBox {
    int xmin, xmax, ymin, ymax;
    
    BBox() : xmin(std::numeric_limits<int>::max()), 
             xmax(std::numeric_limits<int>::min()),
             ymin(std::numeric_limits<int>::max()),
             ymax(std::numeric_limits<int>::min()) {}
    
    int width() const { return xmax - xmin + 1; }
    int height() const { return ymax - ymin + 1; }
    int side_length() const { return std::max(width(), height()); }
};

// Partial solution state
struct BnBState {
    std::set<int> placed;                      // tiles already placed
    std::unordered_map<int, Coord> positions;  // tile_idx -> (x, y)
    BBox bbox;                                 // current bounding box
    std::vector<TreeEdge> tree_edges;          // edges in the tree
    CellMap canvas;                            // occupied cells with symbols
    
    BnBState() = default;
};

// Result structure
struct BranchAndBoundResult {
    int best_obj;              // best side length found
    int bbox_width;
    int bbox_height;
    int bbox_area;
    double wall_time_sec;
    std::vector<std::vector<int>> placements;  // [tile_idx, x, y]
    long long nodes_explored;
    long long nodes_pruned;
    
    BranchAndBoundResult() : best_obj(std::numeric_limits<int>::max()), 
                              bbox_width(0), bbox_height(0), bbox_area(0),
                              wall_time_sec(0.0), nodes_explored(0), nodes_pruned(0) {}
};

// ============================================================================
// Branch and Bound Solver
// ============================================================================

BranchAndBoundResult solve_branch_and_bound(
    const std::vector<Tile>& tiles,
    int root_tile = 0,
    double time_limit_sec = 300.0,
    int initial_upper_bound = std::numeric_limits<int>::max()
);

#endif // MDSSP_BRANCH_AND_BOUND_HPP
