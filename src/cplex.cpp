#ifdef USE_CPLEX

#include "cplex.hpp"
#include <ilcplex/ilocplex.h>
#include <sstream>
#include <chrono>
#include <set>

ILOSTLBEGIN

// ============================================================================
// Helper Functions
// ============================================================================

static bool placements_conflict(
    const std::vector<std::vector<int>>& A, int u, int v,
    const std::vector<std::vector<int>>& B, int p, int q) {
    
    int h1 = A.size();     // height of A
    int w1 = A[0].size();  // width of A
    int h2 = B.size();     // height of B
    int w2 = B[0].size();  // width of B
    
    // Quick bounding box check
    int x0 = std::max(u, p);
    int x1 = std::min(u + w1, p + w2);
    int y0 = std::max(v, q);
    int y1 = std::min(v + h1, q + h2);
    
    // No overlap
    if (x0 >= x1 || y0 >= y1) {
        return false;
    }
    
    // Check for conflicts in overlapping region
    // Matrices use [row][col] = [y][x] indexing
    for (int y = y0; y < y1; ++y) {
        for (int x = x0; x < x1; ++x) {
            if (A[y - v][x - u] != B[y - q][x - p]) {
                return true;
            }
        }
    }
    
    return false;
}

struct PlacementVar {
    int tile_idx;
    int x;
    int y;
    IloBoolVar var;
    
    PlacementVar(int i, int u, int v, IloBoolVar var_) 
        : tile_idx(i), x(u), y(v), var(var_) {}
};

// ============================================================================
// CPLEX Solver Implementation
// ============================================================================

CplexResult solve_cplex(const Matrices& tiles, int time_limit) {
    CplexResult result;
    
    if (tiles.empty()) {
        result.status = "No tiles provided";
        return result;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    try {
        int T = tiles.size();
        int n = tiles[0].size();
        int m = tiles[0][0].size();
        
        // Upper bound for grid size
        int U = T * std::max(n, m);
        
        IloEnv env;
        IloModel model(env);
        IloCplex cplex(model);
        
        // Configure CPLEX
        cplex.setOut(env.getNullStream());
        cplex.setWarning(env.getNullStream());
        cplex.setParam(IloCplex::Param::TimeLimit, time_limit);
        cplex.setParam(IloCplex::Param::MIP::Tolerances::MIPGap, 0.01);
        
        // Decision variables: z[i,u,v] for each tile and position
        std::vector<PlacementVar> Z;
        Z.reserve(T * (U - m + 1) * (U - n + 1));
        
        for (int i = 0; i < T; ++i) {
            for (int u = 0; u <= U - m; ++u) {
                for (int v = 0; v <= U - n; ++v) {
                    std::ostringstream name;
                    name << "z_" << i << "_" << u << "_" << v;
                    IloBoolVar var(env, name.str().c_str());
                    Z.emplace_back(i, u, v, var);
                    model.add(var);
                }
            }
        }
        
        // Variable L: side length of bounding square
        IloIntVar L(env, 0, U, "L");
        model.add(L);
        
        // Constraint 1: Each tile placed exactly once
        for (int i = 0; i < T; ++i) {
            IloExpr sum(env);
            for (const auto& pv : Z) {
                if (pv.tile_idx == i) {
                    sum += pv.var;
                }
            }
            model.add(sum == 1);
            sum.end();
        }
        
        // Constraint 2: Link placements to L (bounding box)
        for (const auto& pv : Z) {
            model.add(L >= (pv.x + m) * pv.var);
            model.add(L >= (pv.y + n) * pv.var);
        }
        
        // Constraint 3: Conflict constraints
        for (int i = 0; i < T; ++i) {
            const auto& A = tiles[i];
            
            for (int j = i + 1; j < T; ++j) {
                const auto& B = tiles[j];
                
                for (int u = 0; u <= U - m; ++u) {
                    for (int p = 0; p <= U - m; ++p) {
                        // Quick x-overlap screening
                        if (u + m <= p || p + m <= u) continue;
                        
                        for (int v = 0; v <= U - n; ++v) {
                            for (int q = 0; q <= U - n; ++q) {
                                // Quick y-overlap screening
                                if (v + n <= q || q + n <= v) continue;
                                
                                if (placements_conflict(A, u, v, B, p, q)) {
                                    // Find corresponding variables
                                    IloBoolVar* var_i = nullptr;
                                    IloBoolVar* var_j = nullptr;
                                    
                                    for (const auto& pv : Z) {
                                        if (pv.tile_idx == i && pv.x == u && pv.y == v) {
                                            var_i = const_cast<IloBoolVar*>(&pv.var);
                                        }
                                        if (pv.tile_idx == j && pv.x == p && pv.y == q) {
                                            var_j = const_cast<IloBoolVar*>(&pv.var);
                                        }
                                    }
                                    
                                    if (var_i && var_j) {
                                        model.add(*var_i + *var_j <= 1);
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        // Objective: minimize L
        model.add(IloMinimize(env, L));
        
        // Solve
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
            
            result.best_obj = static_cast<int>(cplex.getObjValue());
            result.best_bound = cplex.getBestObjValue();
            result.mip_gap = cplex.getMIPRelativeGap();
            result.nodes_processed = cplex.getNnodes();
            
            // Extract solution
            result.bbox_width = result.best_obj;
            result.bbox_height = result.best_obj;
            result.bbox_area = result.best_obj * result.best_obj;
            
            for (const auto& pv : Z) {
                if (cplex.getValue(pv.var) > 0.5) {
                    result.placements.push_back({pv.tile_idx, pv.x, pv.y});
                }
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

#endif // USE_CPLEX
