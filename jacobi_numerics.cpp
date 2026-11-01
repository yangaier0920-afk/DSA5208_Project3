// A's serial numerical route. No MPI/OpenMP; historical solvers are preserved.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

struct Sample { int k; double l2, linf, relative; };
int integer(const std::string& s) {
    std::size_t used=0; int v=std::stoi(s,&used);
    if(used!=s.size() || v<1 || v>10000000) throw std::invalid_argument("Invalid positive integer");
    return v;
}
int main(int argc,char** argv) {
    try {
        std::string problem="poisson3d_mms", mode="fixed", history_path, grid_path;
        int nx=7,ny=0,nz=0,limit=1000,interval=10;
        double tol=1e-8;
        for(int a=1;a<argc;++a) {
            std::string key=argv[a];
            if(key=="--help") {
                std::cout<<"--problem poisson3d_mms|laplace2d_legacy --nx N [--ny N --nz N] "
                    "--mode fixed|solve --max-iters K --tol R --check-every C "
                    "[--history FILE --grid FILE]\n"; return 0;
            }
            if(a+1>=argc) throw std::invalid_argument("Missing option value");
            std::string val=argv[++a];
            if(key=="--problem") problem=val;
            else if(key=="--mode") mode=val;
            else if(key=="--nx") nx=integer(val);
            else if(key=="--ny") ny=integer(val);
            else if(key=="--nz") nz=integer(val);
            else if(key=="--max-iters") limit=integer(val);
            else if(key=="--check-every") interval=integer(val);
            else if(key=="--history") history_path=val;
            else if(key=="--grid") grid_path=val;
            else if(key=="--tol") {
                std::size_t used=0; tol=std::stod(val,&used);
                if(used!=val.size()) throw std::invalid_argument("Invalid tolerance");
            } else throw std::invalid_argument("Unknown option: "+key);
        }
        if(problem!="poisson3d_mms" && problem!="laplace2d_legacy")
            throw std::invalid_argument("Unknown problem");
        if(mode!="fixed" && mode!="solve") throw std::invalid_argument("Unknown mode");
        if(!std::isfinite(tol) || tol<=0) throw std::invalid_argument("Tolerance must be finite and positive");
        const bool three=problem=="poisson3d_mms";
        if(!ny) ny=nx;
        if(!nz) nz=three?nx:1;
        if(!three && nz!=1) throw std::invalid_argument("2D requires nz=1");
        const std::size_t sx=static_cast<std::size_t>(nx)+2;
        const std::size_t sy=static_cast<std::size_t>(ny)+2;
        const std::size_t sz=three?static_cast<std::size_t>(nz)+2:1;
        const std::size_t cap=std::vector<double>().max_size();
        if(sx>cap/sy || sx*sy>cap/sz) throw std::length_error("Grid size overflow");
        const std::size_t count=sx*sy*sz, stride=sy*sz;
        const double hx=1.0/(nx+1),hy=1.0/(ny+1),hz=three?1.0/(nz+1):1;
        const double ax=1/(hx*hx),ay=1/(hy*hy),az=three?1/(hz*hz):0;
        const double diag=2*(ax+ay+az),pi=std::acos(-1.0);
        auto at=[=](int i,int j,int k) {return static_cast<std::size_t>(i)*stride+static_cast<std::size_t>(j)*sz+k;};
        auto boundary=[=](int i,int j,int k) {
            return i==0||i==nx+1||j==0||j==ny+1||(three&&(k==0||k==nz+1));
        };
        auto linear=[=](int i,int j,int k) {return i*hx+(three?2:1)*j*hy+(three?3*k*hz:0);};
        auto wave=[=](int i,int j,int k) {
            return three?std::sin(pi*i*hx)*std::sin(2*pi*j*hy)*std::sin(3*pi*k*hz):0.0;
        };
        std::vector<double> u(count,0),v(count,0),rhs(count,0);
        for(int i=0;i<=nx+1;++i) for(int j=0;j<=ny+1;++j)
            for(int k=0;k<static_cast<int>(sz);++k) {
                auto q=at(i,j,k);
                if(boundary(i,j,k)) u[q]=v[q]=linear(i,j,k);
                else rhs[q]=three?14*pi*pi*wave(i,j,k):0;
            }
        auto residual=[&](int iteration,double initial) {
            double sum=0,maximum=0;
            for(int i=1;i<=nx;++i) for(int j=1;j<=ny;++j)
                for(int k=three?1:0;k<=(three?nz:0);++k) {
                    auto q=at(i,j,k);
                    double ah=diag*u[q]-ax*(u[q-stride]+u[q+stride])-ay*(u[q-sz]+u[q+sz]);
                    if(three) ah-=az*(u[q-1]+u[q+1]);
                    double r=rhs[q]-ah;
                    if(!std::isfinite(r)) throw std::runtime_error("Non-finite residual");
                    sum+=r*r; maximum=std::max(maximum,std::abs(r));
                }
            double norm=std::sqrt(sum);
            if(!std::isfinite(norm)) throw std::runtime_error("Residual norm overflow");
            return Sample{iteration,norm,maximum,initial==0?(norm==0?0:std::numeric_limits<double>::infinity()):norm/initial};
        };
        Sample initial=residual(0,1); initial.relative=initial.l2==0?0:1;
        std::vector<Sample> samples{initial};
        bool converged=initial.l2==0;
        int iterations=0;
        const auto begin=std::chrono::steady_clock::now();
        for(int iteration=1;iteration<=limit && !(mode=="solve"&&converged);++iteration) {
            for(int i=1;i<=nx;++i) for(int j=1;j<=ny;++j)
                for(int k=three?1:0;k<=(three?nz:0);++k) {
                    auto q=at(i,j,k);
                    double neighbors=ax*(u[q-stride]+u[q+stride])+ay*(u[q-sz]+u[q+sz]);
                    if(three) neighbors+=az*(u[q-1]+u[q+1]);
                    v[q]=(neighbors+rhs[q])/diag;
                }
            u.swap(v); iterations=iteration;
            if(mode=="solve" && (iteration%interval==0||iteration==limit)) {
                samples.push_back(residual(iteration,initial.l2));
                converged=samples.back().relative<=tol;
            }
        }
        const double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-begin).count();
        Sample final_sample=residual(iterations,initial.l2);
        if(samples.back().k!=iterations) samples.push_back(final_sample);
        converged=final_sample.relative<=tol;
        const double lambda=three?4*ax*std::pow(std::sin(pi*hx/2),2)
            +4*ay*std::pow(std::sin(2*pi*hy/2),2)+4*az*std::pow(std::sin(3*pi*hz/2),2):1;
        double error=0,discrete_error=0,boundary_error=0;
        for(int i=0;i<=nx+1;++i) for(int j=0;j<=ny+1;++j)
            for(int k=0;k<static_cast<int>(sz);++k) {
                double value=u[at(i,j,k)];
                if(!std::isfinite(value)) throw std::runtime_error("Non-finite solution");
                if(boundary(i,j,k)) boundary_error=std::max(boundary_error,std::abs(value-linear(i,j,k)));
                else {
                    error=std::max(error,std::abs(value-linear(i,j,k)-wave(i,j,k)));
                    discrete_error=std::max(discrete_error,std::abs(value-linear(i,j,k)-(three?14*pi*pi/lambda:0)*wave(i,j,k)));
                }
            }
        if(!history_path.empty()) {
            std::ofstream out(history_path);
            if(!out) throw std::runtime_error("Cannot open history");
            out<<std::setprecision(17)<<"iteration,residual_l2,residual_inf,relative_residual\n";
            for(auto s:samples) out<<s.k<<','<<s.l2<<','<<s.linf<<','<<s.relative<<'\n';
            out.close(); if(!out) throw std::runtime_error("Cannot write history");
        }
        if(!grid_path.empty()) {
            std::ofstream out(grid_path);
            if(!out) throw std::runtime_error("Cannot open grid");
            out<<std::setprecision(17)<<"i,j,k,u\n";
            for(int i=0;i<=nx+1;++i) for(int j=0;j<=ny+1;++j)
                for(int k=0;k<static_cast<int>(sz);++k) out<<i<<','<<j<<','<<k<<','<<u[at(i,j,k)]<<'\n';
            out.close(); if(!out) throw std::runtime_error("Cannot write grid");
        }
        int first=-1;
        for(auto s:samples) if(s.relative<=1e-8) {first=s.k;break;}
        std::cout<<std::setprecision(17)
            <<"{\"problem_id\":\""<<problem<<"\",\"dimension\":"<<(three?3:2)
            <<",\"implementation\":\"serial_A\",\"mode\":\""<<mode<<"\",\"nx\":"<<nx<<",\"ny\":"<<ny<<",\"nz\":"<<(three?nz:0)
            <<",\"max_iters\":"<<limit<<",\"iterations\":"<<iterations<<",\"tolerance\":"<<tol<<",\"check_every\":"<<interval
            <<",\"status\":\""<<(mode=="fixed"?"fixed_iterations":(converged?"converged":"iteration_limit"))
            <<"\",\"converged\":"<<(converged?"true":"false")<<",\"initial_residual_l2\":"<<initial.l2
            <<",\"residual_l2\":"<<final_sample.l2<<",\"residual_inf\":"<<final_sample.linf
            <<",\"relative_residual\":"<<final_sample.relative<<",\"continuous_error_inf\":"<<error
            <<",\"discrete_error_inf\":"<<discrete_error<<",\"boundary_error_inf\":"<<boundary_error
            <<",\"first_check_le_1e8\":"<<first<<",\"compute_seconds\":"<<seconds<<"}\n";
        return mode=="solve"&&!converged?2:0;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}

