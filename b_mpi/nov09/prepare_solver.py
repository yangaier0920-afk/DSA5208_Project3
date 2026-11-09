"""Derive an experimental solver without modifying the audited November 7 source."""
from pathlib import Path
s=Path('b_mpi/jacobi_cart.cpp').read_text().replace('#include <vector>','#include <vector>\n#include <memory>')
s=s.replace('bool diagnostic=false;std::string grid;', 'bool diagnostic=false;std::string grid,variant="baseline";')
s=s.replace('if(key=="--dim")','if(key=="--variant")variant=v;else if(key=="--dim")',1)
s=s.replace(' int periods[3]', ' const bool persistent=variant=="persistent"||variant=="optimized", parallel_pack=variant=="parallel_pack"||variant=="optimized", first_touch=variant=="first_touch"||variant=="optimized";\n if(variant!="baseline"&&variant!="persistent"&&variant!="parallel_pack"&&variant!="first_touch"&&variant!="optimized")throw std::runtime_error("invalid variant");\n int periods[3]',1)
s=s.replace(' std::vector<double>u(count,0),v(count,0),rhs(count,0);', ' std::unique_ptr<double[]>u(new double[count]),v(new double[count]),rhs(new double[count]);\n#ifdef _OPENMP\n#pragma omp parallel for collapse(2) schedule(static) if(first_touch)\n#endif')
s=s.replace('auto q=at(i,j,k);if(boundary(i,j,k))', 'auto q=at(i,j,k);u[q]=v[q]=rhs[q]=0;if(boundary(i,j,k))',1)
s=s.replace('double pack=0,comm=0,update=0,other=0;', 'double pack=0,comm=0,update=0,other=0; std::array<double,3>axis_comm{0,0,0},axis_pack{0,0,0};')
start=s.index(' auto face=');end=s.index(' auto metrics=',start)
s=s[:start]+''' auto face_serial=[&](int d,int fixed,std::vector<double>&buf,bool unpack){
  int t1=d==0?1:0,t2=d==2?1:2;
  for(int a=1;a<=l[t1];++a)for(int b=1;b<=l[t2];++b){int q[3];q[d]=fixed;q[t1]=a;q[t2]=b;size_t z=(a-1)*static_cast<size_t>(l[t2])+b-1;if(unpack)u[at(q[0],q[1],q[2])]=buf[z];else buf[z]=u[at(q[0],q[1],q[2])];}
 };
 auto face_team=[&](int d,int fixed,std::vector<double>&buf,bool unpack){
  int t1=d==0?1:0,t2=d==2?1:2;
#ifdef _OPENMP
#pragma omp for collapse(2) schedule(static)
#endif
  for(int a=1;a<=l[t1];++a)for(int b=1;b<=l[t2];++b){int q[3];q[d]=fixed;q[t1]=a;q[t2]=b;size_t z=(a-1)*static_cast<size_t>(l[t2])+b-1;if(unpack)u[at(q[0],q[1],q[2])]=buf[z];else buf[z]=u[at(q[0],q[1],q[2])];}
 };
 auto face=[&](int d,int fixed,std::vector<double>&buf,bool unpack){
#ifdef _OPENMP
  if(parallel_pack){
#pragma omp parallel
   {face_team(d,fixed,buf,unpack);}
  }else
#endif
  face_serial(d,fixed,buf,unpack);
 };
 auto halo=[&](bool timed){for(int d=0;d<dim;++d)for(int side=0;side<2;++side){int dest=side?hi[d]:lo[d],src=side?lo[d]:hi[d];double t=timed?MPI_Wtime():0;
 if(dest!=MPI_PROC_NULL)face(d,side?l[d]:1,send[d],false);
 if(timed){double dt=MPI_Wtime()-t;pack+=dt;axis_pack[d]+=dt;t=MPI_Wtime();}
 MPI_Sendrecv(send[d].data(),static_cast<int>(send[d].size()),MPI_DOUBLE,dest,2*d+side,recv[d].data(),static_cast<int>(recv[d].size()),MPI_DOUBLE,src,2*d+side,cart,MPI_STATUS_IGNORE);
 if(timed){double dt=MPI_Wtime()-t;comm+=dt;axis_comm[d]+=dt;t=MPI_Wtime();}
 if(src!=MPI_PROC_NULL)face(d,side?0:l[d]+1,recv[d],true);
 if(timed){double dt=MPI_Wtime()-t;pack+=dt;axis_pack[d]+=dt;}
 }};
''' +s[end:]
start=s.index(' for(int it=0;it<K;++it)');end=s.index(' double elapsed=',start)
old=s[start:end]
new=''' if(persistent){
 double stamp=0;
#ifdef _OPENMP
#pragma omp parallel shared(stamp)
#endif
 {
 for(int it=0;it<K;++it){
  if(parallel_pack){
   for(int d=0;d<dim;++d)for(int side=0;side<2;++side){
    int dest=side?hi[d]:lo[d],src=side?lo[d]:hi[d];
#ifdef _OPENMP
#pragma omp master
#endif
    {if(diagnostic)stamp=MPI_Wtime();}
#ifdef _OPENMP
#pragma omp barrier
#endif
    if(dest!=MPI_PROC_NULL)face_team(d,side?l[d]:1,send[d],false);
#ifdef _OPENMP
#pragma omp master
#endif
    {if(diagnostic){double dt=MPI_Wtime()-stamp;pack+=dt;axis_pack[d]+=dt;stamp=MPI_Wtime();}
     MPI_Sendrecv(send[d].data(),static_cast<int>(send[d].size()),MPI_DOUBLE,dest,2*d+side,recv[d].data(),static_cast<int>(recv[d].size()),MPI_DOUBLE,src,2*d+side,cart,MPI_STATUS_IGNORE);
     if(diagnostic){double dt=MPI_Wtime()-stamp;comm+=dt;axis_comm[d]+=dt;stamp=MPI_Wtime();}}
#ifdef _OPENMP
#pragma omp barrier
#endif
    if(src!=MPI_PROC_NULL)face_team(d,side?0:l[d]+1,recv[d],true);
#ifdef _OPENMP
#pragma omp master
#endif
    {if(diagnostic){double dt=MPI_Wtime()-stamp;pack+=dt;axis_pack[d]+=dt;}}
#ifdef _OPENMP
#pragma omp barrier
#endif
   }
  }else{
#ifdef _OPENMP
#pragma omp master
#endif
   {halo(diagnostic);}
#ifdef _OPENMP
#pragma omp barrier
#endif
  }
#ifdef _OPENMP
#pragma omp master
#endif
  {if(diagnostic)stamp=MPI_Wtime();}
#ifdef _OPENMP
#pragma omp barrier
#pragma omp for collapse(2) schedule(static)
#endif
  for(int i=1;i<=l[0];++i)for(int j=1;j<=l[1];++j)for(int k=1;k<=l[2];++k){auto q=at(i,j,k);double nb=a[0]*(u[q-sx]+u[q+sx])+a[1]*(u[q-sy]+u[q+sy]);if(dim==3)nb+=a[2]*(u[q-1]+u[q+1]);v[q]=(nb+rhs[q])/diag;}
#ifdef _OPENMP
#pragma omp master
#endif
  {if(diagnostic){update+=MPI_Wtime()-stamp;stamp=MPI_Wtime();}u.swap(v);if(diagnostic)other+=MPI_Wtime()-stamp;}
#ifdef _OPENMP
#pragma omp barrier
#endif
 }
 }
 }else{
''' +old+''' }
'''
s=s[:start]+new+s[end:]
s=s.replace('double timing[5]={elapsed,update,pack,comm,other};std::vector<double>all(rank==0?5*size:0);if(diagnostic)MPI_Gather(timing,5,MPI_DOUBLE,all.data(),5,MPI_DOUBLE,0,cart);', '''double timing[11]={elapsed,update,pack,comm,other,axis_comm[0],axis_comm[1],axis_comm[2],axis_pack[0],axis_pack[1],axis_pack[2]};std::vector<double>all(rank==0?11*size:0);if(diagnostic)MPI_Gather(timing,11,MPI_DOUBLE,all.data(),11,MPI_DOUBLE,0,cart);
 char host[MPI_MAX_PROCESSOR_NAME]={0};int hostlen;MPI_Get_processor_name(host,&hostlen);std::vector<char>hostnames(rank==0?size*MPI_MAX_PROCESSOR_NAME:0);MPI_Gather(host,MPI_MAX_PROCESSOR_NAME,MPI_CHAR,hostnames.data(),MPI_MAX_PROCESSOR_NAME,MPI_CHAR,0,cart);
 int topology[12]={c[0],c[1],c[2],lo[0],hi[0],lo[1],hi[1],lo[2],hi[2],l[0],l[1],l[2]};std::vector<int>topologies(rank==0?size*12:0);MPI_Gather(topology,12,MPI_INT,topologies.data(),12,MPI_INT,0,cart);''')
s=s.replace('<<all[5*r+j]', '<<all[11*r+j]')
needle='std::cout<<\']\';}std::cout<<"}\\n";}'
replacement='''std::cout<<']';}
 std::cout<<",\\"variant\\":\\""<<variant<<"\\",\\"rank_hosts\\":[";
 for(int r=0;r<size;++r){if(r)std::cout<<',';std::cout<<'"'<<(hostnames.data()+r*MPI_MAX_PROCESSOR_NAME)<<'"';}std::cout<<']';
 if(diagnostic){std::cout<<",\\"rank_axis_seconds\\":[";for(int r=0;r<size;++r){if(r)std::cout<<',';std::cout<<'[';for(int j=5;j<11;++j){if(j>5)std::cout<<',';std::cout<<all[11*r+j];}std::cout<<']';}std::cout<<"],\\"rank_topology\\":[";for(int r=0;r<size;++r){if(r)std::cout<<',';std::cout<<'[';for(int j=0;j<12;++j){if(j)std::cout<<',';std::cout<<topologies[12*r+j];}std::cout<<']';}std::cout<<']';}std::cout<<"}\\n";}'''
assert needle in s;s=s.replace(needle,replacement)
Path('b_mpi/nov09/jacobi_cart_tuned.cpp').write_text(s)
