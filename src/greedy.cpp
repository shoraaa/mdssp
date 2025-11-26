#include "greedy.hpp"
#include <chrono>
#include <unordered_set>
#include <sstream>
#include <cassert>
#include <iostream>
#include <random>
#include <algorithm>
#include <numeric>
#include <omp.h>

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

// Compute the new bounding box objective after placing a tile
// Returns max(width, height) for BOUNDING_SQUARE or width * height for RECTANGLE_AREA
static int compute_new_bbox_objective(const Tile& tile, int dx, int dy, const Canvas& canvas, ObjectiveType obj_type) {
    if (canvas.is_empty()) {
        if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
            return std::max(tile.width(), tile.height());
        } else {
            return tile.width() * tile.height();
        }
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
    
    if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
        return std::max(new_width, new_height);
    } else {
        return new_width * new_height;
    }
}

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

// Generate candidate positions for a tile that would result in approximately target_objective
// Works for both BOUNDING_SQUARE and RECTANGLE_AREA objectives
static std::vector<Coord> enumerate_positions_for_objective(const Tile& tile, const Canvas& canvas, 
                                                             int target_objective, ObjectiveType obj_type) {
    std::vector<Coord> positions;
    
    if (canvas.is_empty()) {
        int tile_obj = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                       ? std::max(tile.width(), tile.height())
                       : tile.width() * tile.height();
        if (tile_obj == target_objective) {
            positions.push_back({0, 0});
        }
        return positions;
    }
    
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    
    int current_width = canvas.xmax - canvas.xmin + 1;
    int current_height = canvas.ymax - canvas.ymin + 1;
    int current_area = current_width * current_height;
    
    // Optimization for RECTANGLE_AREA: when target area > current area,
    // only positions that extend the bounding box can increase the area
    if (obj_type == ObjectiveType::RECTANGLE_AREA && target_objective > current_area) {
        // Only check positions along the 4 edges and 4 corners
        int search_range = std::max({tile.width(), tile.height(), current_width, current_height}) + 5;
        
        // Define the ranges for dx and dy
        int dx_min = canvas.xmin - tmaxx - search_range;
        int dx_max = canvas.xmax - tminx + search_range;
        int dy_min = canvas.ymin - tmaxy - search_range;
        int dy_max = canvas.ymax - tminy + search_range;
        
        // 1. Top edge (dy = dy_min to canvas.ymin - tminy)
        for (int dy = dy_min; dy < canvas.ymin - tminy; ++dy) {
            for (int dx = dx_min; dx <= dx_max; ++dx) {
                int new_obj = compute_new_bbox_objective(tile, dx, dy, canvas, obj_type);
                if (new_obj == target_objective) {
                    positions.push_back({dx, dy});
                }
            }
        }
        
        // 2. Bottom edge (dy = canvas.ymax - tmaxy + 1 to dy_max)
        for (int dy = canvas.ymax - tmaxy + 1; dy <= dy_max; ++dy) {
            for (int dx = dx_min; dx <= dx_max; ++dx) {
                int new_obj = compute_new_bbox_objective(tile, dx, dy, canvas, obj_type);
                if (new_obj == target_objective) {
                    positions.push_back({dx, dy});
                }
            }
        }
        
        // 3. Left edge (dx = dx_min to canvas.xmin - tminx - 1, dy in middle range)
        for (int dx = dx_min; dx < canvas.xmin - tminx; ++dx) {
            for (int dy = canvas.ymin - tminy; dy <= canvas.ymax - tmaxy; ++dy) {
                int new_obj = compute_new_bbox_objective(tile, dx, dy, canvas, obj_type);
                if (new_obj == target_objective) {
                    positions.push_back({dx, dy});
                }
            }
        }
        
        // 4. Right edge (dx = canvas.xmax - tmaxx + 1 to dx_max, dy in middle range)
        for (int dx = canvas.xmax - tmaxx + 1; dx <= dx_max; ++dx) {
            for (int dy = canvas.ymin - tminy; dy <= canvas.ymax - tmaxy; ++dy) {
                int new_obj = compute_new_bbox_objective(tile, dx, dy, canvas, obj_type);
                if (new_obj == target_objective) {
                    positions.push_back({dx, dy});
                }
            }
        }
    } else {
        // For target_objective <= current_area, or for BOUNDING_SQUARE,
        // we need to search the interior as well
        int search_range = std::max({tile.width(), tile.height(), current_width, current_height}) + 5;
        
        // Sample positions around the canvas perimeter and interior
        for (int dx = canvas.xmin - tmaxx - search_range; dx <= canvas.xmax - tminx + search_range; dx += 1) {
            for (int dy = canvas.ymin - tmaxy - search_range; dy <= canvas.ymax - tminy + search_range; dy += 1) {
                int new_obj = compute_new_bbox_objective(tile, dx, dy, canvas, obj_type);
                if (new_obj == target_objective) {
                    positions.push_back({dx, dy});
                }
            }
        }
    }
    
    return positions;
}

// Generate all candidate positions for a tile that would result in exactly target_size
// This function is optimized for BOUNDING_SQUARE objective
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

GreedySolver::GreedySolver(std::vector<Tile> tiles_, ObjectiveType obj_type_) 
    : tiles(std::move(tiles_)), obj_type(obj_type_) {
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
        int current_width = canvas.xmax - canvas.xmin + 1;
        int current_height = canvas.ymax - canvas.ymin + 1;
        int current_objective = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                                ? std::max(current_width, current_height)
                                : current_width * current_height;
        
        // Iterate through increasing objective values
        // This allows early termination as soon as we find any valid placement
        int max_tile_obj = 0;
        for (int idx : remaining) {
            if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
                max_tile_obj = std::max(max_tile_obj, std::max(tiles[idx].width(), tiles[idx].height()));
            } else {
                max_tile_obj = std::max(max_tile_obj, tiles[idx].width() * tiles[idx].height());
            }
        }
        
        int max_search_range = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                               ? current_objective + max_tile_obj
                               : current_objective + max_tile_obj * 10; // Larger range for area
        bool found = false;
        
        for (int target_objective = std::max(current_objective, max_tile_obj); 
             target_objective <= max_search_range && !found; 
             ++target_objective) {
            
            // Get candidate positions for this objective value
            std::vector<Coord> positions;
            if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
                // Use optimized enumeration for bounding square
                positions = enumerate_positions_for_size(tiles[0], canvas, target_objective);
            } else {
                // Use general enumeration for rectangle area
                positions = enumerate_positions_for_objective(tiles[0], canvas, target_objective, obj_type);
            }
            int delta = target_objective - current_objective;
            
            // Parallel search through remaining tiles
            #pragma omp parallel
            {
                std::optional<PlacementChoice> thread_best;
                
                #pragma omp for schedule(dynamic)
                for (size_t i = 0; i < remaining.size(); ++i) {
                    int idx = remaining[i];
                    const Tile& tile = tiles[idx];
                    
                    // Check if any thread has already found a solution
                    #pragma omp flush(found)
                    if (found) continue;
                    
                    for (const auto& [dx, dy] : positions) {
                        CellMap placement = tile.translate(dx, dy);
                        auto [ok, overlap] = canvas.overlap_check(placement);
                        if (!ok) continue;
                        
                        PlacementChoice cand(idx, dx, dy, delta, overlap, std::move(placement));
                        
                        if (!thread_best.has_value() || cand.overlap > thread_best->overlap) {
                            thread_best = std::move(cand);
                            break; // Found a placement for this tile
                        }
                    }
                }
                
                // Update global best with critical section
                if (thread_best.has_value()) {
                    #pragma omp critical
                    {
                        if (!best_global.has_value() || thread_best->overlap > best_global->overlap) {
                            best_global = std::move(thread_best);
                        }
                        found = true;
                    }
                }
            }
        }

        assert(best_global.has_value());
        printf("Remaining: %d, placed with delta_area=%d, overlap=%d, current bbox size=%d\n",
               remaining.size(),
               best_global->delta_area, best_global->overlap,
               std::max(canvas.xmax - canvas.xmin + 1, canvas.ymax - canvas.ymin + 1));

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

GreedyResult solve_greedy(const std::vector<Tile>& tiles, int start_index, ObjectiveType obj_type) {
    auto start = std::chrono::high_resolution_clock::now();
    
    GreedySolver solver(tiles, obj_type);
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
        result.bbox_width = width;
        result.bbox_height = height;
        result.bbox_area = final_canvas.bbox_area();
        result.best_obj = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                          ? std::max(width, height) 
                          : width * height;
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

// ============================================================================
// StochasticGreedySolver Implementation
// ============================================================================

StochasticGreedySolver::StochasticGreedySolver(std::vector<Tile> tiles_, unsigned int seed, ObjectiveType obj_type_) 
    : tiles(std::move(tiles_)), rng(seed), obj_type(obj_type_) {
    n = tiles.size();
    for (auto& tile : tiles) {
        tile = tile.normalized();
    }
    placed.resize(n);
}

Canvas StochasticGreedySolver::solve(int start_index) {
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
        int current_width = canvas.xmax - canvas.xmin + 1;
        int current_height = canvas.ymax - canvas.ymin + 1;
        int current_objective = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                                ? std::max(current_width, current_height)
                                : current_width * current_height;
        
        // Iterate through increasing objective values
        int max_tile_obj = 0;
        for (int idx : remaining) {
            if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
                max_tile_obj = std::max(max_tile_obj, std::max(tiles[idx].width(), tiles[idx].height()));
            } else {
                max_tile_obj = std::max(max_tile_obj, tiles[idx].width() * tiles[idx].height());
            }
        }
        
        int max_search_range = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                               ? current_objective + max_tile_obj
                               : current_objective + max_tile_obj * 10;
        std::vector<PlacementChoice> candidates_at_min_bbox;
        int min_bbox_increase = 10000000;
        
        for (int target_objective = std::max(current_objective, max_tile_obj); 
             target_objective <= min_bbox_increase; 
             ++target_objective) {
            
            int delta = target_objective - current_objective;    
            // Precompute candidate positions for this objective value
            std::vector<Coord> positions;
            if (obj_type == ObjectiveType::BOUNDING_SQUARE) {
                positions = enumerate_positions_for_size(tiles[0], canvas, target_objective);
            } else {
                positions = enumerate_positions_for_objective(tiles[0], canvas, target_objective, obj_type);
            }
            
            // Parallel search through remaining tiles
            #pragma omp parallel
            {
                std::vector<PlacementChoice> thread_candidates;
                
                #pragma omp for schedule(dynamic)
                for (size_t i = 0; i < remaining.size(); ++i) {
                    int idx = remaining[i];
                    const Tile& tile = tiles[idx];
                    
                    for (const auto& [dx, dy] : positions) {
                        CellMap placement = tile.translate(dx, dy);
                        auto [ok, overlap] = canvas.overlap_check(placement);
                        if (!ok) continue;
                        
                        PlacementChoice cand(idx, dx, dy, delta, overlap, std::move(placement));
                        thread_candidates.push_back(std::move(cand));
                    }
                }
                
                // Merge thread candidates into global list
                #pragma omp critical
                {
                    for (auto& cand : thread_candidates) {
                        // First valid placement sets the min_bbox_increase
                        if (cand.delta_area < min_bbox_increase) {
                            min_bbox_increase = cand.delta_area;
                            candidates_at_min_bbox.clear();
                        }
                        
                        // Only keep candidates with the minimum bbox increase
                        if (cand.delta_area == min_bbox_increase) {
                            candidates_at_min_bbox.push_back(std::move(cand));
                        }
                    }
                }
            }
            
            // If we found any candidates with this bbox increase, we're done searching
            if (!candidates_at_min_bbox.empty()) {
                break;
            }
        }
        
        assert(!candidates_at_min_bbox.empty());
        
        // Sample from candidates weighted by overlap count
        // Build cumulative weights
        std::vector<int> weights;
        weights.reserve(candidates_at_min_bbox.size());
        for (const auto& cand : candidates_at_min_bbox) {
            weights.push_back(cand.overlap + 1); // +1 to ensure non-zero weight
        }
        
        std::discrete_distribution<int> dist(weights.begin(), weights.end());
        int chosen_idx = dist(rng);
        
        PlacementChoice& chosen = candidates_at_min_bbox[chosen_idx];
        
        canvas.add_placement(chosen.placement);
        placed[chosen.tile_idx] = {chosen.dx, chosen.dy};
        order.push_back(chosen.tile_idx);
        
        remaining.erase(
            std::remove(remaining.begin(), remaining.end(), chosen.tile_idx),
            remaining.end()
        );
    }
    
    return canvas;
}

GreedyResult solve_greedy_stochastic(const std::vector<Tile>& tiles, int start_index, unsigned int seed, ObjectiveType obj_type) {
    auto start = std::chrono::high_resolution_clock::now();
    
    // If seed is 0, use random_device to generate a random seed
    if (seed == 0) {
        seed = std::random_device{}();
    }
    
    StochasticGreedySolver solver(tiles, seed, obj_type);
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
        result.bbox_width = width;
        result.bbox_height = height;
        result.bbox_area = final_canvas.bbox_area();
        result.best_obj = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                          ? std::max(width, height) 
                          : width * height;
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

// ============================================================================
// Merge-based Greedy Algorithm
// ============================================================================

struct MergedTile {
    CellMap cells;
    std::vector<std::tuple<int, int, int>> placements; // original_tile_idx, dx, dy
    
    MergedTile() = default;
    
    explicit MergedTile(const Tile& tile, int original_idx) {
        cells = tile.cells;
        placements.push_back({original_idx, 0, 0});
    }
    
    int min_x() const {
        if (cells.empty()) return 0;
        int minx = std::numeric_limits<int>::max();
        for (const auto& [coord, _] : cells) {
            minx = std::min(minx, coord.first);
        }
        return minx;
    }
    
    int min_y() const {
        if (cells.empty()) return 0;
        int miny = std::numeric_limits<int>::max();
        for (const auto& [coord, _] : cells) {
            miny = std::min(miny, coord.second);
        }
        return miny;
    }
    
    int max_x() const {
        if (cells.empty()) return -1;
        int maxx = std::numeric_limits<int>::min();
        for (const auto& [coord, _] : cells) {
            maxx = std::max(maxx, coord.first);
        }
        return maxx;
    }
    
    int max_y() const {
        if (cells.empty()) return -1;
        int maxy = std::numeric_limits<int>::min();
        for (const auto& [coord, _] : cells) {
            maxy = std::max(maxy, coord.second);
        }
        return maxy;
    }
    
    int width() const {
        return cells.empty() ? 0 : max_x() - min_x() + 1;
    }
    
    int height() const {
        return cells.empty() ? 0 : max_y() - min_y() + 1;
    }
};

struct MergeOption {
    int tile1_idx;
    int tile2_idx;
    int dx, dy; // offset for tile2 relative to tile1
    int overlap_count;
    int bbox_size; // max(width, height) of merged tile
    CellMap merged_cells;
    std::vector<std::tuple<int, int, int>> merged_placements;
    
    MergeOption() : tile1_idx(-1), tile2_idx(-1), dx(0), dy(0), 
                    overlap_count(0), bbox_size(0) {}
};

// Find the best merge between two tiles, considering all possible relative positions
static MergeOption find_best_merge(const MergedTile& tile1, int idx1, 
                                   const MergedTile& tile2, int idx2) {
    MergeOption best;
    
    // Try different offsets for tile2 relative to tile1
    int search_range = std::max({tile1.width(), tile1.height(), tile2.width(), tile2.height()}) + 2;
    
    for (int dx = -search_range; dx <= search_range; ++dx) {
        for (int dy = -search_range; dy <= search_range; ++dy) {
            // Create translated tile2
            CellMap tile2_translated;
            for (const auto& [coord, label] : tile2.cells) {
                tile2_translated[{coord.first + dx, coord.second + dy}] = label;
            }
            
            // Check if merge is valid and count overlaps
            CellMap merged = tile1.cells;
            int overlap_count = 0;
            bool valid = true;
            
            for (const auto& [coord, label] : tile2_translated) {
                auto it = merged.find(coord);
                if (it != merged.end()) {
                    if (it->second != label) {
                        valid = false;
                        break;
                    }
                    overlap_count++;
                } else {
                    merged[coord] = label;
                }
            }
            
            if (!valid) continue;
            
            // Calculate bounding box
            int xmin = std::numeric_limits<int>::max();
            int xmax = std::numeric_limits<int>::min();
            int ymin = std::numeric_limits<int>::max();
            int ymax = std::numeric_limits<int>::min();
            
            for (const auto& [coord, _] : merged) {
                xmin = std::min(xmin, coord.first);
                xmax = std::max(xmax, coord.first);
                ymin = std::min(ymin, coord.second);
                ymax = std::max(ymax, coord.second);
            }
            
            int width = xmax - xmin + 1;
            int height = ymax - ymin + 1;
            int bbox_size = std::max(width, height);
            
            // Check if this is the best merge so far
            // Prioritize: 1) maximum overlap, 2) minimum bbox_size
            bool is_better = false;
            if (best.tile1_idx == -1) {
                is_better = true;
            } else if (overlap_count > best.overlap_count) {
                is_better = true;
            } else if (overlap_count == best.overlap_count && bbox_size < best.bbox_size) {
                is_better = true;
            }
            
            if (is_better) {
                best.tile1_idx = idx1;
                best.tile2_idx = idx2;
                best.dx = dx;
                best.dy = dy;
                best.overlap_count = overlap_count;
                best.bbox_size = bbox_size;
                best.merged_cells = merged;
                
                // Merge placement lists
                best.merged_placements = tile1.placements;
                for (const auto& [orig_idx, orig_dx, orig_dy] : tile2.placements) {
                    best.merged_placements.push_back({orig_idx, orig_dx + dx, orig_dy + dy});
                }
            }
        }
    }
    
    return best;
}

GreedyResult solve_greedy_merge(const std::vector<Tile>& tiles, ObjectiveType obj_type) {
    auto start = std::chrono::high_resolution_clock::now();
    
    // Initialize with all tiles as separate MergedTiles
    std::vector<MergedTile> merged_tiles;
    merged_tiles.reserve(tiles.size());
    
    for (size_t i = 0; i < tiles.size(); ++i) {
        merged_tiles.emplace_back(tiles[i], (int)i);
    }
    
    // Repeatedly merge tiles until only one remains
    while (merged_tiles.size() > 1) {
        MergeOption best_merge;
        
        // Find the best merge among all pairs
        for (size_t i = 0; i < merged_tiles.size(); ++i) {
            for (size_t j = i + 1; j < merged_tiles.size(); ++j) {
                MergeOption candidate = find_best_merge(merged_tiles[i], (int)i, 
                                                      merged_tiles[j], (int)j);
                
                if (candidate.tile1_idx != -1) {
                    bool is_better = false;
                    if (best_merge.tile1_idx == -1) {
                        is_better = true;
                    } else if (candidate.overlap_count > best_merge.overlap_count) {
                        is_better = true;
                    } else if (candidate.overlap_count == best_merge.overlap_count && 
                             candidate.bbox_size < best_merge.bbox_size) {
                        is_better = true;
                    }
                    
                    if (is_better) {
                        best_merge = candidate;
                    }
                }
            }
        }
        
        if (best_merge.tile1_idx == -1) {
            // No valid merge found - this shouldn't happen with valid tiles
            break;
        }
        
        // Apply the best merge
        MergedTile new_tile;
        new_tile.cells = best_merge.merged_cells;
        new_tile.placements = best_merge.merged_placements;
        
        // Remove the two merged tiles and add the new one
        std::vector<MergedTile> new_merged_tiles;
        new_merged_tiles.reserve(merged_tiles.size() - 1);
        
        for (size_t i = 0; i < merged_tiles.size(); ++i) {
            if ((int)i != best_merge.tile1_idx && (int)i != best_merge.tile2_idx) {
                new_merged_tiles.push_back(std::move(merged_tiles[i]));
            }
        }
        new_merged_tiles.push_back(std::move(new_tile));
        
        merged_tiles = std::move(new_merged_tiles);
    }
    
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;
    
    GreedyResult result;
    result.wall_time_sec = elapsed.count();
    
    if (merged_tiles.empty() || merged_tiles[0].cells.empty()) {
        result.best_obj = 0;
        result.bbox_width = 0;
        result.bbox_height = 0;
        result.bbox_area = 0;
    } else {
        const MergedTile& final_tile = merged_tiles[0];
        int width = final_tile.width();
        int height = final_tile.height();
        result.bbox_width = width;
        result.bbox_height = height;
        result.bbox_area = width * height;
        result.best_obj = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                          ? std::max(width, height) 
                          : width * height;
        
        // Convert placements from tuple format to vector format
        for (const auto& [tile_idx, dx, dy] : final_tile.placements) {
            result.placements.push_back({tile_idx, dx, dy});
            result.order.push_back(tile_idx);
        }
    }
    
    return result;
}

// ============================================================================
// Partial Greedy Solver Implementation
// ============================================================================

GreedyResult solve_greedy_partial(const std::vector<Tile>& tiles, int start_index, int max_tiles, ObjectiveType obj_type) {
    auto start = std::chrono::high_resolution_clock::now();
    
    GreedySolver solver(tiles, obj_type);
    
    if (solver.n == 0) {
        GreedyResult result;
        result.wall_time_sec = 0.0;
        result.best_obj = 0;
        result.bbox_width = 0;
        result.bbox_height = 0;
        result.bbox_area = 0;
        return result;
    }
    
    // Place the start tile
    CellMap start_placement = solver.tiles[start_index].translate(0, 0);
    solver.canvas.add_placement(start_placement);
    solver.placed[start_index] = {0, 0};
    solver.order.push_back(start_index);
    
    std::vector<int> remaining;
    remaining.reserve(solver.n - 1);
    for (int i = 0; i < solver.n; ++i) {
        if (i != start_index) {
            remaining.push_back(i);
        }
    }
    
    // Place tiles up to max_tiles (including the start tile)
    int tiles_placed = 1;
    while (!remaining.empty() && tiles_placed < max_tiles) {
        std::optional<PlacementChoice> best_global;
        int current_size = std::max(solver.canvas.xmax - solver.canvas.xmin + 1, 
                                    solver.canvas.ymax - solver.canvas.ymin + 1);
        
        int max_tile_size = 0;
        for (int idx : remaining) {
            max_tile_size = std::max(max_tile_size, 
                std::max(solver.tiles[idx].width(), solver.tiles[idx].height()));
        }
        
        int max_search_delta = current_size + max_tile_size;
        bool found = false;
        
        for (int target_size = std::max(current_size, max_tile_size); 
             target_size <= current_size + max_search_delta && !found; 
             ++target_size) {
            
            auto positions = enumerate_positions_for_size(solver.tiles[0], solver.canvas, target_size);
            int delta = target_size - current_size;
            
            #pragma omp parallel
            {
                std::optional<PlacementChoice> thread_best;
                
                #pragma omp for schedule(dynamic)
                for (size_t i = 0; i < remaining.size(); ++i) {
                    int idx = remaining[i];
                    const Tile& tile = solver.tiles[idx];
                    
                    #pragma omp flush(found)
                    if (found) continue;
                    
                    for (const auto& [dx, dy] : positions) {
                        CellMap placement = tile.translate(dx, dy);
                        auto [ok, overlap] = solver.canvas.overlap_check(placement);
                        if (!ok) continue;
                        
                        PlacementChoice cand(idx, dx, dy, delta, overlap, std::move(placement));
                        
                        if (!thread_best.has_value() || cand.overlap > thread_best->overlap) {
                            thread_best = std::move(cand);
                            break;
                        }
                    }
                }
                
                if (thread_best.has_value()) {
                    #pragma omp critical
                    {
                        if (!best_global.has_value() || thread_best->overlap > best_global->overlap) {
                            best_global = std::move(thread_best);
                        }
                        found = true;
                    }
                }
            }
        }

        if (best_global.has_value()) {
            solver.canvas.add_placement(best_global->placement);
            solver.placed[best_global->tile_idx] = {best_global->dx, best_global->dy};
            solver.order.push_back(best_global->tile_idx);
            
            remaining.erase(
                std::remove(remaining.begin(), remaining.end(), best_global->tile_idx),
                remaining.end()
            );
            tiles_placed++;
        } else {
            break; // No valid placement found
        }
    }
    
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;
    
    GreedyResult result;
    result.wall_time_sec = elapsed.count();
    
    if (solver.canvas.is_empty()) {
        result.best_obj = 0;
        result.bbox_width = 0;
        result.bbox_height = 0;
        result.bbox_area = 0;
    } else {
        int width = solver.canvas.xmax - solver.canvas.xmin + 1;
        int height = solver.canvas.ymax - solver.canvas.ymin + 1;
        result.bbox_width = width;
        result.bbox_height = height;
        result.bbox_area = solver.canvas.bbox_area();
        result.best_obj = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                          ? std::max(width, height) 
                          : width * height;
    }
    
    result.order = solver.order;
    for (int idx : solver.order) {
        if (solver.placed[idx].has_value()) {
            auto [dx, dy] = *solver.placed[idx];
            result.placements.push_back({idx, dx, dy});
        }
    }
    
    result.canvas_xmin = solver.canvas.xmin;
    result.canvas_xmax = solver.canvas.xmax;
    result.canvas_ymin = solver.canvas.ymin;
    result.canvas_ymax = solver.canvas.ymax;
    
    return result;
}

GreedyResult solve_greedy_stochastic_partial(const std::vector<Tile>& tiles, int start_index, 
                                             unsigned int seed, int max_tiles, ObjectiveType obj_type) {
    auto start = std::chrono::high_resolution_clock::now();
    
    if (seed == 0) {
        seed = std::random_device{}();
    }
    
    StochasticGreedySolver solver(tiles, seed, obj_type);
    
    if (solver.n == 0) {
        GreedyResult result;
        result.wall_time_sec = 0.0;
        result.best_obj = 0;
        result.bbox_width = 0;
        result.bbox_height = 0;
        result.bbox_area = 0;
        return result;
    }
    
    // Place the start tile
    CellMap start_placement = solver.tiles[start_index].translate(0, 0);
    solver.canvas.add_placement(start_placement);
    solver.placed[start_index] = {0, 0};
    solver.order.push_back(start_index);
    
    std::vector<int> remaining;
    remaining.reserve(solver.n - 1);
    for (int i = 0; i < solver.n; ++i) {
        if (i != start_index) {
            remaining.push_back(i);
        }
    }
    
    // Place tiles up to max_tiles (including the start tile)
    int tiles_placed = 1;
    while (!remaining.empty() && tiles_placed < max_tiles) {
        int current_size = std::max(solver.canvas.xmax - solver.canvas.xmin + 1, 
                                    solver.canvas.ymax - solver.canvas.ymin + 1);
        
        int max_tile_size = 0;
        for (int idx : remaining) {
            max_tile_size = std::max(max_tile_size, 
                std::max(solver.tiles[idx].width(), solver.tiles[idx].height()));
        }
        
        int max_search_delta = current_size + max_tile_size;
        std::vector<PlacementChoice> candidates_at_min_bbox;
        int min_bbox_increase = 10000000;
        
        for (int target_size = std::max(current_size, max_tile_size); 
             target_size <= min_bbox_increase; 
             ++target_size) {
            
            int delta = target_size - current_size;    
            auto positions = enumerate_positions_for_size(solver.tiles[0], solver.canvas, target_size);
            
            #pragma omp parallel
            {
                std::vector<PlacementChoice> thread_candidates;
                
                #pragma omp for schedule(dynamic)
                for (size_t i = 0; i < remaining.size(); ++i) {
                    int idx = remaining[i];
                    const Tile& tile = solver.tiles[idx];
                    
                    for (const auto& [dx, dy] : positions) {
                        CellMap placement = tile.translate(dx, dy);
                        auto [ok, overlap] = solver.canvas.overlap_check(placement);
                        if (!ok) continue;
                        
                        PlacementChoice cand(idx, dx, dy, delta, overlap, std::move(placement));
                        thread_candidates.push_back(std::move(cand));
                    }
                }
                
                #pragma omp critical
                {
                    for (auto& cand : thread_candidates) {
                        if (cand.delta_area < min_bbox_increase) {
                            min_bbox_increase = cand.delta_area;
                            candidates_at_min_bbox.clear();
                        }
                        
                        if (cand.delta_area == min_bbox_increase) {
                            candidates_at_min_bbox.push_back(std::move(cand));
                        }
                    }
                }
            }
            
            if (!candidates_at_min_bbox.empty()) {
                break;
            }
        }
        
        if (candidates_at_min_bbox.empty()) {
            break; // No valid placement found
        }
        
        // Sample from candidates weighted by overlap count
        std::vector<int> weights;
        weights.reserve(candidates_at_min_bbox.size());
        for (const auto& cand : candidates_at_min_bbox) {
            weights.push_back(cand.overlap + 1);
        }
        
        std::discrete_distribution<int> dist(weights.begin(), weights.end());
        int chosen_idx = dist(solver.rng);
        
        PlacementChoice& chosen = candidates_at_min_bbox[chosen_idx];
        
        solver.canvas.add_placement(chosen.placement);
        solver.placed[chosen.tile_idx] = {chosen.dx, chosen.dy};
        solver.order.push_back(chosen.tile_idx);
        
        remaining.erase(
            std::remove(remaining.begin(), remaining.end(), chosen.tile_idx),
            remaining.end()
        );
        tiles_placed++;
    }
    
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> elapsed = end - start;
    
    GreedyResult result;
    result.wall_time_sec = elapsed.count();
    
    if (solver.canvas.is_empty()) {
        result.best_obj = 0;
        result.bbox_width = 0;
        result.bbox_height = 0;
        result.bbox_area = 0;
    } else {
        int width = solver.canvas.xmax - solver.canvas.xmin + 1;
        int height = solver.canvas.ymax - solver.canvas.ymin + 1;
        result.bbox_width = width;
        result.bbox_height = height;
        result.bbox_area = solver.canvas.bbox_area();
        result.best_obj = (obj_type == ObjectiveType::BOUNDING_SQUARE) 
                          ? std::max(width, height) 
                          : width * height;
    }
    
    result.order = solver.order;
    for (int idx : solver.order) {
        if (solver.placed[idx].has_value()) {
            auto [dx, dy] = *solver.placed[idx];
            result.placements.push_back({idx, dx, dy});
        }
    }
    
    result.canvas_xmin = solver.canvas.xmin;
    result.canvas_xmax = solver.canvas.xmax;
    result.canvas_ymin = solver.canvas.ymin;
    result.canvas_ymax = solver.canvas.ymax;
    
    return result;
}

