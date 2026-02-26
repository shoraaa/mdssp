# The 2D Shortest Superstring Problem (2D-SSP)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![C++17](https://img.shields.io/badge/C++-17-blue.svg)](#)
<!-- [![Paper](https://img.shields.io/badge/Paper-PDF-red.svg)](#) Add link to arXiv or published paper here -->

This repository contains the official implementation of the algorithms and experiments from the paper: **"The 2D Shortest Superstring Problem"** (Dat Thanh Tran, Khai Quang Tran, Van Khu Vu, Yining Ma, Hoang Ta). 

## 📖 Overview

The **Two-Dimensional Shortest Superstring Problem (2D-SSP)** is a generalization of the classical 1D Shortest Superstring Problem. Given a set of rectangular 2D strings (symbol arrays), the goal is to arrange them on an integer plane with **symbol-consistent overlaps** to minimize the bounding-box cost. 

Unlike standard 2D bin packing, 2D-SSP allows (and encourages) pieces to overlap as long as their overlapping symbols match. This creates a hybrid optimization challenge combining aspects of *stringology* (overlap exploitation) and *bin packing* (spatial arrangement).

We study two bounding-box objectives:
1. **Area** ($W \times H$) - The natural 2D analogue to 1D string length.
2. **Square** ($\max\{W, H\}$) - Minimizing the maximum side length for balanced layouts.

## ✨ Key Contributions

* **Complexity Proofs:** We prove that 2D-SSP is NP-hard for both objectives and APX-hard for the area objective via L-reduction from 1D-SSP.
* **Compaction Theorem:** We prove that optimal placements can always be made 4-connected without increasing the bounding-box cost.
* **Bounded-Offset Tree Representation:** We reduce the problem from an infinite coordinate search to a finite search over spanning trees with bounded edge labels.
* **Novel Algorithms:** A Tree-Based Genetic Algorithm (T-GA/ST-GA) with a locality-preserving crossover operator that recombines subtrees to preserve spatially coherent clusters.

---

## 📊 Experimental Highlights

Our experimental suite compares our novel Tree-based Genetic Algorithms (**T-GA** and **ST-GA**) against exact Mixed-Integer Programming (**CPLEX**) and classical greedy baselines adapted for 2D (**M-Greedy**).

* **Near-Optimal Performance:** On small, genuinely 2D instances ($N \le 10$) where CPLEX can find the provably global optimum, ST-GA achieves an optimality gap of **$\le 2.6\%$** in a fraction of a second.
* **Massive Improvements over Greedy:** ST-GA outperforms the 1D-adapted Merge-Greedy baseline by **6% to 12%** on Area objectives, and reduces the cost by **over 50%** on certain configurations for the Square objective.
* **Scalability:** Scales up to $N=100$ strings in minutes. In-depth dynamics analysis shows that **95% - 97.5%** of string placements are successfully inherited directly from parents during crossover, proving the efficiency of our subtree recombination.

---

## 🛠️ Repository Structure

The core algorithms are implemented in a highly optimized compiled binary (`./mdssp`), while the systematic benchmarks are driven by a robust Python orchestrator.

```text
.
├── src/                          # C++ source code for the core algorithms
├── systematic_experiments.py     # Main Python experiment driver (reproduces tables)
├── experiments/                  # Auto-generated output directory for JSON/CSV results
├── README.md
└── requirements.txt
```

### Algorithm Mapping
When running the binary or analyzing the outputs, the code terminology maps to the paper as follows:
* `genetic_stochastic` ➔ **ST-GA** (Stochastic Tree-Based GA)
* `genetic_greedy` ➔ **T-GA** (Deterministic Tree-Based GA)
* `stochastic_greedy` ➔ **ST-Greedy** (Stochastic Tree-Growing Greedy)
* `greedy` ➔ **T-Greedy** (Deterministic Tree-Growing Greedy)
* `cplex` ➔ **CPLEX** (Exact ILP Baseline)
* `merge_greedy` ➔ **M-Greedy** (1D-Adapted Baseline)

---

## 🚀 Getting Started

### Prerequisites
* A C++17 compatible compiler (e.g., GCC, Clang) and CMake to build the `./mdssp` core binary.
* Python 3.8+ (for the experiment driver).
* [IBM ILOG CPLEX](https://www.ibm.com/analytics/cplex-optimizer) (Optional: Only required if you want to run the exact MIP solver baseline for small instances).

### 1. Build the Core Binary
*(Ensure your CMake and C++ compiler are set up, then compile the project to generate the `./mdssp` executable in the root directory).*
```bash
# Example build steps
mkdir build && cd build
cmake ..
make
mv mdssp ..
cd ..
```

### 2. Running Systematic Experiments
The paper's experiments are divided into three scales: `small` ($T \in \{6,8,10\}$), `medium` ($T \in \{20,30,50\}$), and `large` ($T \in \{60,80,100\}$). 

We provide `systematic_experiments.py` to systematically run these configurations across multiple random seeds, automatically compiling the results into `all_results.csv` and `summary_statistics.json`.

**Preview what will be run (Dry Run):**
```bash
python systematic_experiments.py --dry-run
```

**Run the Small scale instances with the Area objective:**
```bash
python systematic_experiments.py --scales small --objective-type area
```

**Run Medium and Large instances with the Square objective:**
```bash
python systematic_experiments.py --scales medium large --objective-type square
```

### 🔁 Resuming Interrupted Runs
The experiment script features built-in checkpointing. It saves `experiment_metadata.json` and marks individual run completions. If your execution is interrupted, simply re-run the exact same command. The script will automatically skip previously completed instances and resume where it left off.

If you want to force a fresh run and ignore previous progress, use the `--no-resume` flag:
```bash
python systematic_experiments.py --scales all --no-resume
```

## 📜 Citation

If you find this code or our theoretical framework useful in your research, please consider citing our paper:

```bibtex
@article{tran20262dssp,
  title={The 2D Shortest Superstring Problem},
  author={Tran, Dat Thanh and Tran, Khai Quang and Vu, Van Khu and Ma, Yining and Ta, Hoang},
  journal={Computers \& Operations Research},
  year={2026}
}
```

## ✉️ Contact
For questions regarding the paper or the code, please open an issue or contact the corresponding author at[dat.tt3@vinuni.edu.vn](mailto:dat.tt3@vinuni.edu.vn).