# Makefile for Modular MDSSP Solver

CXX = g++
CXXFLAGS = -std=c++17 -O3 -march=native -Wall -Wextra
INCLUDES = -Iinclude
LDFLAGS =
SRC_DIR = src
OBJ_DIR = obj

# Optional CPLEX support
ifdef USE_CPLEX
    ifndef CPLEX_ROOT
        CPLEX_ROOT = /workspace/ttdat/cplex
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
else
    CPLEX_OBJ =
endif

# Object files
ALL_OBJS = $(OBJ_DIR)/common.o $(OBJ_DIR)/greedy.o $(OBJ_DIR)/genetic.o $(OBJ_DIR)/verifier.o $(CPLEX_OBJ)

.PHONY: all clean run test demo help

all: mdssp

mdssp: mdssp.cpp $(ALL_OBJS)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o $@ $^ $(LDFLAGS)

$(OBJ_DIR)/common.o: $(SRC_DIR)/common.cpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/greedy.o: $(SRC_DIR)/greedy.cpp include/greedy.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/genetic.o: $(SRC_DIR)/genetic.cpp include/genetic.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

$(OBJ_DIR)/verifier.o: $(SRC_DIR)/verifier.cpp include/verifier.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@

ifdef USE_CPLEX
$(OBJ_DIR)/cplex.o: $(SRC_DIR)/cplex.cpp include/cplex.hpp include/common.hpp
	@mkdir -p $(OBJ_DIR)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -c $< -o $@
endif

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
	@echo "  make USE_CPLEX=1"
	@echo "  make USE_CPLEX=1 CPLEX_ROOT=/path/to/cplex"
