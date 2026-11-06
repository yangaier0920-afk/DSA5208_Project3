// C's independent fixed-work CPU/OpenMP target solver. See README.md.
#include <omp.h>
#ifdef C_ENABLE_TARGET
#include "jacobi_c_target.h"
#endif
#include <algorithm>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

int positive(const std::string& s) {
    std::size_t n=0; int v=std::stoi(s,&n);
    if(n!=s.size() || v<1 || v>1000000) throw std::invalid_argument("Expected positive integer <=1000000");
    return v;
}
int main(int argc, char** argv) {
 try {
    int dim=3,nx=7,ny=0,nz=0,K=1000,threads=1;
    std::string backend="cpu",grid;
    for(int p=1;p<argc;++p) {
        std::string key=argv[p];
        if(key=="--help") {
            std::cout<<"--backend cpu|gpu --dim 2|3 --nx N [--ny N --nz N] --iterations K --threads T [--grid FILE]\n";
            return 0;
        }
        if(p+1>=argc) throw std::invalid_argument("Missing value for "+key);
        std::string val=argv[++p];
        if(key=="--backend") backend=val;
        else if(key=="--dim") dim=positive(val);
        else if(key=="--nx") nx=positive(val);
        else if(key=="--ny") ny=positive(val);
        else if(key=="--nz") nz=positive(val);
        else if(key=="--iterations") K=positive(val);
        else if(key=="--threads") threads=positive(val);
        else if(key=="--grid") grid=val;
        else throw std::invalid_argument("Unknown option "+key);
    }
    if(dim!=2 && dim!=3) throw std::invalid_argument("Dimension must be 2 or 3");
    if(backend!="cpu" && backend!="gpu") throw std::invalid_argument("Backend must be cpu or gpu");
    if(!ny) ny=nx;
    if(!nz) nz=dim==3?nx:1;
    if(dim==2 && nz!=1) throw std::invalid_argument("2D requires nz=1 (storage has one plane)");
#ifndef C_ENABLE_TARGET
    if(backend=="gpu") throw std::runtime_error("CPU-only build: rebuild with -DC_ENABLE_TARGET and GPU offload compiler flags");
#endif
    const int devices=backend=="gpu"?omp_get_num_devices():0;
    if(backend=="gpu" && devices<1) throw std::runtime_error("No OpenMP target device: GPU run refused");
    omp_set_dynamic(0);
    const std::size_t sx=static_cast<std::size_t>(nx)+2,sy=static_cast<std::size_t>(ny)+2;
    const std::size_t sz=dim==3?static_cast<std::size_t>(nz)+2:1;
    const auto cap=std::vector<double>().max_size();
    if(sx>cap/sy || sx*sy>cap/sz) throw std::length_error("Grid size overflow");
    const std::size_t count=sx*sy*sz,stride=sy*sz;
    const int klo=dim==3?1:0,khi=dim==3?nz:0;
    const double hx=1.0/(nx+1),hy=1.0/(ny+1),hz=dim==3?1.0/(nz+1):1;
    const double ax=1/(hx*hx),ay=1/(hy*hy),az=dim==3?1/(hz*hz):0;
    const double diag=2*(ax+ay+az),pi=std::acos(-1.0),amplitude=(dim==3?14:5)*pi*pi;
    auto index=[=](int i,int j,int k) {return static_cast<std::size_t>(i)*stride+static_cast<std::size_t>(j)*sz+k;};
    auto boundary=[=](int i,int j,int k) {return i==0||i==nx+1||j==0||j==ny+1||(dim==3&&(k==0||k==nz+1));};
    auto linear=[=](int i,int j,int k) {return i*hx+2*j*hy+(dim==3?3*k*hz:0);};
    auto wave=[=](int i,int j,int k) {return std::sin(pi*i*hx)*std::sin(2*pi*j*hy)*(dim==3?std::sin(3*pi*k*hz):1);};
    std::vector<double> av(count,0),bv(count,0),fv(count,0);
    double *a=av.data(),*b=bv.data(),*f=fv.data();
    for(int i=0;i<=nx+1;++i) for(int j=0;j<=ny+1;++j) for(int k=0;k<static_cast<int>(sz);++k) {
        const auto q=index(i,j,k);
        if(boundary(i,j,k)) a[q]=b[q]=linear(i,j,k);
        else f[q]=amplitude*wave(i,j,k);
    }
    auto residual=[&](const double* u) {
        double sum=0;
        for(int i=1;i<=nx;++i) for(int j=1;j<=ny;++j) for(int k=klo;k<=khi;++k) {
            const auto q=index(i,j,k);
            double ah=diag*u[q]-ax*(u[q-stride]+u[q+stride])-ay*(u[q-sz]+u[q+sz]);
            if(dim==3) ah-=az*(u[q-1]+u[q+1]);
            const double r=f[q]-ah; sum+=r*r;
        }
        if(!std::isfinite(sum)) throw std::runtime_error("Nonfinite residual");
        return std::sqrt(sum);
    };
    const double initial=residual(a);
    double cpu_seconds=0,gpu_resident_seconds=0,gpu_e2e_seconds=0;
    int actual_threads=0,ran_on_host=1;
    if(backend=="cpu") {
        const double start=omp_get_wtime();
        // Persistent team. Each omp-for barrier completes the current time step.
        #pragma omp parallel num_threads(threads) shared(actual_threads)
        {
            #pragma omp single
            actual_threads=omp_get_num_threads();
            for(int m=0;m<K;++m) {
                const double* src=(m%2==0)?a:b;
                double* dst=(m%2==0)?b:a;
                #pragma omp for collapse(3) schedule(static)
                for(int i=1;i<=nx;++i) for(int j=1;j<=ny;++j) for(int k=klo;k<=khi;++k) {
                    const std::size_t q=static_cast<std::size_t>(i)*stride+static_cast<std::size_t>(j)*sz+k;
                    double v=ax*(src[q-stride]+src[q+stride])+ay*(src[q-sz]+src[q+sz]);
                    if(dim==3) v+=az*(src[q-1]+src[q+1]);
                    dst[q]=(v+f[q])/diag;
                }
            }
        }
        cpu_seconds=omp_get_wtime()-start;
        if(actual_threads!=threads) throw std::runtime_error("Actual CPU thread count differs from requested count");
    }
#ifdef C_ENABLE_TARGET
    else {
        c_jacobi_target(a,b,f,count,stride,sz,K,nx,ny,klo,khi,dim,
                        ax,ay,az,diag,&ran_on_host,
                        &gpu_resident_seconds,&gpu_e2e_seconds);
        if(ran_on_host) throw std::runtime_error("Stencil executed on host: GPU result refused");
    }
#endif
    const double* result=(K%2==0)?a:b;
    const double final_residual=residual(result);
    const double lambda=4*ax*std::pow(std::sin(pi*hx/2),2)+4*ay*std::pow(std::sin(pi*hy),2)
        +(dim==3?4*az*std::pow(std::sin(3*pi*hz/2),2):0);
    double discrete=0,continuous=0,edge=0;
    for(int i=0;i<=nx+1;++i) for(int j=0;j<=ny+1;++j) for(int k=0;k<static_cast<int>(sz);++k) {
        const double u=result[index(i,j,k)];
        if(!std::isfinite(u)) throw std::runtime_error("Nonfinite solution");
        if(boundary(i,j,k)) edge=std::max(edge,std::abs(u-linear(i,j,k)));
        else {
            continuous=std::max(continuous,std::abs(u-linear(i,j,k)-wave(i,j,k)));
            discrete=std::max(discrete,std::abs(u-linear(i,j,k)-amplitude/lambda*wave(i,j,k)));
        }
    }
    if(!grid.empty()) {
        std::ofstream out(grid); if(!out) throw std::runtime_error("Cannot open grid output");
        out<<std::setprecision(17)<<"i,j,k,u\n";
        for(int i=0;i<=nx+1;++i) for(int j=0;j<=ny+1;++j) for(int k=0;k<static_cast<int>(sz);++k)
            out<<i<<','<<j<<','<<k<<','<<result[index(i,j,k)]<<'\n';
        out.close(); if(!out) throw std::runtime_error("Cannot write grid");
    }
    std::cout<<std::setprecision(17)<<"{\"problem_id\":\"poisson"<<dim<<"d_mms\",\"backend\":\""<<backend
        <<"\",\"dimension\":"<<dim<<",\"nx\":"<<nx<<",\"ny\":"<<ny<<",\"nz\":"<<(dim==3?nz:0)
        <<",\"iterations\":"<<K<<",\"requested_threads\":"<<threads<<",\"actual_threads\":"<<actual_threads
        <<",\"target_is_initial_device\":"<<(backend=="gpu"&&!ran_on_host?"false":"true")
        <<",\"omp_default_device\":"<<omp_get_default_device()
        <<",\"num_devices\":"<<devices<<",\"gpu_verified\":"<<(backend=="gpu"&&!ran_on_host?"true":"false")
        <<",\"cpu_seconds\":"<<cpu_seconds<<",\"gpu_resident_seconds\":"<<gpu_resident_seconds
        <<",\"gpu_e2e_seconds\":"<<gpu_e2e_seconds<<",\"initial_residual_l2\":"<<initial
        <<",\"residual_l2\":"<<final_residual<<",\"relative_residual\":"<<(initial==0?0:final_residual/initial)
        <<",\"discrete_error_inf\":"<<discrete<<",\"continuous_error_inf\":"<<continuous
        <<",\"boundary_error_inf\":"<<edge<<",\"status\":\"completed_fixed_work\"}\n";
    return 0;
 } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
