#include "greedy.hpp"
#include <chrono>
#include <unordered_set>
#include <sstream>

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

static std::vector<Coord> enumerate_overlap_offsets(const Tile& tile, const Canvas& canvas) {
    std::vector<Coord> offsets;
    
    if (canvas.is_empty()) {
        offsets.push_back({0, 0});
        return offsets;
    }
    
    std::unordered_map<Label, std::vector<Coord>> inv;
    for (const auto& [coord, ch] : canvas.cells) {
        inv[ch].push_back(coord);
    }
    
    for (const auto& [tcoord, tch] : tile.cells) {
        auto it = inv.find(tch);
        if (it != inv.end()) {
            for (const auto& ccoord : it->second) {
                int dx = ccoord.first - tcoord.first;
                int dy = ccoord.second - tcoord.second;
                offsets.push_back({dx, dy});
            }
        }
    }
    
    return offsets;
}

static std::vector<Coord> enumerate_border_offsets_simple(const Tile& tile, const Canvas& canvas) {
    std::vector<Coord> offsets;
    
    if (canvas.is_empty()) {
        offsets.push_back({0, 0});
        return offsets;
    }
    
    int tminx = tile.min_x();
    int tmaxx = tile.max_x();
    int tminy = tile.min_y();
    int tmaxy = tile.max_y();
    int tw = tile.width();
    int th = tile.height();
    
    int left_dx = canvas.xmin - (tmaxx + 1);
    int right_dx = canvas.xmax - tminx + 1;
    int top_dy = canvas.ymin - (tmaxy + 1);
    int bot_dy = canvas.ymax - tminy + 1;
    
    std::vector<int> y_aligns = {
        canvas.ymin - tminy,
        canvas.ymin - tminy + (canvas.ymax - canvas.ymin - th) / 2,
        canvas.ymax - tmaxy
    };
    
    std::vector<int> x_aligns = {
        canvas.xmin - tminx,
        canvas.xmin - tminx + (canvas.xmax - canvas.xmin - tw) / 2,
        canvas.xmax - tmaxx
    };
    
    for (int dy : y_aligns) {
        offsets.push_back({left_dx, dy});
        offsets.push_back({right_dx, dy});
    }
    
    for (int dx : x_aligns) {
        offsets.push_back({dx, top_dy});
        offsets.push_back({dx, bot_dy});
    }
    
    return offsets;
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

std::optional<PlacementChoice> GreedySolver::best_placement_for_tile(int idx) {
    const Tile& tile = tiles[idx];
    int cur_area = canvas.bbox_area();
    std::optional<PlacementChoice> best;
    
    auto overlap_offs = enumerate_overlap_offsets(tile, canvas);
    auto border_offs = enumerate_border_offsets_simple(tile, canvas);
    
    std::unordered_set<Coord> seen;
    std::vector<Coord> all_offsets;
    all_offsets.reserve(overlap_offs.size() + border_offs.size());
    all_offsets.insert(all_offsets.end(), overlap_offs.begin(), overlap_offs.end());
    all_offsets.insert(all_offsets.end(), border_offs.begin(), border_offs.end());
    
    for (const auto& [dx, dy] : all_offsets) {
        if (seen.count({dx, dy})) continue;
        seen.insert({dx, dy});
        
        CellMap placement = tile.translate(dx, dy);
        auto [ok, overlap] = canvas.overlap_check(placement);
        if (!ok) continue;
        
        int nxmin = std::numeric_limits<int>::max();
        int nxmax = std::numeric_limits<int>::min();
        int nymin = std::numeric_limits<int>::max();
        int nymax = std::numeric_limits<int>::min();
        
        for (const auto& [coord, _] : canvas.cells) {
            nxmin = std::min(nxmin, coord.first);
            nxmax = std::max(nxmax, coord.first);
            nymin = std::min(nymin, coord.second);
            nymax = std::max(nymax, coord.second);
        }
        
        for (const auto& [coord, _] : placement) {
            nxmin = std::min(nxmin, coord.first);
            nxmax = std::max(nxmax, coord.first);
            nymin = std::min(nymin, coord.second);
            nymax = std::max(nymax, coord.second);
        }
        
        int new_area = (nxmax >= nxmin && nymax >= nymin) 
            ? std::max(nxmax - nxmin + 1, nymax - nymin + 1) 
            : 0;
        int delta = new_area - cur_area;
        
        PlacementChoice cand(idx, dx, dy, delta, overlap, std::move(placement));
        
        if (!best.has_value()) {
            best = std::move(cand);
        } else {
            if (cand.delta_area < best->delta_area || 
                (cand.delta_area == best->delta_area && cand.overlap > best->overlap)) {
                best = std::move(cand);
                if (best->delta_area == 0) break;
            }
        }
    }
    
    return best;
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
        
        for (int idx : remaining) {
            auto cand = best_placement_for_tile(idx);
            if (!cand.has_value()) continue;
            
            if (!best_global.has_value()) {
                best_global = std::move(cand);
            } else {
                if (cand->delta_area < best_global->delta_area ||
                    (cand->delta_area == best_global->delta_area && 
                     cand->overlap > best_global->overlap)) {
                    best_global = std::move(cand);
                }
            }
        }
        
        if (!best_global.has_value()) {
            int idx = remaining[0];
            remaining.erase(remaining.begin());
            
            int dx = !canvas.is_empty() 
                ? (canvas.xmax - canvas.xmin + 1) + 1 - tiles[idx].min_x() 
                : 0;
            int dy = 0;
            CellMap placement = tiles[idx].translate(dx, dy);
            
            auto [ok, overlap] = canvas.overlap_check(placement);
            if (!ok) {
                int offset = 0;
                while (true) {
                    offset++;
                    placement = tiles[idx].translate(dx, dy + offset);
                    auto [ok2, _] = canvas.overlap_check(placement);
                    if (ok2) {
                        dy += offset;
                        break;
                    }
                }
            }
            
            canvas.add_placement(placement);
            placed[idx] = {dx, dy};
            order.push_back(idx);
        } else {
            canvas.add_placement(best_global->placement);
            placed[best_global->tile_idx] = {best_global->dx, best_global->dy};
            order.push_back(best_global->tile_idx);
            
            remaining.erase(
                std::remove(remaining.begin(), remaining.end(), best_global->tile_idx),
                remaining.end()
            );
        }
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
