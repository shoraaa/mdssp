#ifdef USE_CPLEX

#include "cplex.hpp"
#include <ilcplex/ilocplex.h>
#include <sstream>
#include <chrono>
#include <vector>
#include <set>
#include <map>
#include <climits>
#include <algorithm>

ILOSTLBEGIN

// ============================================================================
// Helper: Check if two tile placements conflict  
// ============================================================================

static bool placements_conflict(
    const std::vector<std::vector<int>>& A, int xa, int ya,
    const std::vector<std::vector<int>>& B, int xb, int yb) {
    
    int ha = A.size();
    int wa = A[0].size();
    int hb = B.size();
    int wb = B[0].size();
    
    // Check bounding box overlap
    int x0 = std::max(xa, xb);
    int x1 = std::min(xa + wa, xb + wb);
    int y0 = std::max(ya, yb);
    int y1 = std::min(ya + ha, yb + hb);
    
    if (x0 >= x1 || y0 >= y1) return false;
    
    // Check cell-level conflict
    for (int y = y0; y < y1; ++y) {
        for (int x = x0; x < x1; ++x) {
            if (A[y - ya][x - xa] != B[y - yb][x - xb]) {
                return true;
            }
        }
    }
    return false;
}

// ============================================================================
// Tree-based CPLEX formulation
// ============================================================================

struct Edge {
    int u, v;  // parent -> child
    int dx, dy;  // offset of v relative to u
};

CplexResult solve_cplex(const Matrices& tiles, int time_limit) {
    CplexResult result;
    
    if (tiles.empty()) {
        result.status = "No tiles provided";
        return result;
    }
    
    auto start_time = std::chrono::high_resolution_clock::now();
    
    try {
        int T = tiles.size();
        int n = tiles[0].size();  // tile height
        int m = tiles[0][0].size();  // tile width
        
        int root = 0;  // Choose tile 0 as root
        
        // Big-M for offset constraints
        int M = T * std::max(n, m) * 4;
        
        IloEnv env;
        IloModel model(env);
        IloCplex cplex(model);
        
        // Configure CPLEX
        cplex.setOut(env.getNullStream());
        cplex.setWarning(env.getNullStream());
        cplex.setParam(IloCplex::Param::TimeLimit, time_limit);
        cplex.setParam(IloCplex::Param::MIP::Tolerances::MIPGap, 0.01);
        
        // ====================================================================
        // 1. Build edge set E: all possible parent-child pairs with offsets
        // ====================================================================
        std::vector<Edge> edges;
        std::map<std::pair<int,int>, std::vector<int>> edgeMap;  // (u,v) -> list of edge indices
        
        int range = std::max(n, m) * 2;  // Search range for neighbors
        
        for (int u = 0; u < T; ++u) {
            for (int v = 0; v < T; ++v) {
                if (u == v) continue;
                
                // Try different offset positions
                for (int dx = -range; dx <= range; ++dx) {
                    for (int dy = -range; dy <= range; ++dy) {
                        // Check if tiles would be adjacent/overlapping at this offset
                        if (!placements_conflict(tiles[u], 0, 0, tiles[v], dx, dy)) {
                            // Check if they're actually adjacent (sharing boundary)
                            bool adjacent = false;
                            
                            // Check if cells are within 1 unit distance
                            for (int yu = 0; yu < n && !adjacent; ++yu) {
                                for (int xu = 0; xu < m && !adjacent; ++xu) {
                                    if (tiles[u][yu][xu] != 1) continue;
                                    for (int yv = 0; yv < n && !adjacent; ++yv) {
                                        for (int xv = 0; xv < m && !adjacent; ++xv) {
                                            if (tiles[v][yv][xv] != 1) continue;
                                            int dist = std::abs(xu - (xv + dx)) + std::abs(yu - (yv + dy));
                                            if (dist <= 1) {
                                                adjacent = true;
                                            }
                                        }
                                    }
                                }
                            }
                            
                            if (adjacent) {
                                int edgeIdx = edges.size();
                                edges.push_back({u, v, dx, dy});
                                edgeMap[{u, v}].push_back(edgeIdx);
                            }
                        }
                    }
                }
            }
        }
        
        int E = edges.size();
        
        // ====================================================================
        // 2. Build conflict sets: sets of edges that lead to symbol conflicts
        // ====================================================================
        std::vector<std::vector<int>> conflictSets;
        
        for (int i = 0; i < T; ++i) {
            for (int j = i + 1; j < T; ++j) {
                std::vector<int> conflictingEdges;
                
                // Check all edge combinations that would place i and j in conflict
                for (int ei = 0; ei < E; ++ei) {
                    if (edges[ei].v != i) continue;  // Edge doesn't place tile i
                    
                    for (int ej = 0; ej < E; ++ej) {
                        if (edges[ej].v != j) continue;  // Edge doesn't place tile j
                        
                        // If both edges share the same parent, check if children conflict
                        if (edges[ei].u == edges[ej].u) {
                            int u = edges[ei].u;
                            // i is at offset (edges[ei].dx, edges[ei].dy) from u
                            // j is at offset (edges[ej].dx, edges[ej].dy) from u
                            // Relative position: j is at (edges[ej].dx - edges[ei].dx, edges[ej].dy - edges[ei].dy) from i
                            int rel_dx = edges[ej].dx - edges[ei].dx;
                            int rel_dy = edges[ej].dy - edges[ei].dy;
                            
                            if (placements_conflict(tiles[i], 0, 0, tiles[j], rel_dx, rel_dy)) {
                                // This pair of edges creates a conflict
                                if (std::find(conflictingEdges.begin(), conflictingEdges.end(), ei) == conflictingEdges.end()) {
                                    conflictingEdges.push_back(ei);
                                }
                                if (std::find(conflictingEdges.begin(), conflictingEdges.end(), ej) == conflictingEdges.end()) {
                                    conflictingEdges.push_back(ej);
                                }
                            }
                        }
                    }
                }
                
                if (!conflictingEdges.empty()) {
                    conflictSets.push_back(conflictingEdges);
                }
            }
        }
        
        // ====================================================================
        // 3. Decision variables
        // ====================================================================
        
        // x[e]: whether edge e is chosen
        IloBoolVarArray x(env, E);
        for (int e = 0; e < E; ++e) {
            std::ostringstream name;
            name << "x_" << e;
            x[e] = IloBoolVar(env, name.str().c_str());
        }
        
        // X[i], Y[i]: position of tile i
        IloIntVarArray X(env, T, -M, M);
        IloIntVarArray Y(env, T, -M, M);
        for (int i = 0; i < T; ++i) {
            std::ostringstream nameX, nameY;
            nameX << "X_" << i;
            nameY << "Y_" << i;
            X[i] = IloIntVar(env, -M, M, nameX.str().c_str());
            Y[i] = IloIntVar(env, -M, M, nameY.str().c_str());
        }
        
        // u[i]: MTZ ordering variable
        IloIntVarArray u(env, T, 0, T);
        for (int i = 0; i < T; ++i) {
            std::ostringstream name;
            name << "u_" << i;
            u[i] = IloIntVar(env, 0, T, name.str().c_str());
        }
        
        // Bounding box variables
        IloIntVar Xmin(env, -M, M, "Xmin");
        IloIntVar Xmax(env, -M, M, "Xmax");
        IloIntVar Ymin(env, -M, M, "Ymin");
        IloIntVar Ymax(env, -M, M, "Ymax");
        IloIntVar L(env, 0, M, "L");
        
        // ====================================================================
        // 4. Constraints
        // ====================================================================
        
        // Tree size: exactly T-1 edges
        IloExpr sumEdges(env);
        for (int e = 0; e < E; ++e) {
            sumEdges += x[e];
        }
        model.add(sumEdges == T - 1);
        sumEdges.end();
        
        // Parent constraints: each non-root tile has exactly one parent
        for (int i = 0; i < T; ++i) {
            IloExpr sumParents(env);
            for (int e = 0; e < E; ++e) {
                if (edges[e].v == i) {
                    sumParents += x[e];
                }
            }
            if (i == root) {
                model.add(sumParents == 0);
            } else {
                model.add(sumParents == 1);
            }
            sumParents.end();
        }
        
        // MTZ ordering to prevent cycles
        model.add(u[root] == 0);
        for (int e = 0; e < E; ++e) {
            int uNode = edges[e].u;
            int vNode = edges[e].v;
            model.add(u[vNode] >= u[uNode] + 1 - T * (1 - x[e]));
        }
        
        // Offset consistency (big-M)
        for (int e = 0; e < E; ++e) {
            int uNode = edges[e].u;
            int vNode = edges[e].v;
            int dx = edges[e].dx;
            int dy = edges[e].dy;
            
            model.add(X[vNode] - X[uNode] - dx <= M * (1 - x[e]));
            model.add(X[vNode] - X[uNode] - dx >= -M * (1 - x[e]));
            model.add(Y[vNode] - Y[uNode] - dy <= M * (1 - x[e]));
            model.add(Y[vNode] - Y[uNode] - dy >= -M * (1 - x[e]));
        }
        
        // Fix root position to remove translation symmetry
        model.add(X[root] == 0);
        model.add(Y[root] == 0);
        
        // Symbol-conflict constraints
        for (const auto& conflictSet : conflictSets) {
            IloExpr sumConflict(env);
            for (int e : conflictSet) {
                sumConflict += x[e];
            }
            model.add(sumConflict <= static_cast<int>(conflictSet.size() - 1));
            sumConflict.end();
        }
        
        // Bounding box constraints
        for (int i = 0; i < T; ++i) {
            // Find actual width and height of tile i
            int wi = 0, hi = 0;
            for (int y = 0; y < n; ++y) {
                for (int x = 0; x < m; ++x) {
                    if (tiles[i][y][x] == 1) {
                        wi = std::max(wi, x + 1);
                        hi = std::max(hi, y + 1);
                    }
                }
            }
            
            model.add(Xmin <= X[i]);
            model.add(Xmax >= X[i] + wi);
            model.add(Ymin <= Y[i]);
            model.add(Ymax >= Y[i] + hi);
        }
        
        // L >= max(width, height)
        model.add(L >= Xmax - Xmin);
        model.add(L >= Ymax - Ymin);
        
        // Objective: minimize L
        model.add(IloMinimize(env, L));
        
        // ====================================================================
        // 5. Solve
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
            
            result.best_obj = static_cast<int>(cplex.getObjValue() + 0.5);
            result.best_bound = cplex.getBestObjValue();
            result.mip_gap = cplex.getMIPRelativeGap();
            result.nodes_processed = cplex.getNnodes();
            
            // Extract solution
            for (int i = 0; i < T; ++i) {
                int xi = static_cast<int>(cplex.getValue(X[i]) + 0.5);
                int yi = static_cast<int>(cplex.getValue(Y[i]) + 0.5);
                result.placements.push_back({i, xi, yi});
            }
            
            // Compute actual bounding box
            int min_x = INT_MAX, max_x = INT_MIN;
            int min_y = INT_MAX, max_y = INT_MIN;
            
            for (int i = 0; i < T; ++i) {
                int xi = static_cast<int>(cplex.getValue(X[i]) + 0.5);
                int yi = static_cast<int>(cplex.getValue(Y[i]) + 0.5);
                
                for (int y = 0; y < n; ++y) {
                    for (int x = 0; x < m; ++x) {
                        if (tiles[i][y][x] == 1) {
                            min_x = std::min(min_x, xi + x);
                            max_x = std::max(max_x, xi + x);
                            min_y = std::min(min_y, yi + y);
                            max_y = std::max(max_y, yi + y);
                        }
                    }
                }
            }
            
            result.bbox_width = max_x - min_x + 1;
            result.bbox_height = max_y - min_y + 1;
            result.bbox_area = result.bbox_width * result.bbox_height;
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
