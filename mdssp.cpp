/*
 * Unified MDSSP Solver
 * 
 * This is a unified interface for all MDSSP solving algorithms with
 * verification and comparison capabilities.
 * 
 * Compilation:
 *   g++ -std=c++17 -O3 -march=native -Iinclude -o mdssp mdssp.cpp src/*.cpp
 *   
 * Usage:
 *   ./mdssp --algorithm greedy --T 10 --n 3 --m 3 --seed 42
 *   ./mdssp --algorithm all --T 10 --n 3 --m 3 --seed 42 --compare
 *   ./mdssp --verify --algorithm greedy --T 10 --n 3 --m 3 --seed 42
 */

#include "cxxopts/cxxopts.hpp"
#include "common.hpp"
#include "greedy.hpp"
#include "genetic.hpp"
#include "cplex.hpp"
#include "verifier.hpp"
#include "dataset.hpp"
#include "json.hpp"
#include <iostream>
#include <iomanip>
#include <fstream>
#include <chrono>
#include <string>
#include <vector>

using json = nlohmann::json;

// ============================================================================
// Result Display
// ============================================================================

struct UnifiedResult {
    int best_obj;
    int bbox_width;
    int bbox_height;
    int bbox_area;
    double wall_time_sec;
    std::vector<std::vector<int>> placements;
    std::string status;
    
    UnifiedResult() : best_obj(0), bbox_width(0), bbox_height(0), 
                      bbox_area(0), wall_time_sec(0.0), status("success") {}
};

void print_result(const std::string& algorithm, const UnifiedResult& result) {
    std::cout << "\n" << std::string(70, '=') << "\n";
    std::cout << algorithm << " Algorithm Results\n";
    std::cout << std::string(70, '=') << "\n";
    
    if (result.status != "success" && result.status != "optimal") {
        std::cout << "Status:            " << result.status << "\n";
        std::cout << std::string(70, '=') << "\n";
        return;
    }
    
    std::cout << "Objective (L):     " << result.best_obj << "\n";
    std::cout << "Bounding Box:      " << result.bbox_width << " × " << result.bbox_height << "\n";
    std::cout << "Area:              " << result.bbox_area << "\n";
    std::cout << "Runtime:           " << std::fixed << std::setprecision(6) 
              << result.wall_time_sec << " seconds\n";
    std::cout << "Placements:        " << result.placements.size() << " tiles\n";
    std::cout << std::string(70, '=') << "\n";
}

void print_verification(const VerificationResult& vr) {
    std::cout << "\n" << std::string(70, '=') << "\n";
    std::cout << "Solution Verification\n";
    std::cout << std::string(70, '=') << "\n";
    std::cout << "Status:            " << (vr.is_valid ? "✓ VALID" : "✗ INVALID") << "\n";
    std::cout << "Message:           " << vr.error_message << "\n";
    std::cout << "Tiles Total:       " << vr.num_tiles << "\n";
    std::cout << "Tiles Placed:      " << vr.num_placed << "\n";
    
    if (vr.is_valid) {
        std::cout << "Verified Objective: " << vr.best_obj << "\n";
        std::cout << "Verified BBox:      " << vr.bbox_width << " × " << vr.bbox_height << "\n";
        std::cout << "Verified Area:      " << vr.bbox_area << "\n";
    }
    std::cout << std::string(70, '=') << "\n";
}

void print_comparison_header() {
    std::cout << "\n" << std::string(90, '=') << "\n";
    std::cout << "Algorithm Comparison\n";
    std::cout << std::string(90, '=') << "\n";
    std::cout << std::setw(15) << std::left << "Algorithm"
              << std::setw(12) << "Objective"
              << std::setw(18) << "BBox (W×H)"
              << std::setw(12) << "Area"
              << std::setw(15) << "Time (s)"
              << std::setw(10) << "Valid"
              << "\n";
    std::cout << std::string(90, '-') << "\n";
}

void print_comparison_row(const std::string& algo, const UnifiedResult& result, bool valid) {
    std::cout << std::setw(15) << std::left << algo
              << std::setw(12) << result.best_obj
              << std::setw(18) << (std::to_string(result.bbox_width) + "×" + 
                                   std::to_string(result.bbox_height))
              << std::setw(12) << result.bbox_area
              << std::setw(15) << std::fixed << std::setprecision(6) << result.wall_time_sec
              << std::setw(10) << (valid ? "✓" : "✗")
              << "\n";
}

// ============================================================================
// Main Function
// ============================================================================

int main(int argc, char* argv[]) {
    try {
        cxxopts::Options options("mdssp", "2D Shortest Superarray Problem Solver");
        
        options.add_options()
            ("a,algorithm", "Algorithm to use: greedy, genetic, cplex, all", 
             cxxopts::value<std::string>()->default_value("greedy"))
            ("d,dataset", "Dataset file (JSON format)", 
             cxxopts::value<std::string>()->default_value(""))
            ("T,tiles", "Number of tiles", 
             cxxopts::value<int>()->default_value("10"))
            ("n,height", "Tile height", 
             cxxopts::value<int>()->default_value("3"))
            ("m,width", "Tile width", 
             cxxopts::value<int>()->default_value("3"))
            ("s,seed", "Random seed", 
             cxxopts::value<int>()->default_value("42"))
            ("p,probability", "Probability for binary generation", 
             cxxopts::value<double>()->default_value("0.5"))
            ("pop-size", "Genetic algorithm population size",
             cxxopts::value<int>()->default_value("10"))
            ("generations", "Genetic algorithm generations",
             cxxopts::value<int>()->default_value("20"))
            ("time-limit", "CPLEX time limit in seconds",
             cxxopts::value<int>()->default_value("60"))
            ("verify", "Verify the solution", 
             cxxopts::value<bool>()->default_value("false"))
            ("compare", "Compare all available algorithms", 
             cxxopts::value<bool>()->default_value("false"))
            ("verbose", "Verbose output", 
             cxxopts::value<bool>()->default_value("false"))
            ("render", "Render the solution canvas", 
             cxxopts::value<bool>()->default_value("false"))
            ("o,output", "Output solution to file (JSON format)", 
             cxxopts::value<std::string>()->default_value(""))
            ("h,help", "Print usage");
        
        auto result = options.parse(argc, argv);
        
        if (result.count("help")) {
            std::cout << options.help() << "\n";
            std::cout << "\nExamples:\n";
            std::cout << "  ./mdssp -a greedy -T 10 -n 3 -m 3\n";
            std::cout << "  ./mdssp -a greedy -T 10 -n 3 -m 3 --verify\n";
            std::cout << "  ./mdssp -a genetic -T 10 -n 3 -m 3 --pop-size 20 --generations 50\n";
            std::cout << "  ./mdssp -a all -T 10 -n 3 -m 3 --compare\n";
            std::cout << "  ./mdssp -a greedy -T 5 -n 2 -m 2 --render\n";
            std::cout << "  ./mdssp -a cplex --dataset dataset.json\n";
            std::cout << "  ./mdssp -a greedy --dataset dataset.json --output solution.json\n";
            return 0;
        }
        
        // Parse options
        std::string algorithm = result["algorithm"].as<std::string>();
        std::string dataset_file = result["dataset"].as<std::string>();
        std::string output_file = result["output"].as<std::string>();
        int T = result["tiles"].as<int>();
        int n = result["height"].as<int>();
        int m = result["width"].as<int>();
        int seed = result["seed"].as<int>();
        double p = result["probability"].as<double>();
        int pop_size = result["pop-size"].as<int>();
        int generations = result["generations"].as<int>();
        int time_limit = result["time-limit"].as<int>();
        bool verify = result["verify"].as<bool>();
        bool compare = result["compare"].as<bool>();
        bool verbose = result["verbose"].as<bool>();
        bool render = result["render"].as<bool>();
        
        // Validate parameters
        if (!dataset_file.empty()) {
            // Using dataset file - skip other validations
        } else if (T <= 0 || n <= 0 || m <= 0) {
            std::cerr << "Error: T, n, and m must be positive integers\n";
            return 1;
        }
        
        if (p < 0.0 || p > 1.0) {
            std::cerr << "Error: probability must be between 0.0 and 1.0\n";
            return 1;
        }
        
        // Print configuration
        std::cout << "MDSSP Solver Configuration\n";
        std::cout << std::string(70, '=') << "\n";
        if (!dataset_file.empty()) {
            std::cout << "Dataset file:      " << dataset_file << "\n";
        } else {
            std::cout << "Instance:          T=" << T << ", n=" << n << ", m=" << m << "\n";
            std::cout << "Seed:              " << seed << "\n";
            std::cout << "Probability:       " << p << "\n";
        }
        std::cout << "Algorithm:         " << algorithm << "\n";
        std::cout << std::string(70, '=') << "\n";
        
        // Generate or load instance
        std::vector<Tile> tiles;
        if (!dataset_file.empty()) {
            if (verbose) {
                std::cout << "\nLoading instance from dataset...\n";
            }
            tiles = read_dataset(dataset_file);
        } else {
            if (verbose) {
                std::cout << "\nGenerating instance...\n";
            }
            tiles = generate_instance(T, n, m, p, seed);
        }
        
        if (verbose) {
            std::cout << "Generated " << tiles.size() << " tiles\n";
        }
        
        // Run algorithm(s)
        std::vector<std::pair<std::string, UnifiedResult>> results;
        
        if (algorithm == "greedy" || algorithm == "all") {
            if (verbose) std::cout << "\nRunning Greedy algorithm...\n";
            auto greedy_result = solve_greedy(tiles);
            
            UnifiedResult unified;
            unified.best_obj = greedy_result.best_obj;
            unified.bbox_width = greedy_result.bbox_width;
            unified.bbox_height = greedy_result.bbox_height;
            unified.bbox_area = greedy_result.bbox_area;
            unified.wall_time_sec = greedy_result.wall_time_sec;
            unified.placements = greedy_result.placements;
            unified.status = "success";
            
            results.push_back({"Greedy", unified});
            
            if (!compare) {
                print_result("Greedy", unified);
                
                if (verify) {
                    std::vector<std::tuple<int, int, int>> placements;
                    for (const auto& p : greedy_result.placements) {
                        placements.push_back({p[0], p[1], p[2]});
                    }
                    SolutionVerifier verifier(tiles);
                    auto vr = verifier.verify(placements);
                    print_verification(vr);
                    
                    if (render && vr.is_valid) {
                        std::cout << "\nSolution Canvas:\n";
                        std::cout << verifier.render_solution(placements) << "\n";
                    }
                }
            }
        }
        
        if (algorithm == "genetic" || algorithm == "all") {
            if (verbose) std::cout << "\nRunning Genetic algorithm...\n";
            auto genetic_result = solve_genetic(tiles, pop_size, generations);
            
            UnifiedResult unified;
            unified.best_obj = genetic_result.best_obj;
            unified.bbox_width = genetic_result.bbox_width;
            unified.bbox_height = genetic_result.bbox_height;
            unified.bbox_area = genetic_result.bbox_area;
            unified.wall_time_sec = genetic_result.wall_time_sec;
            unified.placements = genetic_result.placements;
            unified.status = "success";
            
            results.push_back({"Genetic", unified});
            
            if (!compare) {
                print_result("Genetic", unified);
                
                if (verify) {
                    std::vector<std::tuple<int, int, int>> placements;
                    for (const auto& p : genetic_result.placements) {
                        placements.push_back({p[0], p[1], p[2]});
                    }
                    SolutionVerifier verifier(tiles);
                    auto vr = verifier.verify(placements);
                    print_verification(vr);
                    
                    if (render && vr.is_valid) {
                        std::cout << "\nSolution Canvas:\n";
                        std::cout << verifier.render_solution(placements) << "\n";
                    }
                }
            }
        }
        
        if (algorithm == "cplex" || algorithm == "all") {
            if (verbose) std::cout << "\nRunning CPLEX algorithm...\n";
            
            auto matrices = generate_binary_matrices(T, n, m, p, seed);
            auto cplex_result = solve_cplex(matrices, time_limit);
            
            UnifiedResult unified;
            if (cplex_result.status == "CPLEX not available") {
                unified.status = "CPLEX not available - compile with -DUSE_CPLEX";
                if (!compare) {
                    print_result("CPLEX", unified);
                }
            } else {
                unified.best_obj = cplex_result.best_obj;
                unified.bbox_width = cplex_result.bbox_width;
                unified.bbox_height = cplex_result.bbox_height;
                unified.bbox_area = cplex_result.bbox_area;
                unified.wall_time_sec = cplex_result.wall_time_sec;
                unified.status = cplex_result.status;
                
                for (const auto& [idx, x, y] : cplex_result.placements) {
                    unified.placements.push_back({idx, x, y});
                }
                
                results.push_back({"CPLEX", unified});
                
                if (!compare) {
                    print_result("CPLEX", unified);
                    
                    if (verify && !cplex_result.placements.empty()) {
                        SolutionVerifier verifier(tiles);
                        auto vr = verifier.verify(cplex_result.placements);
                        print_verification(vr);
                        
                        if (render && vr.is_valid) {
                            std::cout << "\nSolution Canvas:\n";
                            std::cout << verifier.render_solution(cplex_result.placements) << "\n";
                        }
                    }
                }
            }
        }
        
        // Comparison mode
        if (compare && !results.empty()) {
            print_comparison_header();
            
            for (const auto& [algo_name, algo_result] : results) {
                if (algo_result.status != "success" && algo_result.status != "optimal") {
                    // Algorithm not available
                    std::cout << std::setw(15) << std::left << algo_name
                              << "Not available" << "\n";
                    continue;
                }
                
                // Verify each result
                std::vector<std::tuple<int, int, int>> placements;
                for (const auto& p : algo_result.placements) {
                    placements.push_back({p[0], p[1], p[2]});
                }
                SolutionVerifier verifier(tiles);
                auto vr = verifier.verify(placements);
                
                print_comparison_row(algo_name, algo_result, vr.is_valid);
            }
            
            std::cout << std::string(90, '=') << "\n";
            
            // Find best among available results
            int best_obj = std::numeric_limits<int>::max();
            std::string best_algo;
            double best_time = std::numeric_limits<double>::max();
            std::string fastest_algo;
            
            for (const auto& [algo_name, algo_result] : results) {
                if (algo_result.status != "success" && algo_result.status != "optimal") {
                    continue;
                }
                
                if (algo_result.best_obj < best_obj) {
                    best_obj = algo_result.best_obj;
                    best_algo = algo_name;
                }
                if (algo_result.wall_time_sec < best_time) {
                    best_time = algo_result.wall_time_sec;
                    fastest_algo = algo_name;
                }
            }
            
            if (!best_algo.empty()) {
                std::cout << "\nBest Solution:     " << best_algo << " (L=" << best_obj << ")\n";
                std::cout << "Fastest:           " << fastest_algo << " (" << std::fixed 
                          << std::setprecision(6) << best_time << "s)\n";
            }
        }
        
        // Output solution to file if requested
        if (!output_file.empty() && !results.empty()) {
            std::ofstream out(output_file);
            if (!out.is_open()) {
                std::cerr << "Error: Cannot open output file: " << output_file << "\n";
                return 1;
            }
            
            json output_json;
            json results_array = json::array();
            
            for (const auto& [algo_name, algo_result] : results) {
                json result_obj;
                result_obj["algorithm"] = algo_name;
                result_obj["status"] = algo_result.status;
                
                if (algo_result.status == "success" || algo_result.status == "optimal") {
                    result_obj["objective"] = algo_result.best_obj;
                    result_obj["bbox_width"] = algo_result.bbox_width;
                    result_obj["bbox_height"] = algo_result.bbox_height;
                    result_obj["bbox_area"] = algo_result.bbox_area;
                    result_obj["runtime_seconds"] = algo_result.wall_time_sec;
                    result_obj["num_tiles_placed"] = algo_result.placements.size();
                    
                    json placements_array = json::array();
                    for (const auto& p : algo_result.placements) {
                        placements_array.push_back({
                            {"tile_id", p[0]},
                            {"x", p[1]},
                            {"y", p[2]}
                        });
                    }
                    result_obj["placements"] = placements_array;
                    
                    // Construct and output the canvas
                    std::vector<std::tuple<int, int, int>> placements;
                    for (const auto& p : algo_result.placements) {
                        placements.push_back({p[0], p[1], p[2]});
                    }
                    SolutionVerifier verifier(tiles);
                    auto vr = verifier.verify(placements);
                    
                    if (vr.is_valid) {
                        // Get canvas as string (nlohmann::json handles escaping automatically)
                        std::string canvas_str = verifier.render_solution(placements);
                        result_obj["canvas"] = canvas_str;
                        result_obj["verified"] = true;
                    } else {
                        result_obj["canvas"] = nullptr;
                        result_obj["verified"] = false;
                        result_obj["verification_error"] = vr.error_message;
                    }
                } else {
                    result_obj["error"] = algo_result.status;
                }
                
                results_array.push_back(result_obj);
            }
            
            output_json["results"] = results_array;
            
            // Write JSON with pretty formatting (2-space indent)
            out << output_json.dump(2) << "\n";
            
            out.close();
            std::cout << "\nSolution written to: " << output_file << "\n";
        }
        
        return 0;
        
    } catch (const cxxopts::OptionException& e) {
        std::cerr << "Error parsing options: " << e.what() << "\n";
        return 1;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }
}
