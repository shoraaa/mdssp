#ifndef MDSSP_CPLEX_HPP
#define MDSSP_CPLEX_HPP

#include "common.hpp"
#include <string>
#include <tuple>

// ============================================================================
// CPLEX Result
// ============================================================================

struct CplexResult {
    std::string status;
    int best_obj;
    double best_bound;
    double mip_gap;
    long nodes_processed;
    double wall_time_sec;
    std::vector<std::tuple<int, int, int>> placements;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    
    CplexResult() 
        : status("unknown"), best_obj(-1), best_bound(-1), mip_gap(-1),
          nodes_processed(0), wall_time_sec(0.0),
          bbox_width(0), bbox_height(0), bbox_area(0) {}
};

// ============================================================================
// CPLEX Solver Function
// ============================================================================

#ifdef USE_CPLEX
CplexResult solve_cplex(const Matrices& matrices, int time_limit = 60);
#else
// Dummy implementation when CPLEX is not available
inline CplexResult solve_cplex(const Matrices& matrices, int time_limit = 60) {
    CplexResult result;
    result.status = "CPLEX not available";
    result.wall_time_sec = 0.0;
    return result;
}
#endif

#endif // MDSSP_CPLEX_HPP
