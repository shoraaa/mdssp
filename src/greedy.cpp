#include "greedy.hpp"
#include <chrono>
#include <unordered_set>
#include <sstream>
#include <cassert>
#include <iostream>

// ============================================================================
// Canvas Implementation
// ============================================================================

Canvas::Canvas() : xmin(0), xmax(-1), ymin(0), ymax(-1) {}

bool Canvas::is_empty() const {
    return xmax < xmin || ymax < ymin;
}

int Canvas::bbox_area() const {
    if (is_empty()) return 0;
    return (xmax - xmin + 1) * (ymax - ymin + 1);
}

void Canvas::add_placement(const CellMap& placement) {
    for (const auto& [coord, ch] : placement) {
        cells[coord] = ch;
    }
    
    if (is_empty()) {
        xmin = xmax = cells.begin()->first.first;
        ymin = ymax = cells.begin()->first.second;
    }
    
    // Update bounding box
    for (const auto& [coord, _] : placement) {
        xmin = std::min(xmin, coord.first);
        xmax = std::max(xmax, coord.first);
        ymin = std::min(ymin, coord.second);
        ymax = std::max(ymax, coord.second);
    }
}

std::pair<bool, int> Canvas::overlap_check(const CellMap& placement) const {
    int overlap = 0;
    for (const auto& [coord, ch] : placement) {
        auto it = cells.find(coord);
        if (it != cells.end()) {
            if (it->second != ch) {
                return {false, 0};
            }
            overlap++;
        }
    }
    return {true, overlap};
}

std::string Canvas::render_ascii(int pad) const {
    if (is_empty()) return "<empty canvas>";
    
    std::ostringstream oss;
    for (int y = ymin; y <= ymax; ++y) {
        for (int x = xmin; x <= xmax; ++x) {
            if (x > xmin) {
                for (int p = 0; p < pad; ++p) oss << ' ';
            }
            auto it = cells.find({x, y});
            oss << (it != cells.end() ? it->second : '.');
        }
        if (y < ymax) oss << '\n';
    }
    return oss.str();
}

// ============================================================================
// Helper Functions
// ============================================================================

// Compute the new bounding box size after placing a tile
// Returns max(width, height) of the new bounding box
static int compute_new_bbox_size(const Tile& tile, int dx, int dy, const Canvas& canvas) {
    if (canvas.is_empty()) {
        return std::max(tile.width(), tile.height());
    }
    
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    
    int nxmin = std::min(canvas.xmin, tminx + dx);
    int nxmax = std::max(canvas.xmax, tmaxx + dx);
    int nymin = std::min(canvas.ymin, tminy + dy);
    int nymax = std::max(canvas.ymax, tmaxy + dy);
    
    int new_width = nxmax - nxmin + 1;
    int new_height = nymax - nymin + 1;
    
    return std::max(new_width, new_height);
}

static void enumerate_positions_inside_box(const Tile& tile, const Canvas& canvas, int target_size, std::vector<Coord>& positions, int box_xmin, int box_xmax, int box_ymin, int box_ymax) {
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    // The tile must fit within this square box to keep the bounding box size unchanged
    for (int dx = box_xmin - tminx; dx <= box_xmax - tmaxx; ++dx) {
        for (int dy = box_ymin - tminy; dy <= box_ymax - tmaxy; ++dy) {
            positions.push_back({dx, dy});
        }
    }
}

static void enumerate_positions_top(const Tile& tile, const Canvas& canvas, int target_size, std::vector<Coord>& positions, int box_xmin, int box_xmax, int box_ymin, int box_ymax, int delta) {
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    // The tile must fit within this square box to keep the bounding box size unchanged
    for (int dx = box_xmin - tminx - delta; dx <= box_xmax - tmaxx + delta; ++dx) {
        int dy = box_ymin - tminy - delta; // Align to top
        positions.push_back({dx, dy});
    }
}

static void enumerate_positions_bottom(const Tile& tile, const Canvas& canvas, int target_size, std::vector<Coord>& positions, int box_xmin, int box_xmax, int box_ymin, int box_ymax, int delta) {
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    // The tile must fit within this square box to keep the bounding box size unchanged
    for (int dx = box_xmin - tminx - delta; dx <= box_xmax - tmaxx + delta; ++dx) {
        int dy = box_ymax - tmaxy + delta; // Align to bottom
        positions.push_back({dx, dy});
    }
}

static void enumerate_positions_left(const Tile& tile, const Canvas& canvas, int target_size, std::vector<Coord>& positions, int box_xmin, int box_xmax, int box_ymin, int box_ymax, int delta) {
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    for (int dy = box_ymin - tminy - delta; dy <= box_ymax - tmaxy + delta; ++dy) {
        int dx = box_xmin - tminx - delta; // Align to left
        positions.push_back({dx, dy});
    }
}

static void enumerate_positions_right(const Tile& tile, const Canvas& canvas, int target_size, std::vector<Coord>& positions, int box_xmin, int box_xmax, int box_ymin, int box_ymax, int delta) {
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    for (int dy = box_ymin - tminy - delta; dy <= box_ymax - tmaxy + delta; ++dy) {
        int dx = box_xmax - tmaxx + delta; // Align to right
        positions.push_back({dx, dy});
    }
}

// Generate all candidate positions for a tile that would result in exactly target_size
static std::vector<Coord> enumerate_positions_for_size(const Tile& tile, const Canvas& canvas, int target_size) {
    std::vector<Coord> positions;
    
    if (canvas.is_empty()) {
        if (std::max(tile.width(), tile.height()) == target_size) {
            positions.push_back({0, 0});
        }
        return positions;
    }
    
    int current_width = canvas.xmax - canvas.xmin + 1;
    int current_height = canvas.ymax - canvas.ymin + 1;
    int current_size = std::max(current_width, current_height);
    
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    
    // For delta_area = 0, we need to place the tile such that the bounding BOX size stays the same
    // The bounding box size is max(width, height), not the rectangle dimensions
    // So we can expand the smaller dimension up to current_size without increasing the box size
    if (target_size == current_size) {
        // The new bounding box after placing the tile must satisfy:
        // max(new_width, new_height) == current_size
        // This means we can expand up to a square of size current_size × current_size
        
        // Calculate the virtual square box boundaries
        int box_xmin = canvas.xmin;
        int box_xmax = canvas.xmin + current_size - 1;
        int box_ymin = canvas.ymin;
        int box_ymax = canvas.ymin + current_size - 1;
        
        enumerate_positions_inside_box(tile, canvas, target_size, positions, box_xmin, box_xmax, box_ymin, box_ymax);

        if (current_width < current_height) {
            // also extend left
            box_xmin = canvas.xmax - current_size + 1;
            box_xmax = canvas.xmax;
            box_ymin = canvas.ymin;
            box_ymax = canvas.ymin + current_size - 1;
            // The tile must fit within this square box to keep the bounding box size unchanged
            enumerate_positions_inside_box(tile, canvas, target_size, positions, box_xmin, box_xmax, box_ymin, box_ymax);
        } else if (current_height < current_width) {
            // also extend top
            box_xmin = canvas.xmin;
            box_xmax = canvas.xmin + current_size - 1;
            box_ymin = canvas.ymax - current_size + 1;
            box_ymax = canvas.ymax;
            enumerate_positions_inside_box(tile, canvas, target_size, positions, box_xmin, box_xmax, box_ymin, box_ymax);
        }
    } else {
        // For delta_area > 0, we need to check positions on the boundary of expanded rectangles
        // IMPORTANT: Since we already checked delta_area = 0, we can assume the current bounding
        // box is square (width = height = current_size). Any non-square box would have been
        // balanced during the delta_area = 0 check.
        
        int delta = target_size - current_size;
        
        // To increase the max side from current_size to target_size, we must place a tile
        // such that it extends beyond the current boundary in at least one direction.
        // 
        // The only positions that achieve exactly target_size are along the 4 boundaries:
        // - Left boundary:   tile positioned to extend the left edge outward
        // - Right boundary:  tile positioned to extend the right edge outward
        // - Top boundary:    tile positioned to extend the top edge outward
        // - Bottom boundary: tile positioned to extend the bottom edge outward
        
        // Left boundary: tile extends to the left (new_xmin = canvas.xmin - delta)
        // We need: tminx + dx <= canvas.xmin - delta AND tmaxx + dx >= canvas.xmin - delta
        // Simplest: tminx + dx = canvas.xmin - delta


        // Calculate the virtual square box boundaries
        int box_xmin = canvas.xmin;
        int box_xmax = canvas.xmin + current_size - 1;
        int box_ymin = canvas.ymin;
        int box_ymax = canvas.ymin + current_size - 1;


        // Down
        enumerate_positions_bottom(tile, canvas, target_size, positions, box_xmin, box_xmax, box_ymin, box_ymax, delta);

        // Right
        enumerate_positions_right(tile, canvas, target_size, positions, box_xmin, box_xmax, box_ymin, box_ymax, delta);

        // Top
        box_xmin = canvas.xmin;
        box_xmax = canvas.xmin + current_size - 1;
        box_ymin = canvas.ymax - current_size + 1;
        box_ymax = canvas.ymax;
        enumerate_positions_top(tile, canvas, target_size, positions, box_xmin, box_xmax, box_ymin, box_ymax, delta);

        // Left
        enumerate_positions_left(tile, canvas, target_size, positions, box_xmin, box_xmax, box_ymin, box_ymax, delta);


      
    }
    
    return positions;
}

// ============================================================================
// PlacementChoice Implementation
// ============================================================================

PlacementChoice::PlacementChoice(int idx, int dx_, int dy_, int da, int ov, CellMap pl)
    : tile_idx(idx), dx(dx_), dy(dy_), delta_area(da), overlap(ov), placement(std::move(pl)) {}

// ============================================================================
// GreedySolver Implementation
// ============================================================================

GreedySolver::GreedySolver(std::vector<Tile> tiles_) : tiles(std::move(tiles_)) {
    n = tiles.size();
    for (auto& tile : tiles) {
        tile = tile.normalized();
    }
    placed.resize(n);
}

Canvas GreedySolver::solve(int start_index) {
    if (n == 0) return canvas;
    
    CellMap start_placement = tiles[start_index].translate(0, 0);
    canvas.add_placement(start_placement);
    placed[start_index] = {0, 0};
    order.push_back(start_index);
    
    std::vector<int> remaining;
    remaining.reserve(n - 1);
    for (int i = 0; i < n; ++i) {
        if (i != start_index) {
            remaining.push_back(i);
        }
    }
    
    while (!remaining.empty()) {
        std::optional<PlacementChoice> best_global;
        int current_size = std::max(canvas.xmax - canvas.xmin + 1, canvas.ymax - canvas.ymin + 1);
        
        // Iterate through delta_area from 0 upward across all remaining tiles
        // This allows early termination as soon as we find any valid placement
        int max_tile_size = 0;
        for (int idx : remaining) {
            max_tile_size = std::max(max_tile_size, std::max(tiles[idx].width(), tiles[idx].height()));
        }
        
        int max_search_delta = current_size + max_tile_size;
        bool found = false;
        
        for (int target_size = std::max(current_size, max_tile_size); 
             target_size <= current_size + max_search_delta && !found; 
             ++target_size) {
            
            // Suppose all tile have the same size, we can precompute candidate positions
            auto positions = enumerate_positions_for_size(tiles[0], canvas, target_size);
            // For this target_size, check all remaining tiles
            for (int idx : remaining) {
                const Tile& tile = tiles[idx];
                
                for (const auto& [dx, dy] : positions) {
                    
                    CellMap placement = tile.translate(dx, dy);
                    auto [ok, overlap] = canvas.overlap_check(placement);
                    if (!ok) continue;
                    
                    int delta = target_size - current_size;
                    PlacementChoice cand(idx, dx, dy, delta, overlap, std::move(placement));
                    
                    if (!best_global.has_value() || cand.overlap > best_global->overlap) {
                        best_global = std::move(cand);
                    }
                }
            }
            
            // If we found any valid placement for this target_size, stop searching
            if (best_global.has_value()) {
                found = true;
            }
        }

        assert(best_global.has_value());


        canvas.add_placement(best_global->placement);
        placed[best_global->tile_idx] = {best_global->dx, best_global->dy};
        order.push_back(best_global->tile_idx);
        
        remaining.erase(
            std::remove(remaining.begin(), remaining.end(), best_global->tile_idx),
            remaining.end()
        );
    }
    
    return canvas;
}

// ============================================================================
// Solve Function
// ============================================================================

GreedyResult solve_greedy(const std::vector<Tile>& tiles, int start_index) {
    auto start = std::chrono::high_resolution_clock::now();
    
    GreedySolver solver(tiles);
    Canvas final_canvas = solver.solve(start_index);
    
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;
    
    GreedyResult result;
    result.wall_time_sec = elapsed.count();
    
    if (final_canvas.is_empty()) {
        result.best_obj = 0;
        result.bbox_width = 0;
        result.bbox_height = 0;
        result.bbox_area = 0;
    } else {
        int width = final_canvas.xmax - final_canvas.xmin + 1;
        int height = final_canvas.ymax - final_canvas.ymin + 1;
        result.best_obj = std::max(width, height);
        result.bbox_width = width;
        result.bbox_height = height;
        result.bbox_area = final_canvas.bbox_area();
    }
    
    result.order = solver.order;
    for (int idx : solver.order) {
        if (solver.placed[idx].has_value()) {
            auto [dx, dy] = *solver.placed[idx];
            result.placements.push_back({idx, dx, dy});
        }
    }
    
    result.canvas_xmin = final_canvas.xmin;
    result.canvas_xmax = final_canvas.xmax;
    result.canvas_ymin = final_canvas.ymin;
    result.canvas_ymax = final_canvas.ymax;
    
    return result;
}
