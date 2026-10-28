// Independent pure-MPI wait-placement diagnostic; production source preserved.
// Distributed 2-D Jacobi; build with OpenMP for a hybrid MPI + OpenMP solver.
// MPI calls are made only by the thread that initializes MPI (FUNNELED).
#include <mpi.h>
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef _OPENMP
#include <omp.h>
#endif

struct Parameters {
    int n = 16, max_iters = 100000;
    double tolerance = 1e-12;
    std::string exchange = "sendrecv";
};

Parameters parse(int argc, char** argv) {
    Parameters p;
    auto integer = [](const char* s) {
        std::size_t used = 0;
        int value = std::stoi(s, &used);
        if (used != std::string(s).size()) throw std::invalid_argument("Invalid integer");
        return value;
    };
    if (argc > 1) p.n = integer(argv[1]);
    if (argc > 2) p.max_iters = integer(argv[2]);
    if (argc > 3) {
        std::size_t used = 0;
        p.tolerance = std::stod(argv[3], &used);
        if (used != std::string(argv[3]).size()) throw std::invalid_argument("Invalid tolerance");
    }
    if (argc == 6 && std::string(argv[4]) == "--exchange") p.exchange = argv[5];
    else if (argc > 4) throw std::invalid_argument("Expected --exchange sendrecv|immediate|overlap");
    if (p.n < 1 || p.n > 2048 || p.max_iters < 1 || p.max_iters > 10000000 ||
        !std::isfinite(p.tolerance) || p.tolerance < 0 ||
        (p.exchange != "sendrecv" && p.exchange != "immediate" && p.exchange != "overlap"))
        throw std::invalid_argument("Argument outside supported range");
    return p;
}

int main(int argc, char** argv) {
    int provided = MPI_THREAD_SINGLE;
#ifdef _OPENMP
    const int required = MPI_THREAD_FUNNELED;
#else
    const int required = MPI_THREAD_SINGLE;
#endif
    MPI_Init_thread(&argc, &argv, required, &provided);
    int rank = 0, size = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    try {
        Parameters p;
        int invalid = 0;
        std::string error;
        try {
            p = parse(argc, argv);
            if (size > p.n) throw std::invalid_argument("MPI process count must be <= n");
            if (provided < required) throw std::runtime_error("Insufficient MPI thread support");
        } catch (const std::exception& e) { invalid = 1; error = e.what(); }
        int any_invalid = 0;
        MPI_Allreduce(&invalid, &any_invalid, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
        if (any_invalid) {
            if (rank == 0) std::cerr << (error.empty() ? "Invalid input on another rank" : error)
                << "\nUsage: jacobi_mpi [n=16] [max_iters=100000] [tolerance=1e-12]"
                << " [--exchange sendrecv|immediate|overlap]\n";
            MPI_Finalize();
            return 1;
        }
        int threads = 1;
#ifdef _OPENMP
        omp_set_dynamic(0);
        #pragma omp parallel
        {
            #pragma omp single
            threads = omp_get_num_threads();
        }
#endif
        int min_threads = 0, max_threads = 0;
        MPI_Allreduce(&threads, &min_threads, 1, MPI_INT, MPI_MIN, MPI_COMM_WORLD);
        MPI_Allreduce(&threads, &max_threads, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);
        if (min_threads != max_threads) throw std::runtime_error("Thread counts differ across ranks");
        MPI_Comm shared;
        MPI_Comm_split_type(MPI_COMM_WORLD, MPI_COMM_TYPE_SHARED, rank, MPI_INFO_NULL, &shared);
        int local_rank = 0, nodes = 0;
        MPI_Comm_rank(shared, &local_rank);
        const int leader = local_rank == 0 ? 1 : 0;
        MPI_Allreduce(&leader, &nodes, 1, MPI_INT, MPI_SUM, MPI_COMM_WORLD);
        MPI_Comm_free(&shared);

        const int n = p.n, width = n + 2;
        const int rows = n / size + (rank < n % size ? 1 : 0);
        const int start = 1 + rank * (n / size) + std::min(rank, n % size);
        const int up = rank == 0 ? MPI_PROC_NULL : rank - 1;
        const int down = rank == size - 1 ? MPI_PROC_NULL : rank + 1;
        const double h = 1.0 / (n + 1);
        auto at = [width](int i, int j) { return i * width + j; };
        std::vector<double> old_grid((rows + 2) * width, 0.0), new_grid(old_grid.size(), 0.0);
        for (int i = 0; i < rows + 2; ++i) {
            const int global_i = start + i - 1;
            for (int j = 0; j < width; ++j) {
                if (global_i == 0 || global_i == n + 1 || j == 0 || j == n + 1)
                    old_grid[at(i,j)] = new_grid[at(i,j)] = (global_i + j) * h;
            }
        }
        auto exchange_blocking = [&]() {
            // Distinct send/receive storage; PROC_NULL preserves physical boundaries.
            MPI_Sendrecv(old_grid.data() + width, width, MPI_DOUBLE, up, 0,
                old_grid.data() + (rows + 1) * width, width, MPI_DOUBLE, down, 0,
                MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            MPI_Sendrecv(old_grid.data() + rows * width, width, MPI_DOUBLE, down, 1,
                old_grid.data(), width, MPI_DOUBLE, up, 1,
                MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        };
        auto update = [&](int first, int last, bool edges_only = false) {
            double delta = 0.0;
            const int count = edges_only ? std::min(rows, 2) : std::max(0, last - first + 1);
#ifdef _OPENMP
            #pragma omp parallel for schedule(static) reduction(max:delta)
#endif
            for (int index = 0; index < count; ++index) {
                const int i = edges_only ? (index == 0 ? 1 : rows) : first + index;
                for (int j = 1; j <= n; ++j) {
                    const double value = 0.25 * (old_grid[at(i-1,j)] + old_grid[at(i+1,j)] +
                        old_grid[at(i,j-1)] + old_grid[at(i,j+1)]);
                    new_grid[at(i,j)] = value;
                    delta = std::max(delta, std::abs(value - old_grid[at(i,j)]));
                }
            }
            return delta;
        };
        const bool wait_immediately = p.exchange == "immediate";
        int iterations = 0;
        double max_update = 0.0;
        bool converged = false;
        MPI_Barrier(MPI_COMM_WORLD);
        const double begin = MPI_Wtime();
        for (int k = 0; k < p.max_iters; ++k) {
            double local_update = 0.0;
            if (p.exchange == "sendrecv") {
                exchange_blocking();
                local_update = update(1, rows);
            } else {
                MPI_Request requests[4];
                MPI_Irecv(old_grid.data(), width, MPI_DOUBLE, up, 1, MPI_COMM_WORLD, &requests[0]);
                MPI_Irecv(old_grid.data() + (rows + 1) * width, width, MPI_DOUBLE, down, 0,
                    MPI_COMM_WORLD, &requests[1]);
                MPI_Isend(old_grid.data() + width, width, MPI_DOUBLE, up, 0, MPI_COMM_WORLD, &requests[2]);
                MPI_Isend(old_grid.data() + rows * width, width, MPI_DOUBLE, down, 1,
                    MPI_COMM_WORLD, &requests[3]);
                // Both nonblocking modes have identical interior/edge work and order.
                // Only the position of the single wait changes. No phase instrumentation.
                if (wait_immediately) MPI_Waitall(4, requests, MPI_STATUSES_IGNORE);
                if (rows > 2) local_update = update(2, rows - 1);
                if (!wait_immediately) MPI_Waitall(4, requests, MPI_STATUSES_IGNORE);
                local_update = std::max(local_update, update(1, rows, true));
            }
            old_grid.swap(new_grid);
            iterations = k + 1;
            // Fixed-work runs avoid a stopping reduction on every iteration.
            if (p.tolerance > 0 || iterations == p.max_iters)
                MPI_Allreduce(&local_update, &max_update, 1, MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD);
            if (p.tolerance > 0 && max_update <= p.tolerance) { converged = true; break; }
        }
        const double elapsed = MPI_Wtime() - begin;
        double seconds = 0.0;
        MPI_Reduce(&elapsed, &seconds, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);

        // Halo values belong to the previous iteration after a swap: refresh before residuals.
        exchange_blocking();
        double local_metrics[3] = {0.0, 0.0, 0.0}, metrics[3] = {};
        for (int i = 0; i < rows + 2; ++i) {
            const int global_i = start + i - 1;
            for (int j = 0; j < width; ++j) {
                const double error_value = std::abs(old_grid[at(i,j)] - (global_i + j) * h);
                if (global_i == 0 || global_i == n + 1 || j == 0 || j == n + 1)
                    local_metrics[2] = std::max(local_metrics[2], error_value);
                else if (i >= 1 && i <= rows) {
                    local_metrics[0] = std::max(local_metrics[0], error_value);
                    const double residual = std::abs((4.0 * old_grid[at(i,j)] -
                        old_grid[at(i-1,j)] - old_grid[at(i+1,j)] -
                        old_grid[at(i,j-1)] - old_grid[at(i,j+1)]) / (h*h));
                    local_metrics[1] = std::max(local_metrics[1], residual);
                }
            }
        }
        MPI_Reduce(local_metrics, metrics, 3, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);
        std::vector<double> global;
        if (n <= 8) {
            std::vector<int> counts(size), displacements(size);
            for (int r = 0; r < size; ++r) {
                counts[r] = (n / size + (r < n % size ? 1 : 0)) * width;
                displacements[r] = (1 + r * (n / size) + std::min(r, n % size)) * width;
            }
            if (rank == 0) {
                global.resize(width * width, 0.0);
                for (int j = 0; j < width; ++j) {
                    global[j] = j * h;
                    global[(n + 1) * width + j] = (n + 1 + j) * h;
                }
            }
            MPI_Gatherv(old_grid.data() + width, rows * width, MPI_DOUBLE, global.data(),
                counts.data(), displacements.data(), MPI_DOUBLE, 0, MPI_COMM_WORLD);
        }
        if (rank == 0) {
#ifdef _OPENMP
            const char* mode = "hybrid";
#else
            const char* mode = "mpi";
#endif
            std::cout << std::setprecision(17) << "{\"diagnostic\":\"wait-placement-v1\",\"mode\":\"" << mode
                << "\",\"n\":" << n << ",\"mpi_processes\":" << size
                << ",\"threads\":" << threads << ",\"nodes\":" << nodes
                << ",\"exchange\":\"" << p.exchange << "\",\"iterations\":" << iterations
                << ",\"tolerance\":" << p.tolerance << ",\"status\":\""
                << (p.tolerance == 0 ? "fixed_iterations" : (converged ? "update_tolerance_reached" : "iteration_limit"))
                << "\",\"max_update\":" << max_update << ",\"max_error\":" << metrics[0]
                << ",\"residual_inf\":" << metrics[1] << ",\"boundary_error\":" << metrics[2]
                << ",\"compute_seconds\":" << seconds;
            if (n <= 8) {
                std::cout << ",\"grid\":[";
                for (int i = 0; i < width; ++i) {
                    if (i) std::cout << ',';
                    std::cout << '[';
                    for (int j = 0; j < width; ++j) {
                        if (j) std::cout << ',';
                        std::cout << global[at(i,j)];
                    }
                    std::cout << ']';
                }
                std::cout << ']';
            }
            std::cout << "}\n";
        }
        MPI_Finalize();
        return p.tolerance > 0 && !converged ? 2 : 0;
    } catch (const std::exception& e) {
        std::cerr << "rank " << rank << ": " << e.what() << '\n';
        MPI_Abort(MPI_COMM_WORLD, 1);
        return 1;
    }
}
