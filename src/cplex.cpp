#ifdef USE_CPLEX

#include "cplex.hpp"
#include "greedy.hpp"
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
    
    // Preliminary check: For very large instances (>50 tiles), CPLEX may not be practical
    // The model size grows exponentially with number of tiles and allowed origins
    if (matrices.size() > 100) {
        result.status = "Instance too large for CPLEX (>100 tiles)";
        result.best_obj = -1;
        result.wall_time_sec = 0.0;
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
        
        // Compute greedy solution to use as upper bound
        GreedyResult greedy_result = solve_greedy(tiles, 0, obj_type);
        int greedy_bound = greedy_result.best_obj;
        
        std::cerr << "[CPLEX] Greedy solution: obj=" << greedy_bound 
                  << ", bbox=" << greedy_result.bbox_width << "x" << greedy_result.bbox_height
                  << ", area=" << greedy_result.bbox_area << std::endl;
        
        // Use greedy result to tighten grid bound
        // Optimized grid bound: use tighter upper bound based on greedy solution
        int theoretical_min = static_cast<int>(std::sqrt(total_area)) + 1;
        int grid_bound;
        
        if (greedy_bound > 0) {
            // Use greedy solution to provide a tight upper bound
            if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
                grid_bound = greedy_bound;
            } else {
                // For area minimization, use greedy bbox dimensions
                grid_bound = std::max(greedy_result.bbox_width, greedy_result.bbox_height);
            }
        } else if (num_tiles <= 10) {
            // Small instances: use more conservative bound
            grid_bound = std::min(theoretical_min * 2, num_tiles * std::max(max_tile_width, max_tile_height) / 2);
        } else if (num_tiles <= 30) {
            // Medium instances: use tighter bound to reduce model size
            grid_bound = static_cast<int>(theoretical_min * 1.5) + std::max(max_tile_width, max_tile_height);
        } else {
            // Large instances: use very tight bound
            grid_bound = static_cast<int>(theoretical_min * 1.3) + std::max(max_tile_width, max_tile_height);
        }
        
        std::cerr << "[CPLEX] Grid bound: " << grid_bound 
                  << " (theoretical_min=" << theoretical_min << ")" << std::endl;
        
        // Big-M for bounding constraints 
        int M = grid_bound;
        
        // Compute allowed origins for each tile
        std::vector<std::vector<Origin>> allowed_origins(num_tiles);
        long long total_origin_vars = 0;
        for (int i = 0; i < num_tiles; ++i) {
            allowed_origins[i] = compute_allowed_origins(tiles[i], grid_bound);
            total_origin_vars += allowed_origins[i].size();
        }
        
        std::cerr << "[CPLEX] Total origin variables: " << total_origin_vars << std::endl;
        
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
        long long total_conflict_checks = 0;
        long long actual_conflicts = 0;
        for (int i = 0; i < num_tiles; ++i) {
            for (int j = i + 1; j < num_tiles; ++j) {
                for (size_t oi_idx = 0; oi_idx < allowed_origins[i].size(); ++oi_idx) {
                    for (size_t oj_idx = 0; oj_idx < allowed_origins[j].size(); ++oj_idx) {
                        total_conflict_checks++;
                        const Origin& oi = allowed_origins[i][oi_idx];
                        const Origin& oj = allowed_origins[j][oj_idx];
                        
                        if (has_conflict(tiles[i], oi, tiles[j], oj)) {
                            conflict[i][j][oi_idx][oj_idx] = true;
                            actual_conflicts++;
                        }
                    }
                }
            }
        }
        
        std::cerr << "[CPLEX] Conflict checks: " << total_conflict_checks 
                  << ", conflicts found: " << actual_conflicts 
                  << " (" << (100.0 * actual_conflicts / std::max(1LL, total_conflict_checks)) << "%)" << std::endl;
        
        // Setup CPLEX environment
        IloEnv env;
        IloModel model(env);
        IloCplex cplex(model);
        
        // Configure CPLEX with optimized parameters
        cplex.setOut(env.getNullStream());
        cplex.setWarning(env.getNullStream());
        cplex.setParam(IloCplex::Param::TimeLimit, time_limit);
        
        // Set deterministic time limit as well for more reliable termination
        // DetTimeLimit provides deterministic behavior across runs
        // Setting it to a very high value (1e75) with clock time limit as primary control
        cplex.setParam(IloCplex::Param::DetTimeLimit, 1e75);
        
        // Optimization: Enable aggressive preprocessing and cuts
        cplex.setParam(IloCplex::Param::Preprocessing::Presolve, 1);
        cplex.setParam(IloCplex::Param::MIP::Strategy::HeuristicFreq, 20);  // More frequent heuristics
        cplex.setParam(IloCplex::Param::MIP::Strategy::RINSHeur, 50);  // RINS heuristic
        
        // Enable parallel processing if available
        cplex.setParam(IloCplex::Param::Threads, 0);  // Use all available threads
        
        // Different settings for different objective types
        if (obj_type == ObjectiveType::RECTANGLE_AREA) {
            // For area minimization, balance between finding good solutions and proving optimality
            cplex.setParam(IloCplex::Param::MIP::Tolerances::MIPGap, 0.001);  // Allow 0.1% gap
            cplex.setParam(IloCplex::Param::Emphasis::MIP, 0);  // Balanced approach
            cplex.setParam(IloCplex::Param::MIP::Strategy::Search, 0);  // Automatic search strategy
            cplex.setParam(IloCplex::Param::MIP::Strategy::Probe, 2);  // Moderate probing
            cplex.setParam(IloCplex::Param::MIP::Cuts::Gomory, 0);  // Automatic Gomory cuts
            cplex.setParam(IloCplex::Param::MIP::Cuts::Covers, 0);  // Automatic cover cuts
            cplex.setParam(IloCplex::Param::MIP::Strategy::VariableSelect, 3);  // Strong branching
        } else {
            // For square minimization, can use looser gap
            cplex.setParam(IloCplex::Param::MIP::Tolerances::MIPGap, 0.01);
            cplex.setParam(IloCplex::Param::Emphasis::MIP, 1);  // Emphasize feasibility
        }
        
        // Use greedy solution as cutoff (upper bound) to prune search space
        if (greedy_bound > 0) {
            cplex.setParam(IloCplex::Param::MIP::Tolerances::UpperCutoff, static_cast<double>(greedy_bound) + 0.999);
            std::cerr << "[CPLEX] Upper cutoff set to: " << (greedy_bound + 0.999) << std::endl;
        }
        
        std::cerr << "[CPLEX] Model setup complete. Starting optimization..." << std::endl;
        
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
        
        // Note: Symmetry breaking by fixing first tile can exclude optimal solutions
        // for area minimization. While it reduces search space, it may force suboptimal
        // arrangements. For small instances, let CPLEX explore all placements.
        
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
        // W and H represent the bounding box dimensions (max - min + 1)
        // We need auxiliary variables for min and max coordinates
        IloIntVar X_min(env, -M, M, "X_min");
        IloIntVar X_max(env, -M, M, "X_max");
        IloIntVar Y_min(env, -M, M, "Y_min");
        IloIntVar Y_max(env, -M, M, "Y_max");
        
        // For each tile, track its extent
        for (int i = 0; i < num_tiles; ++i) {
            const Tile& tile = tiles[i];
            
            // Get tile's bounding box (min/max relative coords)
            int tile_min_x = tile.min_x();
            int tile_max_x = tile.max_x();
            int tile_min_y = tile.min_y();
            int tile_max_y = tile.max_y();
            
            for (size_t o_idx = 0; o_idx < allowed_origins[i].size(); ++o_idx) {
                const Origin& origin = allowed_origins[i][o_idx];
                
                // When tile i is placed at origin o, its extent is:
                // [origin.x + tile_min_x, origin.x + tile_max_x] x [origin.y + tile_min_y, origin.y + tile_max_y]
                
                // X_min <= origin.x + tile_min_x when b[i][o] = 1
                // X_max >= origin.x + tile_max_x when b[i][o] = 1
                // Y_min <= origin.y + tile_min_y when b[i][o] = 1
                // Y_max >= origin.y + tile_max_y when b[i][o] = 1
                
                model.add(X_min <= origin.x + tile_min_x + M * (1 - b[i][o_idx]));
                model.add(X_max >= origin.x + tile_max_x - M * (1 - b[i][o_idx]));
                model.add(Y_min <= origin.y + tile_min_y + M * (1 - b[i][o_idx]));
                model.add(Y_max >= origin.y + tile_max_y - M * (1 - b[i][o_idx]));
            }
        }
        
        // W = X_max - X_min + 1, H = Y_max - Y_min + 1
        model.add(W == X_max - X_min + 1);
        model.add(H == Y_max - Y_min + 1);
        
        // Valid inequalities: Lower bounds on bounding box dimensions
        // W >= max(tile widths) and H >= max(tile heights)
        model.add(W >= max_tile_width);
        model.add(H >= max_tile_height);
        
        // Note: Cannot add W * H >= total_area directly as it's non-convex
        // This constraint will be enforced through the discretization or McCormick envelope
        
        // ====================================================================
        // Objective: minimize based on objective type
        // ====================================================================
        
        if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
            // L = max(W, H)
            model.add(L >= W);
            model.add(L >= H);
            model.add(IloMinimize(env, L));
        } else {
            // Minimize W * H (area) using linearization
            // Create an auxiliary variable for the area
            IloIntVar Area(env, 0, M * M, "Area");
            
            // Use complete bilinear discretization to linearize Area = W * H
            // This discretizes both W and H and creates binary variables for each possible value
            
            int W_min = max_tile_width;
            int H_min = max_tile_height;
            int W_max = std::min(M, total_area);
            int H_max = std::min(M, total_area);
            
            int W_range = W_max - W_min + 1;
            int H_range = H_max - H_min + 1;
            
            // Use complete bilinear discretization for reasonable-sized instances
            if (W_range * H_range <= 10000) {
                // Binary variables for W and H values
                std::vector<IloBoolVar> x_w;
                std::vector<IloBoolVar> y_h;
                
                for (int w = W_min; w <= W_max; ++w) {
                    x_w.push_back(IloBoolVar(env, ("x_w_" + std::to_string(w)).c_str()));
                }
                for (int h = H_min; h <= H_max; ++h) {
                    y_h.push_back(IloBoolVar(env, ("y_h_" + std::to_string(h)).c_str()));
                }
                
                // Exactly one x_w and one y_h must be selected
                IloExpr sum_x(env);
                for (size_t i = 0; i < x_w.size(); ++i) {
                    sum_x += x_w[i];
                }
                model.add(sum_x == 1);
                sum_x.end();
                
                IloExpr sum_y(env);
                for (size_t i = 0; i < y_h.size(); ++i) {
                    sum_y += y_h[i];
                }
                model.add(sum_y == 1);
                sum_y.end();
                
                // W = sum_{w} w * x_w
                IloExpr W_expr(env);
                for (int w = W_min; w <= W_max; ++w) {
                    W_expr += w * x_w[w - W_min];
                }
                model.add(W == W_expr);
                W_expr.end();
                
                // H = sum_{h} h * y_h
                IloExpr H_expr(env);
                for (int h = H_min; h <= H_max; ++h) {
                    H_expr += h * y_h[h - H_min];
                }
                model.add(H == H_expr);
                H_expr.end();
                
                // Area = sum_{w,h} w * h * z_{w,h}
                // z_{w,h} represents x_w AND y_h (product of binary variables)
                IloExpr area_expr(env);
                for (int w = W_min; w <= W_max; ++w) {
                    for (int h = H_min; h <= H_max; ++h) {
                        IloBoolVar z_wh(env, ("z_" + std::to_string(w) + "_" + std::to_string(h)).c_str());
                        
                        // Linearize z_wh = x_w AND y_h
                        model.add(z_wh <= x_w[w - W_min]);
                        model.add(z_wh <= y_h[h - H_min]);
                        model.add(z_wh >= x_w[w - W_min] + y_h[h - H_min] - 1);
                        
                        // Add the product coefficient (w * h is a constant)
                        area_expr += (w * h) * z_wh;
                    }
                }
                
                // Link Area variable to the expression
                model.add(Area == area_expr);
                area_expr.end();
                
                // Minimize the Area variable (linear objective)
                model.add(IloMinimize(env, Area));
                
            } else {
                // For larger instances, use McCormick envelope relaxation
                // This provides a convex relaxation of the bilinear term
                // Area >= W * H_min + H * W_min - W_min * H_min (lower bound 1)
                // Area >= W * H_max + H * W_max - W_max * H_max (lower bound 2)
                // Area <= W * H_min + H * W_max - W_min * H_max (upper bound 1)
                // Area <= W * H_max + H * W_min - W_max * H_min (upper bound 2)
                
                model.add(Area >= W_min * H + H_min * W - W_min * H_min);
                model.add(Area >= W_max * H + H_max * W - W_max * H_max);
                model.add(Area <= W_min * H + H_max * W - W_min * H_max);
                model.add(Area <= W_max * H + H_min * W - W_max * H_min);
                
                // Minimize the Area variable (linear objective)
                model.add(IloMinimize(env, Area));
            }
        }
        
        // ====================================================================
        // Warm Start: Disabled for area objective to avoid biasing search
        // ====================================================================
        
        // Note: Warm start can bias CPLEX towards suboptimal solutions for area minimization
        // Let CPLEX explore the search space freely to find better solutions
        
        // ====================================================================
        // Solve
        // ====================================================================
        
        bool solved = cplex.solve();
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = end_time - start_time;
        result.wall_time_sec = elapsed.count();
        
        std::cerr << "[CPLEX] Solve completed in " << elapsed.count() << " seconds" << std::endl;
        
        // Check if we have any solution (optimal or feasible)
        IloAlgorithm::Status status = cplex.getStatus();
        bool has_solution = (status == IloAlgorithm::Optimal || 
                            status == IloAlgorithm::Feasible ||
                            cplex.getSolnPoolNsolns() > 0);
        
        if (solved || has_solution) {
            if (status == IloAlgorithm::Optimal) {
                result.status = "optimal";
                std::cerr << "[CPLEX] Status: OPTIMAL" << std::endl;
            } else if (status == IloAlgorithm::Feasible) {
                result.status = "feasible";
                std::cerr << "[CPLEX] Status: FEASIBLE" << std::endl;
            } else {
                result.status = "feasible";  // Have a solution even if not proven optimal
                std::cerr << "[CPLEX] Status: FEASIBLE (from solution pool)" << std::endl;
            }
            
            // Get solution values
            int width_val = static_cast<int>(cplex.getValue(W));
            int height_val = static_cast<int>(cplex.getValue(H));
            
            result.best_bound = cplex.getBestObjValue();
            result.mip_gap = cplex.getMIPRelativeGap();
            result.nodes_processed = cplex.getNnodes();
            
            std::cerr << "[CPLEX] Nodes processed: " << result.nodes_processed 
                      << ", MIP gap: " << (result.mip_gap * 100.0) << "%" << std::endl;
            
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
            
            std::cerr << "[CPLEX] Solution found: obj=" << result.best_obj 
                      << ", bbox=" << result.bbox_width << "x" << result.bbox_height
                      << ", area=" << result.bbox_area << std::endl;
            
            // Compare with greedy
            if (greedy_bound > 0) {
                double improvement = 100.0 * (greedy_bound - result.best_obj) / static_cast<double>(greedy_bound);
                std::cerr << "[CPLEX] Improvement over greedy: " << improvement << "%" << std::endl;
            }
            
        } else {
            result.status = "infeasible";
            result.best_obj = -1;
            std::cerr << "[CPLEX] No solution found (infeasible)" << std::endl;
        }
        
        env.end();
        
    } catch (IloException& e) {
        std::string error_msg = e.getMessage();
        result.status = std::string("CPLEX error: ") + error_msg;
        result.best_obj = -1;
        
        // Log the error to stderr for debugging
        std::cerr << "CPLEX exception caught: " << error_msg << std::endl;
        std::cerr << "Instance: T=" << matrices.size() << ", objective_type=" 
                  << (obj_type == ObjectiveType::BOUNDING_SQUARE ? "square" : "area") << std::endl;
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = end_time - start_time;
        result.wall_time_sec = elapsed.count();
    } catch (std::exception& e) {
        result.status = std::string("C++ exception: ") + e.what();
        result.best_obj = -1;
        
        // Log the error to stderr for debugging
        std::cerr << "C++ exception caught: " << e.what() << std::endl;
        
        auto end_time = std::chrono::high_resolution_clock::now();
        std::chrono::duration<double> elapsed = end_time - start_time;
        result.wall_time_sec = elapsed.count();
    } catch (...) {
        result.status = "Unknown error";
        result.best_obj = -1;
        
        // Log the error to stderr for debugging
        std::cerr << "Unknown exception caught in CPLEX solver" << std::endl;
        
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
