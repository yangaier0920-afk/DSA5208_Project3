// Fixed-work MMS Jacobi; Cartesian face exchange, MPI_THREAD_FUNNELED.
#include <mpi.h>
#ifdef _OPENMP
#include <omp.h>
#endif
#include <algorithm>
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using Clock=double;
int positive(const std::string&s){size_t p;int n=std::stoi(s,&p);if(p!=s.size()||n<1||n>10000000)throw std::runtime_error("invalid positive integer");return n;}
int main(int argc,char**argv){
 int provided; MPI_Init_thread(&argc,&argv,MPI_THREAD_FUNNELED,&provided);
 int rank,size;MPI_Comm_rank(MPI_COMM_WORLD,&rank);MPI_Comm_size(MPI_COMM_WORLD,&size);
 try{
 if(provided<MPI_THREAD_FUNNELED)throw std::runtime_error("FUNNELED unavailable");
 int dim=3,K=1000;std::array<int,3> n{7,7,7},p{1,1,1}; bool diagnostic=false;std::string grid;
 for(int a=1;a<argc;++a){std::string key=argv[a];if(a+1==argc)throw std::runtime_error("missing value");std::string v=argv[++a];
 if(key=="--dim")dim=positive(v);else if(key=="--nx")n[0]=positive(v);else if(key=="--ny")n[1]=positive(v);else if(key=="--nz")n[2]=positive(v);
 else if(key=="--px")p[0]=positive(v);else if(key=="--py")p[1]=positive(v);else if(key=="--pz")p[2]=positive(v);else if(key=="--iterations")K=positive(v);
 else if(key=="--diagnostic") {if(v!="0"&&v!="1")throw std::runtime_error("diagnostic 0 or 1");diagnostic=v=="1";}else if(key=="--grid")grid=v;else throw std::runtime_error("unknown argument "+key);}
 if(dim!=2&&dim!=3)throw std::runtime_error("dim must be 2 or 3");if(dim==2){n[2]=1;if(p[2]!=1)throw std::runtime_error("2D requires pz=1");}
 if(1LL*p[0]*p[1]*p[2]!=size)throw std::runtime_error("process grid product differs from MPI size");for(int d=0;d<3;++d)if(p[d]>n[d])throw std::runtime_error("empty subdomain");
 int periods[3]={0,0,0};MPI_Comm cart;MPI_Cart_create(MPI_COMM_WORLD,3,p.data(),periods,0,&cart);std::array<int,3> c,l,start,lo,hi;
 MPI_Cart_coords(cart,rank,3,c.data());for(int d=0;d<3;++d){l[d]=n[d]/p[d]+(c[d]<n[d]%p[d]);start[d]=c[d]*(n[d]/p[d])+std::min(c[d],n[d]%p[d]);MPI_Cart_shift(cart,d,1,&lo[d],&hi[d]);}
 const size_t sy=l[2]+2,sx=(l[1]+2)*sy,count=(l[0]+2)*sx;auto at=[&](int i,int j,int k){return i*sx+j*sy+k;};
 const double pi=std::acos(-1.0),coef=(dim==3?14:5)*pi*pi;double h[3],a[3],diag=0,lambda=0;int modes[3]={1,2,3};
 for(int d=0;d<3;++d){h[d]=1.0/(n[d]+1);a[d]=d<dim?1/(h[d]*h[d]):0;diag+=2*a[d];lambda+=4*a[d]*std::pow(std::sin(modes[d]*pi*h[d]/2),2);}
 auto linear=[&](int i,int j,int k){return (start[0]+i)*h[0]+2*(start[1]+j)*h[1]+(dim==3?3*(start[2]+k)*h[2]:0);};
 auto wave=[&](int i,int j,int k){return std::sin(pi*(start[0]+i)*h[0])*std::sin(2*pi*(start[1]+j)*h[1])*(dim==3?std::sin(3*pi*(start[2]+k)*h[2]):1);};
 auto boundary=[&](int i,int j,int k){int q[3]={start[0]+i,start[1]+j,start[2]+k};for(int d=0;d<dim;++d)if(q[d]==0||q[d]==n[d]+1)return true;return false;};
 std::vector<double>u(count,0),v(count,0),rhs(count,0);
 for(int i=0;i<=l[0]+1;++i)for(int j=0;j<=l[1]+1;++j)for(int k=0;k<=l[2]+1;++k){auto q=at(i,j,k);if(boundary(i,j,k))u[q]=v[q]=linear(i,j,k);else rhs[q]=coef*wave(i,j,k);}
 std::array<std::vector<double>,3>send,recv;for(int d=0;d<dim;++d){size_t face=1;for(int e=0;e<3;++e)if(e!=d)face*=l[e];send[d].resize(face);recv[d].resize(face);}
 double pack=0,comm=0,update=0,other=0;
 // Faces contain interior tangential indices only: a seven-point stencil needs no edges/corners.
 auto face=[&](int d,int fixed,std::vector<double>&buf,bool unpack){size_t z=0;for(int i=(d==0?fixed:1);i<=(d==0?fixed:l[0]);++i)for(int j=(d==1?fixed:1);j<=(d==1?fixed:l[1]);++j)for(int k=(d==2?fixed:1);k<=(d==2?fixed:l[2]);++k){if(unpack)u[at(i,j,k)]=buf[z++];else buf[z++]=u[at(i,j,k)];}};
 auto halo=[&](bool timed){for(int d=0;d<dim;++d)for(int side=0;side<2;++side){int dest=side?hi[d]:lo[d],src=side?lo[d]:hi[d];double t=timed?MPI_Wtime():0;if(dest!=MPI_PROC_NULL)face(d,side?l[d]:1,send[d],false);if(timed){pack+=MPI_Wtime()-t;t=MPI_Wtime();}
 MPI_Sendrecv(send[d].data(),static_cast<int>(send[d].size()),MPI_DOUBLE,dest,2*d+side,recv[d].data(),static_cast<int>(recv[d].size()),MPI_DOUBLE,src,2*d+side,cart,MPI_STATUS_IGNORE);
 if(timed){comm+=MPI_Wtime()-t;t=MPI_Wtime();}if(src!=MPI_PROC_NULL)face(d,side?0:l[d]+1,recv[d],true);if(timed)pack+=MPI_Wtime()-t;}};
 auto metrics=[&](){double sum=0,err=0,cont=0,bnd=0,bad=0;halo(false);
 for(int i=1;i<=l[0];++i)for(int j=1;j<=l[1];++j)for(int k=1;k<=l[2];++k){auto q=at(i,j,k);double r=rhs[q]-diag*u[q]+a[0]*(u[q-sx]+u[q+sx])+a[1]*(u[q-sy]+u[q+sy]);if(dim==3)r+=a[2]*(u[q-1]+u[q+1]);sum+=r*r;err=std::max(err,std::abs(u[q]-linear(i,j,k)-coef/lambda*wave(i,j,k)));cont=std::max(cont,std::abs(u[q]-linear(i,j,k)-wave(i,j,k)));if(!std::isfinite(r)||!std::isfinite(u[q]))bad=1;}
 for(int i=0;i<=l[0]+1;++i)for(int j=0;j<=l[1]+1;++j)for(int k=1;k<=l[2];++k)if(boundary(i,j,k))bnd=std::max(bnd,std::abs(u[at(i,j,k)]-linear(i,j,k)));
 if(dim==3)for(int i=1;i<=l[0];++i)for(int j=1;j<=l[1];++j)for(int k:{0,l[2]+1})if(boundary(i,j,k))bnd=std::max(bnd,std::abs(u[at(i,j,k)]-linear(i,j,k)));
 double gsum;MPI_Allreduce(&sum,&gsum,1,MPI_DOUBLE,MPI_SUM,cart);double vals[4]={err,cont,bnd,bad},out[4];MPI_Allreduce(vals,out,4,MPI_DOUBLE,MPI_MAX,cart);return std::array<double,5>{std::sqrt(gsum),out[0],out[1],out[2],out[3]};};
 int threads=1;
#ifdef _OPENMP
#pragma omp parallel
 { 
#pragma omp single
 threads=omp_get_num_threads();
 }
#endif
 int tmin,tmax;MPI_Allreduce(&threads,&tmin,1,MPI_INT,MPI_MIN,cart);MPI_Allreduce(&threads,&tmax,1,MPI_INT,MPI_MAX,cart);if(tmin!=tmax)throw std::runtime_error("thread count differs across ranks");
 MPI_Comm shared;MPI_Comm_split_type(cart,MPI_COMM_TYPE_SHARED,rank,MPI_INFO_NULL,&shared);int sr;MPI_Comm_rank(shared,&sr);int leader=sr==0,nodes;MPI_Allreduce(&leader,&nodes,1,MPI_INT,MPI_SUM,cart);MPI_Comm_free(&shared);
 auto initial=metrics();MPI_Barrier(cart);double begin=MPI_Wtime();
 for(int it=0;it<K;++it){halo(diagnostic);double t=diagnostic?MPI_Wtime():0;
#ifdef _OPENMP
#pragma omp parallel for collapse(2) schedule(static)
#endif
 for(int i=1;i<=l[0];++i)for(int j=1;j<=l[1];++j)for(int k=1;k<=l[2];++k){auto q=at(i,j,k);double nb=a[0]*(u[q-sx]+u[q+sx])+a[1]*(u[q-sy]+u[q+sy]);if(dim==3)nb+=a[2]*(u[q-1]+u[q+1]);v[q]=(nb+rhs[q])/diag;}
 if(diagnostic){update+=MPI_Wtime()-t;t=MPI_Wtime();}u.swap(v);if(diagnostic)other+=MPI_Wtime()-t;
 }
 double elapsed=MPI_Wtime()-begin,maxelapsed;MPI_Allreduce(&elapsed,&maxelapsed,1,MPI_DOUBLE,MPI_MAX,cart);auto final=metrics();
 double timing[5]={elapsed,update,pack,comm,other};std::vector<double>all(rank==0?5*size:0);if(diagnostic)MPI_Gather(timing,5,MPI_DOUBLE,all.data(),5,MPI_DOUBLE,0,cart);
 if(!grid.empty()){std::ofstream f(grid+".rank"+std::to_string(rank)+".csv");if(!f)throw std::runtime_error("cannot open grid");f<<std::setprecision(17)<<"i,j,k,u\n";for(int i=1;i<=l[0];++i)for(int j=1;j<=l[1];++j)for(int k=1;k<=l[2];++k)f<<start[0]+i<<','<<start[1]+j<<','<<(dim==3?start[2]+k:0)<<','<<u[at(i,j,k)]<<'\n';}
 if(rank==0){std::cout<<std::setprecision(17)<<"{\"problem_id\":\"poisson"<<dim<<"d_mms\",\"nx\":"<<n[0]<<",\"ny\":"<<n[1]<<",\"nz\":"<<(dim==3?n[2]:0)<<",\"iterations\":"<<K<<",\"ranks\":"<<size<<",\"threads\":"<<threads<<",\"nodes\":"<<nodes<<",\"process_grid\":["<<p[0]<<','<<p[1]<<','<<p[2]<<"],\"diagnostic\":"<<(diagnostic?"true":"false")<<",\"compute_seconds\":"<<maxelapsed<<",\"initial_residual_l2\":"<<initial[0]<<",\"residual_l2\":"<<final[0]<<",\"relative_residual\":"<<(initial[0]?final[0]/initial[0]:0)<<",\"discrete_error_inf\":"<<final[1]<<",\"continuous_error_inf\":"<<final[2]<<",\"boundary_error_inf\":"<<final[3]<<",\"status\":\""<<(final[4]?"FAIL":"fixed_iterations")<<'"';
 if(diagnostic){std::cout<<",\"rank_timings\":[";for(int r=0;r<size;++r){if(r)std::cout<<',';std::cout<<'[';for(int j=0;j<5;++j){if(j)std::cout<<',';std::cout<<all[5*r+j];}std::cout<<']';}std::cout<<']';}std::cout<<"}\n";}
 MPI_Comm_free(&cart);MPI_Finalize();return final[4]?1:0;
 }catch(const std::exception&e){std::cerr<<"rank "<<rank<<": "<<e.what()<<'\n';MPI_Abort(MPI_COMM_WORLD,1);return 1;}
}
