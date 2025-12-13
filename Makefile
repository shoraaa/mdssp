# Makefile for Modular MDSSP Solver

CXX = g++
CXXFLAGS = -std=c++17 -O3 -march=native -Wall -Wextra -fopenmp
INCLUDES = -Iinclude
LDFLAGS = -fopenmp
SRC_DIR = src
OBJ_DIR = obj

# Enable parallel compilation by default
MAKEFLAGS += -j$(shell nproc 2>/dev/null || echo 4)

# Try to use ccache if available for faster recompilation
CCACHE := $(shell command -v ccache 2> /dev/null)
ifdef CCACHE
    CXX := ccache $(CXX)
endif


ifndef CPLEX_ROOT
	CPLEX_ROOT = /opt/ibm/ILOG/CPLEX_Studio2211
# 	/workspace/ttdat/cplex
endif

UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Linux)
	CPLEX_ARCH = x86-64_linux
else
	CPLEX_ARCH = x86-64_osx
endif

CPLEX_INCLUDE = -I$(CPLEX_ROOT)/cplex/include -I$(CPLEX_ROOT)/concert/include
CPLEX_LIBS = -L$(CPLEX_ROOT)/cplex/lib/$(CPLEX_ARCH)/static_pic -L$(CPLEX_ROOT)/concert/lib/$(CPLEX_ARCH)/static_pic
CPLEX_LDFLAGS = -lconcert -lilocplex -lcplex -lm -lpthread -ldl

CXXFLAGS += -DUSE_CPLEX -DIL_STD $(CPLEX_INCLUDE)
LDFLAGS += $(CPLEX_LIBS) $(CPLEX_LDFLAGS)
CPLEX_OBJ = $(OBJ_DIR)/cplex.o


# Object files
ALL_OBJS = $(OBJ_DIR)/common.o $(OBJ_DIR)/greedy.o $(OBJ_DIR)/genetic.o $(OBJ_DIR)/genetic_tree.o $(OBJ_DIR)/branch_and_bound.o $(OBJ_DIR)/verifier.o $(OBJ_DIR)/dataset.o $(CPLEX_OBJ)
MAIN_OBJ = $(OBJ_DIR)/mdssp.o

.PHONY: all clean run test demo help

all: mdssp

mdssp: $(MAIN_OBJ) $(ALL_OBJS)
	@echo "Linking mdssp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -o $@ $^ $(LDFLAGS)

$(MAIN_OBJ): mdssp.cpp include/common.hpp include/greedy.hpp include/genetic.hpp include/branch_and_bound.hpp include/cplex.hpp include/verifier.hpp include/dataset.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling mdssp.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/common.o: $(SRC_DIR)/common.cpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling common.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/greedy.o: $(SRC_DIR)/greedy.cpp include/greedy.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling greedy.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/genetic.o: $(SRC_DIR)/genetic.cpp include/genetic.hpp include/common.hpp include/greedy.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling genetic.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/genetic_tree.o: $(SRC_DIR)/genetic_tree.cpp include/genetic.hpp include/common.hpp include/greedy.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling genetic_tree.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/branch_and_bound.o: $(SRC_DIR)/branch_and_bound.cpp include/branch_and_bound.hpp include/common.hpp include/greedy.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling branch_and_bound.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/verifier.o: $(SRC_DIR)/verifier.cpp include/verifier.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling verifier.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/dataset.o: $(SRC_DIR)/dataset.cpp include/dataset.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling dataset.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/cplex.o: $(SRC_DIR)/cplex.cpp include/cplex.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	@echo "Compiling cplex.cpp..."
	@$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

run: mdssp
	./mdssp -a greedy -T 10 -n 3 -m 3

demo: mdssp
	@echo "=== Greedy Algorithm ==="
	./mdssp -a greedy -T 8 -n 3 -m 3 -s 42
	@echo ""
	@echo "=== Genetic Algorithm ==="
	./mdssp -a genetic -T 8 -n 3 -m 3 -s 42
	@echo ""
	@echo "=== Compare All ==="
	./mdssp -a all -T 10 -n 3 -m 3 -s 42 --compare

test: mdssp
	@echo "Running tests..."
	./mdssp -a greedy -T 5 -n 2 -m 2 -s 42 --verify
	./mdssp -a genetic -T 8 -n 3 -m 3 -s 42 --verify
	@echo "✓ Tests passed!"

clean:
	rm -f mdssp $(OBJ_DIR)/*.o
	rm -rf $(OBJ_DIR)

help:
	@echo "MDSSP Solver Makefile"
	@echo "====================="
	@echo ""
	@echo "Targets:"
	@echo "  make         - Build mdssp"
	@echo "  make run     - Run default"
	@echo "  make demo    - Run demos"
	@echo "  make test    - Run tests"
	@echo "  make clean   - Clean build"
	@echo ""
	@echo "CPLEX Support:"
