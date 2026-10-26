This project focuses on a MPI+{OpenMP, CUDA, Kokkos, *} parallelization of an algorithm of your choice. Coding in C or C++ (or Fortran), you should pick an algorithm and implement it in serial and in parallel, exploring different methods of parallelization and how the various choices made in parallelization affect the parallel scaling and efficiency. The algorithm does not necessarily need to be related to data science, but the parallelization of the algorithm should present some challenges (i.e., not embarrassingly parallel). Please submit the following to Canvas before 13 November 2026:

A PDF report containing:
An introduction to the algorithm
A discussion of the design decisions made in the parallelization
A discussion of the parallel scaling and efficiency of your parallelization
A validation that the parallel algorithm works correctly
Runtime figures from Atlas or Vanda
If working with real data, conclusions about the data
Explanation of any AI usage
Your source code, with a README explaining how to run it
You may choose to work in a group of up to three people for this assignment. If you do, the report should include everyone's names and student ID numbers. 

If you are uncertain about whether an algorithm would be appropriate, please email me. If you are uncertain about your progress and whether or not it is sufficient, you may optionally email me a progress report before 30 October, and I will provide direction if necessary. 

* Other options are possible, including pthreads, OpenACC, Apple Metal for M series GPU computing, HIP for AMD GPUs, SYCL, and others. I am less familiar with these so the support I can provide is limited, but if you are interested in using one of these, please get in touch with me. 