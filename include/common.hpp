#ifndef MDSSP_COMMON_HPP
#define MDSSP_COMMON_HPP

#include <vector>
#include <unordered_map>
#include <utility>
#include <string>
#include <limits>
#include <algorithm>

// ============================================================================
// Type Definitions
// ============================================================================

using Coord = std::pair<int, int>;
using Label = char;
using CellMap = std::unordered_map<Coord, Label>;
using Matrix = std::vector<std::vector<int>>;
using Matrices = std::vector<Matrix>;

// ============================================================================
// Objective Function Type
// ============================================================================

enum class ObjectiveType {
    BOUNDING_SQUARE,  // Minimize max(width, height) - original objective
    RECTANGLE_AREA    // Minimize width * height - area objective
};

// Hash function for Coord (pair<int,int>)
namespace std {
    template <>
    struct hash<Coord> {
        size_t operator()(const Coord& c) const {
            return ((size_t)c.first << 32) | ((size_t)c.second & 0xFFFFFFFF);
        }
    };
}

// ============================================================================
// Tile Class
// ============================================================================

class Tile {
public:
    CellMap cells;
    
    Tile() = default;
    explicit Tile(CellMap cells_);
    
    int min_x() const;
    int min_y() const;
    int max_x() const;
    int max_y() const;
    int width() const;
    int height() const;
    
    CellMap translate(int dx, int dy) const;
    Tile normalized() const;
};

// ============================================================================
// Instance Generation
// ============================================================================

std::vector<Tile> tiles_from_binary_matrices(const Matrices& matrices);
Matrices generate_binary_matrices(int T, int n, int m, double p, unsigned int seed);
Matrices generate_matrices(int T, int n, int m, int alphabet_size, unsigned int seed);
std::vector<Tile> generate_instance(int T, int n, int m, double p, unsigned int seed);
std::vector<Tile> generate_instance(int T, int n, int m, int alphabet_size, unsigned int seed);

#endif // MDSSP_COMMON_HPP
