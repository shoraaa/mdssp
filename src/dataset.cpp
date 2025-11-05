#include "dataset.hpp"
#include "json.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>

using json = nlohmann::json;

// Parse dataset using nlohmann JSON library
std::vector<Tile> read_dataset(const std::string& filename) {
    std::ifstream file(filename);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open dataset file: " + filename);
    }
    
    json j;
    try {
        file >> j;
    } catch (const json::exception& e) {
        throw std::runtime_error("JSON parse error: " + std::string(e.what()));
    }
    file.close();
    
    // Validate and extract tiles array
    if (!j.contains("tiles") || !j["tiles"].is_array()) {
        throw std::runtime_error("Invalid dataset format: 'tiles' field not found or not an array");
    }
    
    Matrices matrices;
    for (const auto& tile_json : j["tiles"]) {
        if (!tile_json.is_array()) {
            throw std::runtime_error("Invalid tile format: expected array");
        }
        
        Matrix tile;
        for (const auto& row_json : tile_json) {
            if (!row_json.is_array()) {
                throw std::runtime_error("Invalid row format: expected array");
            }
            
            std::vector<int> row;
            for (const auto& val : row_json) {
                if (!val.is_number_integer()) {
                    throw std::runtime_error("Invalid value format: expected integer");
                }
                row.push_back(val.get<int>());
            }
            
            if (!row.empty()) {
                tile.push_back(row);
            }
        }
        
        if (!tile.empty()) {
            matrices.push_back(tile);
        }
    }
    
    std::cout << "Loaded " << matrices.size() << " tiles from dataset\n";
    
    return tiles_from_binary_matrices(matrices);
}
