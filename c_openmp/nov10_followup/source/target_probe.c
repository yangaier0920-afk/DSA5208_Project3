#include <omp.h>
#include <stdio.h>

int main(void) {
    for (int i = 0; i < 11; ++i) {
        int on_host = 1;
        const double start = omp_get_wtime();
        #pragma omp target map(from:on_host)
        {
            on_host = omp_is_initial_device();
        }
        const double seconds = omp_get_wtime() - start;
        if (on_host) return 2;
        printf("%d,%.17g\n", i, seconds);
    }
    return 0;
}
