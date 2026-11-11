#ifndef JACOBI_C_TARGET_H
#define JACOBI_C_TARGET_H
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
void c_jacobi_target(double* a, double* b, double* f,
    size_t count, size_t stride, size_t sz,
    int K, int nx, int ny, int klo, int khi, int dim,
    double ax, double ay, double az, double diag, int* ran_on_host,
    double* resident_seconds, double* e2e_seconds);
#ifdef __cplusplus
}
#endif
#endif
