# C: OpenMP CPU and genuine single-GPU execution

This chapter presents the formal 64³/128³/256³ measurements and three validated follow-up experiments. The formal ratios use measurements on GN-A40-024. The follow-up sections identify their nodes and timing protocols. The member declaration is a separate draft for review. [Member C contribution and AI use](../nov10_followup/final_results_20261110/CONTRIBUTION_AI_DRAFT.md)

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

The formal run completed 36 performance calls and 18 validation cases. PBS job history reviewed on 10 November 2026 independently confirms that job `1525886.stdct-mgmt-02` finished with `job_state = F` and `Exit_status = 0`. The job ran for 5 min 29 s on `GN-A40-024` with 36 CPUs and one allocated GPU. The scheduler exit status agrees with the successful exit recorded by the run script.

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

Doubling the grid side length increases the number of interior points by 8×. At fixed K, CPU1 median time grows by 7.89× and 8.13× across the two size steps. GPU resident time grows by 3.84× and 7.97×. CPU12 time grows by 6.98× and 5.51×. These different growth rates explain why the GPU resident ratio relative to CPU12 first rises and then falls across the three sampled grids.

CPU12 speedups are 6.452, 7.293 and 10.757, with efficiencies 53.77%, 60.77% and 89.64%. These compare 1 versus 12 threads; they do not establish a complete thread-scaling curve or an optimal team size.

Relative to CPU12, GPU resident speedups are 2.338, 4.249 and 2.938. End-to-end speedups are 0.795, 2.817 and 2.688. Thus at 64³, resident execution is faster but device-region end-to-end execution is slower than CPU12. At the measured 128³ and 256³ points both GPU scopes are faster. The exact crossover size was not measured, and GPU speedup is not monotonic over these three grids.

Relative to CPU1, resident speedups are 15.083, 30.989 and 31.608; the CPU baseline must therefore be identified whenever quoting a GPU speedup. GPU performance is not assigned a CPU-core parallel efficiency.

The difference between the end-to-end and resident medians is approximately 0.1031, 0.1039 and 0.1517 seconds. As a fraction of the end-to-end median this is about 66.0%, 33.7% and 8.5%. That aggregate difference contains allocation, mapping, transfers and release; it does not isolate PCIe or any single operation. At 64³, the nonresident overhead shifts the CPU12 comparison from a resident speedup of 2.34× to an end-to-end speedup of 0.80×. At 128³ and 256³, the overhead represents a smaller share of end-to-end time, and the measured end-to-end speedups are 2.82× and 2.69×.

Using a stated model of 24 bytes per interior point update, the effective throughput is calculated as $24n^3K / (10^9 t)$ GB/s. The model counts one old-solution value, one right-hand-side value and one solution store per update, assuming reuse of neighboring values. At 64³, 128³ and 256³, the estimates are 118.3, 246.4, 247.4 GB/s for GPU resident and 50.6, 58.0, 84.2 GB/s for CPU12. The 256³ GPU estimate is about 35.5% of the 696 GB/s nominal A40 memory-bandwidth specification. This comparison uses modeled work, so it does not measure achieved DRAM bandwidth. From 128³ to 256³, GPU resident time grows by 7.97× while CPU12 time grows by 5.51×. This explains the drop in their speedup ratio arithmetically. The measurements do not isolate memory saturation or GPU occupancy. [NVIDIA A40 specifications](https://www.nvidia.com/en-us/data-center/a40/)

[Runtime figure](../deliverables/formal_20261106/analysis/runtime.pdf) · [Speedup figure](../deliverables/formal_20261106/analysis/speedup.pdf) · [Figure captions](../deliverables/formal_20261106/analysis/figure_captions.md)

CPU12 at 128³ ranged from 0.572921 to 0.870379 s. All valid observations, including this range, are retained. Ratios are ratios of medians, not paired statistical samples. Fixed-K relative residuals are approximately 0.0047745, 0.00626234 and 0.00666474, so these runs are not uniformly converged solutions.

## CPU implementation follow-up

The original 256³ medians were 39.009 s for A serial, 45.525 s for B MPI P1, and 51.451 s for C OpenMP CPU1. A ran on CN-161 with GCC 12.2.0. B used GCC 12.2.0 and Open MPI 4.1.5 with its own allocation and MPI timing scope. C ran on GN-A40-024 with NVHPC 24.7. These historical medians describe the three implementations in their respective environments. The follow-up puts A and C on the same node, and a separate comparison within C isolates the effect of changing the OpenMP loop organization. B retains its own MPI P1 reference.

PBS job `1536409.stdct-mgmt-02` finished with exit status 0 on GN-A40-024. All eight 7³ checks and 32 timed 256³ calls passed validation at K=1000. Each configuration used one warmup and three retained measurements. The single-thread runs were pinned to the same allowed CPU. The GCC comparisons used 12.2.0 and the NVHPC comparisons used 24.7.

| Variant | Threads | Median (s) | Min–max (s) |
|---|---:|---:|---:|
| A serial, GCC | 1 | 32.166 | 32.067–32.334 |
| C serial, GCC | 1 | 29.913 | 29.856–29.931 |
| C OpenMP, GCC | 1 | 37.696 | 37.455–37.729 |
| C serial, NVHPC | 1 | 28.909 | 28.880–28.921 |
| C OpenMP collapse(3), NVHPC | 1 | 51.377 | 51.376–51.392 |
| C OpenMP outer-loop, NVHPC | 1 | 28.837 | 28.821–28.896 |
| C formal build, NVHPC | 1 | 51.396 | 51.343–51.455 |
| C formal build, NVHPC | 12 | 4.968 | 4.921–5.072 |

Within the same NVHPC OpenMP implementation, assigning only the outer loop reduced the T=1 median by 43.9% relative to collapse(3). The outer-loop build was close to C serial, while the collapsed diagnostic reproduced the formal T=1 time within 0.1%. This supports loop organization as a major contributor to the single-thread penalty in this setup. Disassembly of the measured NVHPC 24.7 binaries shows how loop organization changed the generated code. The collapsed stencil updates one grid point at a time, maintains the inner indices through conditional carry and reset operations, and rebuilds the address with two integer multiplies per point. The outer-loop build hoists the row offset and includes a guarded four-point SIMD path alongside a scalar fallback. This confirms the instruction-level mechanisms available in the two builds. The timing experiment does not apportion the gain between simpler addressing and SIMD or identify which path was taken dynamically. The GCC comparisons use their own matched compiler environment. [Disassembly evidence](../nov10_followup/final_results_20261110/CPU_LOOP_EVIDENCE.md)

## GPU timing follow-up

PBS job `1536382.stdct-mgmt-02` completed with exit status 0 on Vanda GN-A40-094 with one NVIDIA A40. The instrumented run used one warmup and three retained trials per grid at K=1000. All twelve trials verified device execution, and the 7³ discrete-solution check passed. The times below are medians in milliseconds from this follow-up node.

| Interior grid | Data entry | Resident sweeps | Final copyback | Data exit | End-to-end |
|---|---:|---:|---:|---:|---:|
| 64³ | 88.502 | 53.223 | 0.251 | 0.036 | 142.133 |
| 128³ | 95.535 | 204.591 | 2.090 | 0.045 | 302.225 |
| 256³ | 128.666 | 1628.309 | 15.223 | 0.095 | 1772.293 |

The four phase times sum to end-to-end time for each individual trial. Medians are taken separately for each column. Data entry accounted for 99.7%, 97.8%, and 92.0% of nonresident time using median per-trial shares. The entry interval includes device-data mapping and host-to-device transfers and can include runtime setup. These timings do not isolate those costs. The measured final copyback is smaller than entry at every grid size.

A separate target probe measured a median first-call cost of 150.00 ms across three fresh processes and a median subsequent-call cost of 20.98 microseconds across 30 calls. The probe includes synchronization and scalar copyback. Its cold-call result is a separate observation and cannot be subtracted from the solver timing. Resident sweeps already include repeated target launches.

## CPU strong-scaling follow-up

PBS job `1536540.stdct-mgmt-02` finished with exit status 0 on GN-A40-024. The formal C build ran at 256³ and K=1000. Each of the seven thread counts passed a 7³ validation check, followed by one warmup and three retained 256³ measurements. Speedup is computed relative to the one-thread median from this allocation. Efficiency is speedup divided by thread count.

| Threads | Median (s) | Min–max (s) | Speedup | Efficiency |
|---:|---:|---:|---:|---:|
| 1 | 51.553 | 51.329–51.602 | 1.00× | 100.0% |
| 2 | 26.235 | 25.753–26.435 | 1.97× | 98.3% |
| 4 | 13.449 | 13.410–13.472 | 3.83× | 95.8% |
| 8 | 7.011 | 6.997–7.077 | 7.35× | 91.9% |
| 16 | 3.994 | 3.901–4.032 | 12.91× | 80.7% |
| 24 | 3.152 | 3.082–3.210 | 16.35× | 68.1% |
| 36 | 2.644 | 2.625–2.870 | 19.50× | 54.2% |

Among the tested configurations, 36 threads were fastest at 2.644 s and 19.50× speedup. Parallel efficiency declined from 91.9% at eight threads to 54.2% at 36 threads. These measurements establish diminishing returns at this grid size without isolating the hardware or runtime cause.

[Runtime figure](../nov10_followup/final_results_20261110/supplemental/scaling/scaling_median_s.png) · [Speedup figure](../nov10_followup/final_results_20261110/supplemental/scaling/scaling_speedup.png) · [Efficiency figure](../nov10_followup/final_results_20261110/supplemental/scaling/scaling_efficiency.png)

## Relation to MPI and overall discussion

MPI partitions distributed memory and exchanges halo faces; CPU OpenMP shares a rank's local computation, whereas target offload maps arrays and launches device kernels. C's persistent CPU region differs from B's per-sweep thread-region entry, and the compiler stacks/allocations differ. C's CPU/GPU ratios must remain within C's matched allocation; no unexplained speedup is computed by dividing a B CPU time by a C GPU time. GPU-resident mapping reduces repeated transfers but does not remove launch or synchronization costs.

Reproduction uses c_openmp/build.sh, run_c.py, make_job.py and analyze_c.py. The concise formal samples, environment metadata, validation table and figure inputs are in the formal directory of this handoff package. Raw terminal logs are excluded from the submission package. AI assistance is disclosed in the integrated report without inventing individual authorship or sign-off.

The packaged tables link each measurement to its PBS job and retain the individual observations and summary statistics. [PBS job index](../nov10_followup/final_results_20261110/PBS_status.csv) · [Formal samples](../deliverables/formal_20261106/samples.csv) · [CPU comparison](../nov10_followup/final_results_20261110/supplemental/cpu/summary.csv) · [GPU phases](../nov10_followup/final_results_20261110/supplemental/gpu/summary.csv) · [Thread scaling](../nov10_followup/final_results_20261110/supplemental/scaling/scaling.csv)
