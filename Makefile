CXX = c++
MPICXX = mpicxx
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra -Wpedantic
OMPFLAGS = -fopenmp
BUILD = build

.PHONY: all check clean
all: $(BUILD)/jacobi_serial $(BUILD)/jacobi_omp $(BUILD)/jacobi_mpi $(BUILD)/jacobi_hybrid

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/jacobi_serial: jacobi.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) $< -o $@

$(BUILD)/jacobi_omp: jacobi.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) $(OMPFLAGS) $< -o $@

$(BUILD)/jacobi_mpi: jacobi_mpi.cpp | $(BUILD)
	$(MPICXX) $(CXXFLAGS) $< -o $@

$(BUILD)/jacobi_hybrid: jacobi_mpi.cpp | $(BUILD)
	$(MPICXX) $(CXXFLAGS) $(OMPFLAGS) $< -o $@

check: all
	python3 verify_small.py $(BUILD)/jacobi_serial $(BUILD)/jacobi_omp
	python3 verify_parallel.py --serial $(BUILD)/jacobi_serial --mpi $(BUILD)/jacobi_mpi --hybrid $(BUILD)/jacobi_hybrid --out-dir results/parallel_check_$$(date +%Y%m%d_%H%M%S)

clean:
	rm -f $(BUILD)/jacobi_serial $(BUILD)/jacobi_omp $(BUILD)/jacobi_mpi $(BUILD)/jacobi_hybrid

# A numerical route, independent of MPI/OpenMP and historical all/check.
.PHONY: numerics
numerics: $(BUILD)/jacobi_numerics

$(BUILD)/jacobi_numerics: jacobi_numerics.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) $< -o $@
