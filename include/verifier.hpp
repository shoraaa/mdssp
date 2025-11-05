#ifndef MDSSP_VERIFIER_HPP
#define MDSSP_VERIFIER_HPP

#include "common.hpp"
#include <tuple>
#include <set>
#include <string>

// ============================================================================
// Verification Result
// ============================================================================

struct VerificationResult {
    bool is_valid;
    std::string error_message;
    int num_tiles;
    int num_placed;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    int best_obj;
    std::set<int> missing_tiles;
    std::set<int> duplicate_tiles;
    int num_conflicts;
    
    VerificationResult();
};

// ============================================================================
// Solution Verifier
// ============================================================================

class SolutionVerifier {
public:
    std::vector<Tile> tiles;
    
    explicit SolutionVerifier(std::vector<Tile> tiles_);
    
    VerificationResult verify(const std::vector<std::tuple<int, int, int>>& placements);
    std::string render_solution(const std::vector<std::tuple<int, int, int>>& placements);
};

#endif // MDSSP_VERIFIER_HPP
