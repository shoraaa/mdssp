#include "common.hpp"
#include <random>

// ============================================================================
// Tile Class Implementation
// ============================================================================

Tile::Tile(CellMap cells_) : cells(std::move(cells_)) {}

int Tile::min_x() const {
    if (cells.empty()) return 0;
    int minx = std::numeric_limits<int>::max();
    for (const auto& [coord, _] : cells) {
        minx = std::min(minx, coord.first);
    }
    return minx;
}

int Tile::min_y() const {
    if (cells.empty()) return 0;
    int miny = std::numeric_limits<int>::max();
    for (const auto& [coord, _] : cells) {
        miny = std::min(miny, coord.second);
    }
    return miny;
}

int Tile::max_x() const {
    if (cells.empty()) return -1;
    int maxx = std::numeric_limits<int>::min();
    for (const auto& [coord, _] : cells) {
        maxx = std::max(maxx, coord.first);
    }
    return maxx;
}

int Tile::max_y() const {
    if (cells.empty()) return -1;
    int maxy = std::numeric_limits<int>::min();
    for (const auto& [coord, _] : cells) {
        maxy = std::max(maxy, coord.second);
    }
    return maxy;
}

int Tile::width() const {
    return cells.empty() ? 0 : max_x() - min_x() + 1;
}

int Tile::height() const {
    return cells.empty() ? 0 : max_y() - min_y() + 1;
}

CellMap Tile::translate(int dx, int dy) const {
    CellMap result;
    result.reserve(cells.size());
    for (const auto& [coord, label] : cells) {
        result[{coord.first + dx, coord.second + dy}] = label;
    }
    return result;
}

Tile Tile::normalized() const {
    if (cells.empty()) return Tile();
    
    int minx = min_x();
    int miny = min_y();
    
    CellMap new_cells;
    for (const auto& [coord, label] : cells) {
        new_cells[{coord.first - minx, coord.second - miny}] = label;
    }
    return Tile(std::move(new_cells));
}

// ============================================================================
// Instance Generation
// ============================================================================

std::vector<Tile> tiles_from_binary_matrices(const Matrices& matrices) {
    std::vector<Tile> tiles;
    tiles.reserve(matrices.size());
    
    for (const auto& mat : matrices) {
        CellMap cells;
        for (size_t y = 0; y < mat.size(); ++y) {
            for (size_t x = 0; x < mat[y].size(); ++x) {
                cells[{(int)x, (int)y}] = '0' + mat[y][x];
            }
        }
        tiles.push_back(Tile(cells).normalized());
    }
    
    return tiles;
}

Matrices generate_binary_matrices(int T, int n, int m, double p, unsigned int seed) {
    std::mt19937 rng(seed);
    std::bernoulli_distribution dist(p);
    Matrices matrices;
    matrices.reserve(T);
    
    for (int t = 0; t < T; ++t) {
        Matrix mat(n, std::vector<int>(m));
        for (int i = 0; i < n; ++i) {
            for (int j = 0; j < m; ++j) {
                mat[i][j] = dist(rng) ? 1 : 0;
            }
        }
        matrices.push_back(std::move(mat));
    }
    
    return matrices;
}

std::vector<Tile> generate_instance(int T, int n, int m, double p, unsigned int seed) {
    auto matrices = generate_binary_matrices(T, n, m, p, seed);
    return tiles_from_binary_matrices(matrices);
}
