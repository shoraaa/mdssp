#ifndef MDSSP_DATASET_HPP
#define MDSSP_DATASET_HPP

#include "common.hpp"
#include <string>

// Read tiles from a dataset file
std::vector<Tile> read_dataset(const std::string& filename);

#endif // MDSSP_DATASET_HPP
