#include <iostream>
#include <omp.h>
int main() {
    int threads = 0;
    long long sum = 0;
    #pragma omp parallel reduction(+:sum)
    {
        #pragma omp single
        threads = omp_get_num_threads();
        #pragma omp for
        for (int i = 1; i <= 100; ++i) sum += i;
    }
    std::cout << "threads=" << threads << " sum=" << sum << '\n';
    return sum == 5050 ? 0 : 1;
}
