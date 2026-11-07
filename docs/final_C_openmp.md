# C: OpenMP CPU and genuine single-GPU execution

This English chapter consolidates the completed formal 64³/128³/256³ experiment. It uses only the formal data on GN-A40-024, not the earlier pilot. Author identification and personal contribution declarations are omitted as requested.

## Implementation and device execution

Both backends solve the common manufactured 2D/3D Poisson problem in double precision, with zero initial interior values, fixed Dirichlet boundaries, a precomputed right-hand side and two solution buffers. Performance measurements use 3D seven-point updates and exactly K=1000 sweeps. The 2D path is exercised by nonzero-source validation, not a second performance matrix.

The CPU backend creates a persistent OpenMP parallel region around the sweep loop. Static work sharing with collapse(3) distributes interior points. An implicit barrier completes each sweep before the next; iteration parity selects the read/write buffers without a shared pointer-swap race. Requested and actual team sizes are checked. CPU comparisons use T=1 and T=12, with OMP_PLACES=cores, OMP_PROC_BIND=close and dynamic teams disabled.

The GPU backend keeps both solution buffers and the right-hand side on the device for all sweeps. Each sweep launches a synchronous target teams/distribute/parallel-for region over the interior; no nowait is used. Only the final solution buffer is copied back for diagnostics. Team/thread mapping is left to the compiler/runtime and is not claimed to be optimal.

Real offload is checked inside the first actual stencil target region using omp_is_initial_device(), alongside a positive device count and OMP_TARGET_OFFLOAD=MANDATORY. The formal GPU samples report gpu_verified=true and target_is_initial_device=false, so host fallback is not counted as GPU execution.

The working NVHPC build separates the C++ host/CPU implementation from a C target translation unit. The host is compiled with -mp=multicore, the target unit with -mp=gpu, and the final link enables GPU support; GCC toolchain selection is explicit. This is a tested workaround for the earlier C++ GPU frontend failure, without assigning that failure to an unproven language clause. Reproduce with bash c_openmp/build.sh nvidia rather than an obsolete single-source GPU command.

## Platform and measurement protocol

The formal platform is Vanda GN-A40-024: Intel Xeon Platinum 8452Y and one NVIDIA A40 with 46068 MiB reported memory, driver 575.57.08, NVHPC 24.7 / CUDA 12.3.0 / GCC 13.2.0, with -O2 in the build. The allocation supplied 36 CPU cores and one GPU; CPU baselines deliberately use 1/12 computational threads. Allocation size is not reported as CPU team size.

There are nine performance configurations: three grids times CPU1/CPU12/GPU. Each has one warmup and three retained measurements, with a fresh process/initial state every time. Configuration order rotates between formal rounds. GPU resident and end-to-end times come from the same invocation. Report medians and actual min/max; three samples do not give confidence intervals or establish a runtime distribution.

| Metric | Included interval |
|---|---|
| CPU iteration | K sweeps after host data preparation, including thread-region entry and per-sweep synchronization |
| GPU resident | K target launches and their completion after device data is resident |
| GPU end-to-end | Device allocation/mapping and transfers, K sweeps, final solution copyback and exit from the device data region |

Host mathematical initialization, final residual/error calculation and file output are excluded from all three. GPU end-to-end therefore means the solver data-region interval, not the entire executable walltime. Resident is not a device-event kernel-only measurement.

The supplied run status is COMPLETED with 36 performance calls and 18 validation cases. The source result note records a successful run log. An independent final PBS historical record was not present in C's supplied evidence, and the current account cannot establish it; no PBS Exit_status is inferred from a log or an unavailable scheduler query.

## Validation and limits

| Purpose | Case and modes | Maximum error | Criterion |
|---|---|---:|---:|
| Exact discrete 2D solution | 7×7, K=1000, CPU1/CPU12/GPU | 1.1945e-15 | 1e-9 |
| Exact discrete 3D solution | 7³, K=1000, CPU1/CPU12/GPU | 2.7247e-15 | 1e-9 |
| Independent transient formula | 9×7 and 9×7×5, K=1/2, all modes | 6.6613e-16 | 1e-12 |
| CPU/GPU full-grid agreement | Six small-grid pairs including boundaries | 0 | 1e-9 |
| Boundary preservation | All 18 validation cases | 0 | 1e-12 |

All 18 checks passed. The one/two-step checks validate finite-time updates and buffer parity; they do not require convergence. The six full-grid comparisons are small cases. Large-grid performance samples were checked using device execution, finite diagnostics, boundary values and matched residuals; they were not all exported for pointwise comparison. Continuous-solution error includes discretization error and must not be substituted for implementation difference.

## Formal results

K=1000; seconds below are medians of three formal samples, excluding warmups.

| Interior grid | CPU1 | CPU12 | GPU resident | GPU end-to-end |
|---|---:|---:|---:|---:|
| 64³ | 0.802221 | 0.124330 | 0.053188 | 0.156299 |
| 128³ | 6.330078 | 0.867985 | 0.204269 | 0.308162 |
| 256³ | 51.450687 | 4.783182 | 1.627774 | 1.779479 |

CPU12 speedups are 6.452, 7.293 and 10.757, with efficiencies 53.77%, 60.77% and 89.64%. These compare 1 versus 12 threads; they do not establish a complete thread-scaling curve or an optimal team size.

Relative to CPU12, GPU resident speedups are 2.338, 4.249 and 2.938. End-to-end speedups are 0.795, 2.817 and 2.688. Thus at 64³, resident execution is faster but device-region end-to-end execution is slower than CPU12. At the measured 128³ and 256³ points both GPU scopes are faster. The exact crossover size was not measured, and GPU speedup is not monotonic over these three grids.

Relative to CPU1, resident speedups are 15.083, 30.989 and 31.608; the CPU baseline must therefore be identified whenever quoting a GPU speedup. GPU performance is not assigned a CPU-core parallel efficiency.

The difference between the end-to-end and resident medians is approximately 0.1031, 0.1039 and 0.1517 seconds. As a fraction of the end-to-end median this is about 66.0%, 33.7% and 8.5%. That aggregate difference contains allocation, mapping, transfers and release; it does not isolate PCIe or any single operation. The falling relative overhead helps explain why larger measured workloads benefit more from offload despite nonmonotonic resident speedup against CPU12.

CPU12 at 128³ ranged from 0.572921 to 0.870379 s. All valid observations, including this range, are retained. Ratios are ratios of medians, not paired statistical samples. Fixed-K relative residuals are approximately 0.0047745, 0.00626234 and 0.00666474, so these runs are not uniformly converged solutions.

## Relation to MPI and overall discussion

MPI partitions distributed memory and exchanges halo faces; CPU OpenMP shares a rank's local computation, whereas target offload maps arrays and launches device kernels. C's persistent CPU region differs from B's per-sweep thread-region entry, and the compiler stacks/allocations differ. C's CPU/GPU ratios must remain within C's matched allocation; no unexplained speedup is computed by dividing a B CPU time by a C GPU time. GPU-resident mapping reduces repeated transfers but does not remove launch or synchronization costs.

Reproduction uses c_openmp/build.sh, run_c.py, make_job.py and analyze_c.py. The concise formal samples, environment metadata, validation table and figure inputs are under c_openmp/deliverables/formal_20261106/. Raw terminal logs are excluded from the submission package. AI assistance is disclosed in the integrated report without inventing individual authorship or sign-off.
