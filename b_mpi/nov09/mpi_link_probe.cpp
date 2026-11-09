#include <mpi.h>
#include <algorithm>
#include <iostream>
#include <iomanip>
#include <vector>
int main(int argc,char**argv){MPI_Init(&argc,&argv);int r,n;MPI_Comm_rank(MPI_COMM_WORLD,&r);MPI_Comm_size(MPI_COMM_WORLD,&n);if(n!=2){MPI_Abort(MPI_COMM_WORLD,1);return 1;}char h[MPI_MAX_PROCESSOR_NAME]={0};int len;MPI_Get_processor_name(h,&len);char hosts[2*MPI_MAX_PROCESSOR_NAME]={0};MPI_Gather(h,MPI_MAX_PROCESSOR_NAME,MPI_CHAR,hosts,MPI_MAX_PROCESSOR_NAME,MPI_CHAR,0,MPI_COMM_WORLD);if(r==0)std::cout<<std::setprecision(17)<<"{\"hosts\":[\""<<hosts<<"\",\""<<hosts+MPI_MAX_PROCESSOR_NAME<<"\"],\"measurements\":[";
 bool comma=false;for(int bytes:{8,32768,65536,262144}){std::vector<char>b(bytes,1);int k=bytes==8?2000:500;for(int repeat=-1;repeat<3;++repeat){int loops=repeat<0?100:k;MPI_Barrier(MPI_COMM_WORLD);double t=MPI_Wtime();for(int i=0;i<loops;++i){if(r==0){MPI_Send(b.data(),bytes,MPI_BYTE,1,1,MPI_COMM_WORLD);MPI_Recv(b.data(),bytes,MPI_BYTE,1,2,MPI_COMM_WORLD,MPI_STATUS_IGNORE);}else{MPI_Recv(b.data(),bytes,MPI_BYTE,0,1,MPI_COMM_WORLD,MPI_STATUS_IGNORE);MPI_Send(b.data(),bytes,MPI_BYTE,0,2,MPI_COMM_WORLD);}}double elapsed=MPI_Wtime()-t;if(r==0&&repeat>=0){if(comma)std::cout<<',';comma=true;std::cout<<"{\"bytes\":"<<bytes<<",\"round_trips\":"<<loops<<",\"repeat\":"<<repeat<<",\"seconds\":"<<elapsed<<",\"round_trip_seconds\":"<<elapsed/loops<<'}';}}}
 if(r==0)std::cout<<"]}\n";MPI_Finalize();return 0;}
