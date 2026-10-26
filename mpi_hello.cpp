#include <iostream>
#include <mpi.h>
int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank = 0, size = 0, sum = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    const int value = rank + 1;
    MPI_Allreduce(&value, &sum, 1, MPI_INT, MPI_SUM, MPI_COMM_WORLD);
    std::cout << "rank=" << rank << '/' << size << " sum=" << sum << '\n';
    const int expected = size * (size + 1) / 2;
    MPI_Finalize();
    return sum == expected ? 0 : 1;
}
