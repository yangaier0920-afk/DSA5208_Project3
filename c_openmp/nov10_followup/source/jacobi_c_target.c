/* Isolated OpenMP target solver: compile as C with nvc -mp=gpu.
 * No C++ headers/lambdas and no combined target/teams directive.
 * This is a candidate workaround, pending NVHPC/Vanda validation. */
#include "jacobi_c_target.h"
#include <omp.h>

/* Host pointer selection happens before this function. The array sections
 * reuse the enclosing data region's mappings by host address, in either role. */
static void jacobi_step(double* src, double* dst, double* f, int* host_flag,
    size_t count, size_t stride, size_t sz,
    int nx, int ny, int klo, int khi, int dim, int verify,
    double ax, double ay, double az, double diag)
{
    #pragma omp target map(alloc:src[0:count],dst[0:count],f[0:count],host_flag[0:1]) \
        firstprivate(nx,ny,klo,khi,stride,sz,dim,verify,ax,ay,az,diag)
    {
        #pragma omp teams
        {
            /* One team primary in the SAME target as the stencil.
             * No separate probe kernel and no write inside the parallel loop. */
            if(verify && omp_get_team_num()==0) host_flag[0]=omp_is_initial_device();
            #pragma omp distribute parallel for collapse(3)
            for(int i=1;i<=nx;++i) for(int j=1;j<=ny;++j) for(int k=klo;k<=khi;++k) {
                const size_t q=(size_t)i*stride+(size_t)j*sz+k;
                double v=ax*(src[q-stride]+src[q+stride])+ay*(src[q-sz]+src[q+sz]);
                if(dim==3) v+=az*(src[q-1]+src[q+1]);
                dst[q]=(v+f[q])/diag;
            }
        }
    }
}

void c_jacobi_target(double* a, double* b, double* f,
    size_t count, size_t stride, size_t sz,
    int K, int nx, int ny, int klo, int khi, int dim,
    double ax, double ay, double az, double diag, int* ran_on_host,
    double* resident_seconds, double* e2e_seconds)
{
    int host_flag[1]={1};
    const double e2e_start=omp_get_wtime();
    #pragma omp target data map(to:a[0:count],b[0:count],f[0:count]) map(tofrom:host_flag[0:1])
    {
        const double resident_start=omp_get_wtime();
        for(int m=0;m<K;++m) {
            /* No nowait: exactly one completed target per Jacobi iteration. */
            double* src=(m%2==0)?a:b;
            double* dst=(m%2==0)?b:a;
            jacobi_step(src,dst,f,host_flag,count,stride,sz,
                nx,ny,klo,khi,dim,m==0,ax,ay,az,diag);
        }
        *resident_seconds=omp_get_wtime()-resident_start;
        if(K%2==0) {
            #pragma omp target update from(a[0:count])
        } else {
            #pragma omp target update from(b[0:count])
        }
    }
    *e2e_seconds=omp_get_wtime()-e2e_start;
    *ran_on_host=host_flag[0];
}
