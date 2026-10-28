// Diagnostic candidate: iteration-local update maximum; original jacobi.cpp preserved.
// Fixed boundary u(x,y)=x+y; initial interior is zero.
// Build without -fopenmp for serial, with -fopenmp for OpenMP.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _OPENMP
#include <omp.h>
#endif

int main(int argc, char** argv) {
    try {
        if (argc > 4) throw std::invalid_argument("Too many arguments");
        auto integer = [](const char* value) {
            std::size_t used = 0;
            int result = std::stoi(value, &used);
            if (used != std::string(value).size())
                throw std::invalid_argument("Invalid integer");
            return result;
        };
        const int n = argc > 1 ? integer(argv[1]) : 16;
        const int max_iters = argc > 2 ? integer(argv[2]) : 100000;
        std::size_t used = 0;
        const double tolerance = argc > 3 ? std::stod(argv[3], &used) : 1e-12;
        if (argc > 3 && used != std::string(argv[3]).size())
            throw std::invalid_argument("Invalid tolerance");
        if (n < 1 || n > 2048 || max_iters < 1 || max_iters > 10000000 ||
            !std::isfinite(tolerance) || tolerance < 0.0)
            throw std::invalid_argument("Argument outside supported range");

        const int width = n + 2; // n interior points plus two boundaries.
        const double h = 1.0 / (n + 1);
        auto at = [width](int i, int j) { return i * width + j; };
        auto exact = [h](int i, int j) { return (i + j) * h; };
        std::vector<double> old_grid(width * width, 0.0);
        std::vector<double> new_grid(width * width, 0.0);
        for (int i = 0; i < width; ++i) {
            for (int j = 0; j < width; ++j) {
                if (i == 0 || j == 0 || i == width-1 || j == width-1) {
                    old_grid[at(i,j)] = exact(i,j);
                    new_grid[at(i,j)] = exact(i,j);
                }
            }
        }

        int threads = 1;
#ifdef _OPENMP
        // Measure the team actually created, rather than its configured maximum.
        #pragma omp parallel
        {
            #pragma omp single
            threads = omp_get_num_threads();
        }
#endif
        double max_update = 0.0;
        int iterations = 0;
        bool reached_tolerance = false;
        const auto begin = std::chrono::steady_clock::now();
        for (int k = 0; k < max_iters; ++k) {
            double iteration_update = 0.0;
#ifdef _OPENMP
            #pragma omp parallel for schedule(static) reduction(max:iteration_update)
#endif
            for (int i = 1; i <= n; ++i) {
                for (int j = 1; j <= n; ++j) {
                    // Read only the previous iteration: this is Jacobi.
                    const double value = 0.25 * (
                        old_grid[at(i-1,j)] + old_grid[at(i+1,j)] +
                        old_grid[at(i,j-1)] + old_grid[at(i,j+1)]);
                    new_grid[at(i,j)] = value;
                    iteration_update = std::max(iteration_update,
                        std::abs(value - old_grid[at(i,j)]));
                }
            }
            // The OpenMP loop's implicit barrier completes writes before swap.
            old_grid.swap(new_grid);
            max_update = iteration_update;
            iterations = k + 1;
            if (tolerance > 0.0 && max_update <= tolerance) {
                reached_tolerance = true;
                break;
            }
        }
        const double seconds = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - begin).count();

        double max_error = 0.0, residual_inf = 0.0, boundary_error = 0.0;
        for (int i = 0; i < width; ++i) {
            for (int j = 0; j < width; ++j) {
                const double error = std::abs(old_grid[at(i,j)] - exact(i,j));
                if (i == 0 || j == 0 || i == width-1 || j == width-1) {
                    boundary_error = std::max(boundary_error, error);
                } else {
                    max_error = std::max(max_error, error);
                    const double residual = std::abs((
                        4.0 * old_grid[at(i,j)] - old_grid[at(i-1,j)] -
                        old_grid[at(i+1,j)] - old_grid[at(i,j-1)] -
                        old_grid[at(i,j+1)]) / (h*h));
                    residual_inf = std::max(residual_inf, residual);
                }
            }
        }
        const char* mode = "serial";
#ifdef _OPENMP
        mode = "openmp";
#endif
        std::cout << std::setprecision(17)
            << "{\"mode\":\"" << mode << "\",\"n\":" << n
            << ",\"threads\":" << threads << ",\"iterations\":" << iterations
            << ",\"tolerance\":" << tolerance
            << ",\"status\":\"" << (tolerance == 0.0 ? "fixed_iterations" :
                (reached_tolerance ? "update_tolerance_reached" : "iteration_limit"))
            << "\",\"max_update\":" << max_update
            << ",\"max_error\":" << max_error
            << ",\"residual_inf\":" << residual_inf
            << ",\"boundary_error\":" << boundary_error
            << ",\"compute_seconds\":" << seconds;
        if (n <= 8) {
            std::cout << ",\"grid\":[";
            for (int i = 0; i < width; ++i) {
                if (i) std::cout << ',';
                std::cout << '[';
                for (int j = 0; j < width; ++j) {
                    if (j) std::cout << ',';
                    std::cout << old_grid[at(i,j)];
                }
                std::cout << ']';
            }
            std::cout << ']';
        }
        std::cout << "}\n";
        return tolerance > 0.0 && !reached_tolerance ? 2 : 0;
    } catch (const std::exception& error) {
        std::cerr << error.what()
            << "\nUsage: jacobi [interior_n=16] [max_iters=100000] [tolerance=1e-12]"
            << "\nUse tolerance=0 for exactly max_iters iterations.\n";
        return 1;
    }
}
