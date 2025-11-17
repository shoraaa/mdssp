#ifdef USE_CPLEX

#include "cplex.hpp"
#include <ilcplex/ilocplex.h>
#include <sstream>
#include <chrono>
#include <set>
#include <map>
#include <climits>

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
std::vector<Origin> compute_allowed_origins(const Tile& tile, int max_grid_bound) {
    std::vector<Origin> origins;
    
    if (tile.cells.empty()) return origins;
    
    int tile_min_x = tile.min_x();
    int tile_min_y = tile.min_y();
    int tile_max_x = tile.max_x();
    int tile_max_y = tile.max_y();
    
    // For each possible origin (ox, oy), check if all tile cells fit in grid [0, max_grid_bound]
    // Global cell (ox + u, oy + v) must be in [0, max_grid_bound] × [0, max_grid_bound]
    for (int ox = -tile_max_x; ox <= max_grid_bound - tile_min_x; ++ox) {
        for (int oy = -tile_max_y; oy <= max_grid_bound - tile_min_y; ++oy) {
            bool valid = true;
            for (const auto& [coord, _] : tile.cells) {
                int gx = ox + coord.first;
                int gy = oy + coord.second;
                if (gx < 0 || gx > max_grid_bound || gy < 0 || gy > max_grid_bound) {
                    valid = false;
                    break;
                }
            }
            if (valid) {
                origins.emplace_back(ox, oy);
            }
        }
    }
    
    return origins;
}

// Check if two tile placements have symbol conflicts
bool has_conflict(const Tile& tile_i, const Origin& origin_i,
                  const Tile& tile_j, const Origin& origin_j) {
    int xi = origin_i.x;
    int yi = origin_i.y;
    int xj = origin_j.x;
    int yj = origin_j.y;
    
    // Check if placements (i, origin_i) and (j, origin_j) would cause ANY symbol conflict
    for (const auto& [coord_i, symbol_i] : tile_i.cells) {
        int u = coord_i.first;
        int v = coord_i.second;
        int global_x_i = xi + u;
        int global_y_i = yi + v;
        
        for (const auto& [coord_j, symbol_j] : tile_j.cells) {
            int u2 = coord_j.first;
            int v2 = coord_j.second;
            int global_x_j = xj + u2;
            int global_y_j = yj + v2;
            
            // Same global position?
            if (global_x_i == global_x_j && global_y_i == global_y_j) {
                // Different symbols -> conflict
                if (symbol_i != symbol_j) {
                    return true;
                }
            }
        }
    }
    
    return false;
}

// ============================================================================
// CPLEX Solver Implementation
// ============================================================================

CplexResult solve_cplex(const Matrices& matrices, int time_limit) {
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
        for (const auto& tile : tiles) {
            max_tile_width = std::max(max_tile_width, tile.width());
            max_tile_height = std::max(max_tile_height, tile.height());
        }
        
        // Grid bound: large enough to allow all placements
        int grid_bound = num_tiles * std::max(max_tile_width, max_tile_height);
        
        // Big-M for bounding square constraints
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
        
        // Configure CPLEX
        cplex.setOut(env.getNullStream());
        cplex.setWarning(env.getNullStream());
        cplex.setParam(IloCplex::Param::TimeLimit, time_limit);
        cplex.setParam(IloCplex::Param::MIP::Tolerances::MIPGap, 0.01);
        
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
        
        // L: side length of bounding square
        IloIntVar L(env, 0, M, "L");
        
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
        
        // Constraint 3: Bounding square constraints
        // All tiles must fit within [0, L] x [0, L]
        // For each tile i at origin o, we need:
        //   L >= o.x + w[i] when b[i][o] = 1
        //   L >= o.y + h[i] when b[i][o] = 1
        // Using big-M: L >= o.x + w[i] - M * (1 - b[i][o])
        //              L >= o.y + h[i] - M * (1 - b[i][o])
        
        for (int i = 0; i < num_tiles; ++i) {
            int w = tiles[i].width();
            int h = tiles[i].height();
            
            for (size_t o_idx = 0; o_idx < allowed_origins[i].size(); ++o_idx) {
                const Origin& origin = allowed_origins[i][o_idx];
                
                // L >= origin.x + w - M * (1 - b[i][o_idx])
                model.add(L >= origin.x + w - M * (1 - b[i][o_idx]));
                
                // L >= origin.y + h - M * (1 - b[i][o_idx])
                model.add(L >= origin.y + h - M * (1 - b[i][o_idx]));
            }
        }
        
        // L >= 0 (already enforced by variable bounds)
        
        // ====================================================================
        // Objective: minimize L
        // ====================================================================
        
        model.add(IloMinimize(env, L));
        
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
            
            result.best_obj = static_cast<int>(cplex.getValue(L));
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
            
            // Override best_obj to be consistent with other algorithms: max(width, height)
            result.best_obj = std::max(result.bbox_width, result.bbox_height);
            
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

#endif // USE_CPLEX
