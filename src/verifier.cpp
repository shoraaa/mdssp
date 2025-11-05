#include "verifier.hpp"
#include <sstream>

// ============================================================================
// VerificationResult Implementation
// ============================================================================

VerificationResult::VerificationResult() 
    : is_valid(true), num_tiles(0), num_placed(0), 
      bbox_width(0), bbox_height(0), bbox_area(0), best_obj(0),
      num_conflicts(0) {}

// ============================================================================
// SolutionVerifier Implementation
// ============================================================================

SolutionVerifier::SolutionVerifier(std::vector<Tile> tiles_) : tiles(std::move(tiles_)) {}

VerificationResult SolutionVerifier::verify(const std::vector<std::tuple<int, int, int>>& placements) {
    VerificationResult result;
    result.num_tiles = tiles.size();
    result.num_placed = placements.size();
    
    // Check 1: Verify all tiles are placed exactly once
    std::set<int> placed_indices;
    for (const auto& [tile_idx, x, y] : placements) {
        if (tile_idx < 0 || tile_idx >= (int)tiles.size()) {
            result.is_valid = false;
            result.error_message = "Invalid tile index: " + std::to_string(tile_idx);
            return result;
        }
        
        if (placed_indices.count(tile_idx)) {
            result.duplicate_tiles.insert(tile_idx);
        }
        placed_indices.insert(tile_idx);
    }
    
    // Find missing tiles
    for (int i = 0; i < (int)tiles.size(); ++i) {
        if (!placed_indices.count(i)) {
            result.missing_tiles.insert(i);
        }
    }
    
    if (!result.missing_tiles.empty()) {
        result.is_valid = false;
        result.error_message = "Missing tiles: ";
        for (int idx : result.missing_tiles) {
            result.error_message += std::to_string(idx) + " ";
        }
        return result;
    }
    
    if (!result.duplicate_tiles.empty()) {
        result.is_valid = false;
        result.error_message = "Duplicate tiles: ";
        for (int idx : result.duplicate_tiles) {
            result.error_message += std::to_string(idx) + " ";
        }
        return result;
    }
    
    // Check 2: Build the canvas and check for conflicts
    CellMap canvas;
    int xmin = std::numeric_limits<int>::max();
    int xmax = std::numeric_limits<int>::min();
    int ymin = std::numeric_limits<int>::max();
    int ymax = std::numeric_limits<int>::min();
    
    for (const auto& [tile_idx, x, y] : placements) {
        CellMap placement = tiles[tile_idx].translate(x, y);
        
        // Check for conflicts
        for (const auto& [coord, label] : placement) {
            auto it = canvas.find(coord);
            if (it != canvas.end()) {
                // Cell already occupied
                if (it->second != label) {
                    // Conflict: different values at same position
                    result.num_conflicts++;
                    result.is_valid = false;
                    std::ostringstream oss;
                    oss << "Conflict at position (" << coord.first << "," << coord.second 
                        << "): tile " << tile_idx << " has value '" << label 
                        << "' but canvas has '" << it->second << "'";
                    result.error_message = oss.str();
                    return result;
                }
                // Same value - allowed overlap
            } else {
                canvas[coord] = label;
            }
            
            // Update bounding box
            xmin = std::min(xmin, coord.first);
            xmax = std::max(xmax, coord.first);
            ymin = std::min(ymin, coord.second);
            ymax = std::max(ymax, coord.second);
        }
    }
    
    // Check 3: Compute bounding box dimensions
    if (canvas.empty()) {
        result.bbox_width = 0;
        result.bbox_height = 0;
        result.bbox_area = 0;
        result.best_obj = 0;
    } else {
        result.bbox_width = xmax - xmin + 1;
        result.bbox_height = ymax - ymin + 1;
        result.bbox_area = result.bbox_width * result.bbox_height;
        result.best_obj = std::max(result.bbox_width, result.bbox_height);
    }
    
    result.is_valid = true;
    result.error_message = "Valid solution";
    return result;
}

std::string SolutionVerifier::render_solution(const std::vector<std::tuple<int, int, int>>& placements) {
    CellMap canvas;
    int xmin = std::numeric_limits<int>::max();
    int xmax = std::numeric_limits<int>::min();
    int ymin = std::numeric_limits<int>::max();
    int ymax = std::numeric_limits<int>::min();
    
    for (const auto& [tile_idx, x, y] : placements) {
        CellMap placement = tiles[tile_idx].translate(x, y);
        for (const auto& [coord, label] : placement) {
            canvas[coord] = label;
            xmin = std::min(xmin, coord.first);
            xmax = std::max(xmax, coord.first);
            ymin = std::min(ymin, coord.second);
            ymax = std::max(ymax, coord.second);
        }
    }
    
    if (canvas.empty()) return "<empty canvas>";
    
    std::ostringstream oss;
    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            if (x > xmin) oss << ' ';
            auto it = canvas.find({x, y});
            oss << (it != canvas.end() ? it->second : '.');
        }
        if (y < ymax) oss << '\n';
    }
    return oss.str();
}
