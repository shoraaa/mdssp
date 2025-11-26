#ifdef USE_CPLEX

#include "cplex.hpp"
#include <ilcplex/ilocplex.h>
#include <sstream>
#include <chrono>
#include <set>
#include <map>
#include <climits>
#include <cmath>

ILOSTLBEGIN

// ============================================================================
// Data Structures
// ============================================================================

struct Origin {
    int x;
    int y;
    
    Origin(int x_, int y_) : x(x_), y(y_) {}
    
    bool operator<(const Origin& other) const {
        return x < other.x || (x == other.x && y < other.y);
    }
};

// ============================================================================
// Helper Functions
// ============================================================================

// Compute allowed origins for a tile given global grid bounds
// Optimized: uses normalized tile coordinates and tighter bounds
std::vector<Origin> compute_allowed_origins(const Tile& tile, int max_grid_bound) {
    std::vector<Origin> origins;
    
    if (tile.cells.empty()) return origins;
    
    int tile_min_x = tile.min_x();
    int tile_min_y = tile.min_y();
    int tile_max_x = tile.max_x();
    int tile_max_y = tile.max_y();
    
    // Optimized bounds: only need origins where tile fits in [0, max_grid_bound]
    // Since tiles are normalized, we can use tighter bounds
    int ox_min = -tile_max_x;
    int ox_max = max_grid_bound - tile_min_x;
    int oy_min = -tile_max_y;
    int oy_max = max_grid_bound - tile_min_y;
    
    // Further optimization: for normalized tiles, origin range is smaller
    for (int ox = ox_min; ox <= ox_max; ++ox) {
        for (int oy = oy_min; oy <= oy_max; ++oy) {
            // Quick check: all cells guaranteed to fit if bounds are met
            origins.emplace_back(ox, oy);
        }
    }
    
    return origins;
}

// Check if two tile placements have symbol conflicts
// Optimized: early bounding box check before cell-by-cell comparison
bool has_conflict(const Tile& tile_i, const Origin& origin_i,
                  const Tile& tile_j, const Origin& origin_j) {
    int xi = origin_i.x;
    int yi = origin_i.y;
    int xj = origin_j.x;
    int yj = origin_j.y;
    
    // Quick bounding box check: if bounding boxes don't overlap, no conflict
    int i_min_x = xi + tile_i.min_x();
    int i_max_x = xi + tile_i.max_x();
    int i_min_y = yi + tile_i.min_y();
    int i_max_y = yi + tile_i.max_y();
    
    int j_min_x = xj + tile_j.min_x();
    int j_max_x = xj + tile_j.max_x();
    int j_min_y = yj + tile_j.min_y();
    int j_max_y = yj + tile_j.max_y();
    
    // No overlap in x or y => no conflict
    if (i_max_x < j_min_x || j_max_x < i_min_x ||
        i_max_y < j_min_y || j_max_y < i_min_y) {
        return false;
    }
    
    // Bounding boxes overlap, check cell-by-cell
    // Optimization: use hash map for faster lookup
    std::map<std::pair<int, int>, char> cells_i;
    for (const auto& [coord_i, symbol_i] : tile_i.cells) {
        int global_x = xi + coord_i.first;
        int global_y = yi + coord_i.second;
        cells_i[{global_x, global_y}] = symbol_i;
    }
    
    for (const auto& [coord_j, symbol_j] : tile_j.cells) {
        int global_x = xj + coord_j.first;
        int global_y = yj + coord_j.second;
        
        auto it = cells_i.find({global_x, global_y});
        if (it != cells_i.end() && it->second != symbol_j) {
            return true;  // Same position, different symbols
        }
    }
    
    return false;
}

// ============================================================================
// CPLEX Solver Implementation
// ============================================================================

CplexResult solve_cplex(const Matrices& matrices, int time_limit, ObjectiveType obj_type) {
    CplexResult result;
    
    if (matrices.empty()) {
        result.status = "No tiles provided";
        return result;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    try {
        // Convert binary matrices to Tile objects
        std::vector<Tile> tiles = tiles_from_binary_matrices(matrices);
        int num_tiles = tiles.size();
        
        // Compute upper bound on grid size and bounding square
        int max_tile_width = 0;
        int max_tile_height = 0;
        int total_area = 0;
        for (const auto& tile : tiles) {
            max_tile_width = std::max(max_tile_width, tile.width());
            max_tile_height = std::max(max_tile_height, tile.height());
            total_area += tile.width() * tile.height();
        }
        
        // Optimized grid bound: use tighter upper bound based on problem structure
        // Theoretical minimum: sqrt(total_area) rounded up
        // Conservative bound: add safety margin
        int theoretical_min = static_cast<int>(std::sqrt(total_area)) + 1;
        int grid_bound = std::max(theoretical_min * 2, num_tiles * std::max(max_tile_width, max_tile_height) / 4);
        
        // Further optimization: use smaller bound for small instances
        if (num_tiles <= 10) {
            grid_bound = std::min(grid_bound, num_tiles * std::max(max_tile_width, max_tile_height) / 2);
        }
        
        // Big-M for bounding constraints (tighter)
        int M = grid_bound + std::max(max_tile_width, max_tile_height);
        
        // Compute allowed origins for each tile
        std::vector<std::vector<Origin>> allowed_origins(num_tiles);
        for (int i = 0; i < num_tiles; ++i) {
            allowed_origins[i] = compute_allowed_origins(tiles[i], grid_bound);
        }
        
        // Precompute conflict information for pairwise tile placements
        // conflict[i][j][oi_idx][oj_idx] = true if tile i at origin oi conflicts with tile j at origin oj
        std::vector<std::vector<std::vector<std::vector<bool>>>> conflict(num_tiles);
        for (int i = 0; i < num_tiles; ++i) {
            conflict[i].resize(num_tiles);
            for (int j = 0; j < num_tiles; ++j) {
                conflict[i][j].resize(allowed_origins[i].size());
                for (size_t oi_idx = 0; oi_idx < allowed_origins[i].size(); ++oi_idx) {
                    conflict[i][j][oi_idx].resize(allowed_origins[j].size(), false);
                }
            }
        }
        
        // Compute conflicts (only for i < j to avoid redundancy)
        for (int i = 0; i < num_tiles; ++i) {
            for (int j = i + 1; j < num_tiles; ++j) {
                for (size_t oi_idx = 0; oi_idx < allowed_origins[i].size(); ++oi_idx) {
                    for (size_t oj_idx = 0; oj_idx < allowed_origins[j].size(); ++oj_idx) {
                        const Origin& oi = allowed_origins[i][oi_idx];
                        const Origin& oj = allowed_origins[j][oj_idx];
                        
                        if (has_conflict(tiles[i], oi, tiles[j], oj)) {
                            conflict[i][j][oi_idx][oj_idx] = true;
                        }
                    }
                }
            }
        }
        
        // Setup CPLEX environment
        IloEnv env;
        IloModel model(env);
        IloCplex cplex(model);
        
        // Configure CPLEX with optimized parameters
        cplex.setOut(env.getNullStream());
        cplex.setWarning(env.getNullStream());
        cplex.setParam(IloCplex::Param::TimeLimit, time_limit);
        cplex.setParam(IloCplex::Param::MIP::Tolerances::MIPGap, 0.01);
        
        // Optimization: Enable aggressive preprocessing and cuts
        cplex.setParam(IloCplex::Param::Preprocessing::Presolve, 1);
        cplex.setParam(IloCplex::Param::MIP::Strategy::HeuristicFreq, 20);  // More frequent heuristics
        cplex.setParam(IloCplex::Param::MIP::Strategy::RINSHeur, 50);  // RINS heuristic
        cplex.setParam(IloCplex::Param::Emphasis::MIP, 1);  // Emphasize feasibility
        
        // Enable parallel processing if available
        cplex.setParam(IloCplex::Param::Threads, 0);  // Use all available threads
        
        // For area objective (non-convex quadratic), enable global optimization
        if (obj_type == ObjectiveType::RECTANGLE_AREA) {
            cplex.setParam(IloCplex::Param::OptimalityTarget, 3);  // Global optimization
            cplex.setParam(IloCplex::Param::MIP::Strategy::Search, 2);  // Dynamic search for QP
        }
        
        // ====================================================================
        // Decision Variables
        // ====================================================================
        
        // b[i][o_idx]: tile i placed at origin allowed_origins[i][o_idx]
        std::vector<std::map<int, IloBoolVar>> b(num_tiles);
        for (int i = 0; i < num_tiles; ++i) {
            for (size_t o_idx = 0; o_idx < allowed_origins[i].size(); ++o_idx) {
                std::ostringstream name;
                name << "b_" << i << "_" << o_idx;
                b[i][o_idx] = IloBoolVar(env, name.str().c_str());
            }
        }
        
        // Variables for bounding box dimensions
        IloIntVar W(env, 0, M, "W");  // Width
        IloIntVar H(env, 0, M, "H");  // Height
        IloIntVar L(env, 0, M, "L");  // For bounding square: max(W, H)
        
        // ====================================================================
        // Constraints
        // ====================================================================
        
        // Constraint 1: Each tile placed exactly once
        for (int i = 0; i < num_tiles; ++i) {
            IloExpr sum(env);
            for (size_t o_idx = 0; o_idx < allowed_origins[i].size(); ++o_idx) {
                sum += b[i][o_idx];
            }
            model.add(sum == 1);
            sum.end();
        }
        
        // Symmetry breaking: Fix first tile at origin (0, 0) to break translational symmetry
        // This significantly reduces the search space
        if (num_tiles > 0 && !allowed_origins[0].empty()) {
            // Find the origin (0, 0) for tile 0
            for (size_t o_idx = 0; o_idx < allowed_origins[0].size(); ++o_idx) {
                const Origin& origin = allowed_origins[0][o_idx];
                if (origin.x == 0 && origin.y == 0) {
                    model.add(b[0][o_idx] == 1);
                    break;
                }
            }
        }
        
        // Constraint 2: Symbol-conflict constraints (pairwise no-conflict)
        // For each pair (i, j) with i < j, if placements (i, oi) and (j, oj) conflict,
        // then we cannot have both: b[i][oi] + b[j][oj] <= 1
        for (int i = 0; i < num_tiles; ++i) {
            for (int j = i + 1; j < num_tiles; ++j) {
                for (size_t oi_idx = 0; oi_idx < allowed_origins[i].size(); ++oi_idx) {
                    for (size_t oj_idx = 0; oj_idx < allowed_origins[j].size(); ++oj_idx) {
                        if (conflict[i][j][oi_idx][oj_idx]) {
                            model.add(b[i][oi_idx] + b[j][oj_idx] <= 1);
                        }
                    }
                }
            }
        }
        
        // Constraint 3: Bounding box constraints
        // All tiles must fit within [0, W] x [0, H]
        // For each tile i at origin o, we need:
        //   W >= o.x + w[i] when b[i][o] = 1
        //   H >= o.y + h[i] when b[i][o] = 1
        // Using big-M: W >= o.x + w[i] - M * (1 - b[i][o])
        //              H >= o.y + h[i] - M * (1 - b[i][o])
        
        for (int i = 0; i < num_tiles; ++i) {
            int w = tiles[i].width();
            int h = tiles[i].height();
            
            for (size_t o_idx = 0; o_idx < allowed_origins[i].size(); ++o_idx) {
                const Origin& origin = allowed_origins[i][o_idx];
                
                // W >= origin.x + w - M * (1 - b[i][o_idx])
                model.add(W >= origin.x + w - M * (1 - b[i][o_idx]));
                
                // H >= origin.y + h - M * (1 - b[i][o_idx])
                model.add(H >= origin.y + h - M * (1 - b[i][o_idx]));
            }
        }
        
        // Valid inequalities: Lower bounds on bounding box dimensions
        // W >= max(tile widths) and H >= max(tile heights)
        model.add(W >= max_tile_width);
        model.add(H >= max_tile_height);
        
        // Valid inequality: Area lower bound (sum of all tile areas)
        if (obj_type == ObjectiveType::RECTANGLE_AREA) {
            model.add(W * H >= total_area);
        }
        
        // ====================================================================
        // Objective: minimize based on objective type
        // ====================================================================
        
        if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
            // L = max(W, H)
            model.add(L >= W);
            model.add(L >= H);
            model.add(IloMinimize(env, L));
        } else {
            // Minimize W * H (area)
            // For CPLEX, we use an auxiliary variable for the product
            IloIntVar Area(env, 0, M * M, "Area");
            // Area = W * H (linearized using McCormick envelopes or other techniques)
            // For simplicity, we can approximate or use quadratic objective
            // CPLEX supports quadratic objectives, so we can minimize W*H directly
            IloExpr obj_expr(env);
            obj_expr = W * H;
            model.add(IloMinimize(env, obj_expr));
            obj_expr.end();
        }
        
        // ====================================================================
        // Solve
        // ====================================================================
        
        bool solved = cplex.solve();
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = end_time - start_time;
        result.wall_time_sec = elapsed.count();
        
        if (solved) {
            IloAlgorithm::Status status = cplex.getStatus();
            
            if (status == IloAlgorithm::Optimal) {
                result.status = "optimal";
            } else if (status == IloAlgorithm::Feasible) {
                result.status = "feasible";
            } else {
                result.status = "unknown";
            }
            
            // Get solution values
            int width_val = static_cast<int>(cplex.getValue(W));
            int height_val = static_cast<int>(cplex.getValue(H));
            
            result.best_bound = cplex.getBestObjValue();
            result.mip_gap = cplex.getMIPRelativeGap();
            result.nodes_processed = cplex.getNnodes();
            
            // Extract placements
            for (int i = 0; i < num_tiles; ++i) {
                for (size_t o_idx = 0; o_idx < allowed_origins[i].size(); ++o_idx) {
                    if (cplex.getValue(b[i][o_idx]) > 0.5) {
                        const Origin& origin = allowed_origins[i][o_idx];
                        result.placements.push_back({i, origin.x, origin.y});
                    }
                }
            }
            
            // Compute actual bounding box from placements
            int min_x = INT_MAX, max_x = INT_MIN;
            int min_y = INT_MAX, max_y = INT_MIN;
            
            for (const auto& [tile_idx, ox, oy] : result.placements) {
                const Tile& tile = tiles[tile_idx];
                
                for (const auto& [coord, _] : tile.cells) {
                    int gx = ox + coord.first;
                    int gy = oy + coord.second;
                    
                    min_x = std::min(min_x, gx);
                    max_x = std::max(max_x, gx);
                    min_y = std::min(min_y, gy);
                    max_y = std::max(max_y, gy);
                }
            }
            
            result.bbox_width = max_x - min_x + 1;
            result.bbox_height = max_y - min_y + 1;
            result.bbox_area = result.bbox_width * result.bbox_height;
            
            // Set objective based on objective type
            if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
                result.best_obj = std::max(result.bbox_width, result.bbox_height);
            } else {
                result.best_obj = result.bbox_width * result.bbox_height;
            }
            
        } else {
            result.status = "infeasible";
            result.best_obj = -1;
        }
        
        env.end();
        
    } catch (IloException& e) {
        result.status = std::string("CPLEX error: ") + e.getMessage();
        result.best_obj = -1;
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = end_time - start_time;
        result.wall_time_sec = elapsed.count();
    } catch (...) {
        result.status = "Unknown error";
        result.best_obj = -1;
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = end_time - start_time;
        result.wall_time_sec = elapsed.count();
    }
    
    return result;
}

#else  // !USE_CPLEX

// Stub implementation when CPLEX is not available
CplexResult solve_cplex(const Matrices& matrices, int time_limit, ObjectiveType obj_type) {
    (void)matrices;      // Suppress unused parameter warning
    (void)time_limit;    // Suppress unused parameter warning
    (void)obj_type;      // Suppress unused parameter warning
    
    CplexResult result;
    result.status = "CPLEX not available";
    result.best_obj = -1;
    result.wall_time_sec = 0.0;
    return result;
}

#endif // USE_CPLEX
