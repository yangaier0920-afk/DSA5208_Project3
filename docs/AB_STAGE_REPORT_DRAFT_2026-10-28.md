# DSA5208 Project 3: A/B Progress Report

28 October 2026 · Prepared for the 29 October update · Awaiting team review; not sent

The serial baseline/correctness work (A), pure MPI (B), and all three supplementary experiments are complete for this round. We explain the original serial/P1 timing gap and validate the tested numerical cases. Scaling varies over time; the wait-placement diagnostic shows no clear benefit at 2048/P2 and approximately 1% lower median times at P12.

## Implementation and measurement

We solve the two-dimensional Laplace equation on a unit square using double-precision, five-point Jacobi iteration with old/new buffers, boundary values u=x+y and zero interior initialization. The grid has n×n interior points. MPI assigns contiguous row blocks plus two halo rows; the first n mod P ranks receive one extra row. P>n is rejected.

Sendrecv (SR) exchanges halos before updating. Overlap (OV) posts nonblocking receives/sends, computes halo-independent interior rows, waits, then updates edge rows, including one/two-row partitions. “Overlap” names the schedule, not a proven mechanism.

The four scaling jobs and the wait diagnostic each used one Vanda node, 12 allocated CPUs/4GB, GCC 12.2.0, OpenMPI 4.1.5 and `-std=c++17 -O2 -Wall -Wextra -Wpedantic`, without OpenMP. CPU/rank mappings were fixed within each job and checked before execution.

Performance measures K=1000 iterations with tol=0, not convergence time. Local maximum updates are computed every iteration; the global maximum-update Allreduce runs only in the final iteration, or every iteration for positive-tolerance stopping. Timers include iteration computation, halo exchange and these reductions; MPI reports the maximum rank-local elapsed time. Initialization, the initial barrier, final timing reduction, final metrics/halo refresh, gathering, startup and output are excluded.

## Serial baseline and correctness

In job 1499842, median times were 3.496400s (original serial), 3.469020s (iteration-local reduction), 1.723135s (row-local reduction) and 1.746897s (MPI P=1). Controlled changes and Linux disassembly identify per-point stack accesses in the original maximum-update reduction as the main gap source in that environment, not vectorization. Subsequent scaling uses `jacobi_serial_row_update.cpp`; historical sources/results and old-job baselines remain unchanged.

Four original suites passed 352 numerical executions and 16 expected rejections, including 172 full-grid comparisons against independent small-grid references. Another 31 full-grid executions tested u=x+2y+xy (x: column; y: row), covering unequal partitions, one/two-row partitions, both schemes, buffer swaps and stopping. Maximum pointwise difference was 8.88e-16.

These are small-grid results. Large performance grids were checked through workload and global metrics, without full-grid comparison; analytic errors after 1000 iterations remained approximately 1.859/1.925 for n=1024/2048.

## Pure-MPI scaling

Each job/size dataset has nine configurations: serial and MPI P=1/2/4/12 with SR/OV. Each configuration has one warmup and nine formal measurements. Let T denote the median of formal times. Within the same job and size, S_serial=T_serial/T_P,scheme and S_MPI=T_1,scheme/T_P,scheme; the latter uses the same scheme at P=1. Efficiency is S/P. Jobs, sizes and production/diagnostic samples or baselines are never pooled.

Paired entries are **SR / OV**. The [full table](../evidence/ab_summary_2026-10-28/performance_comparison.csv) contains all P1/2/4/12 timings, both speedups, efficiencies and dispersion.

| Job / node | n | Serial T (s) | P12 T (s) | P12 S_serial | P12 S_MPI |
|---|---:|---:|---:|---:|---:|
| 1499881 / IN-006 | 1024 | 2.066070 | 0.224262 / 0.216749 | 9.213 / 9.532 | 9.267 / 9.603 |
| 1500271 / IN-003 | 1024 | 1.527579 | 0.217869 / 0.217064 | 7.011 / 7.037 | 7.084 / 7.048 |
| 1500222 / IN-003 | 2048 | 6.842698 | 1.168184 / 1.166647 | 5.858 / 5.865 | 5.787 / 5.937 |
| 1501884 / IN-005 | 1024 | 1.749200 | 3.101710 / 0.991551 | 0.564 / 1.764 | 0.564 / 1.801 |
| 1501884 / IN-005 | 2048 | 7.650589 | 4.192806 / 2.828012 | 1.825 / 2.705 | 1.829 / 2.730 |

The first three jobs showed decreasing median times with increasing P. Job 1501884 interleaved both sizes with unchanged production source/binaries and fixed mapping. Yet 1024/P12/SR times fell from 3.102–3.504s in rounds 0–4 to 0.213–0.224s in rounds 5–8, while serial/P1 slowed later. Scaling was not monotonic; 1024/P12/SR was slower than serial. All samples remain included. Fixed allocation/binding did not ensure stable timing. Ordering was balanced within each size, not across eighteen cross-size positions.

## Independent wait-placement diagnostic

Job 1502229 compared SR, nonblocking immediate Waitall (IM), and OV in one independent, uninstrumented diagnostic program. IM/OV share interior/edge work and update order; only wait placement changes. SR/IM also changes update ordering/grouping and potentially code generation, so it does not isolate API cost.

All 45 correctness executions passed before timing: 18 production and 27 diagnostic, comprising 35 full small grids and 10 global-metric checks. Maximum pointwise difference was 2.22e-16.

All timing below uses the diagnostic binary: one warmup and five formal measurements per configuration. Schemes ran adjacently in rotating order; positions occurred once or twice, not equally often. Reduction means 100×(1−T_OV/T_IM).

| n / P | SR T (s) | IM T (s) | OV T (s) | OV reduction vs IM | OV faster rounds |
|---|---:|---:|---:|---:|---:|
| 2048 / 2 | 4.434342 | 4.399289 | 4.406850 | −0.17% | 2/5 |
| 2048 / 12 | 1.285498 | 1.263220 | 1.250628 | +1.00% | 4/5 |
| 1024 / 12 | 0.221087 | 0.219135 | 0.216518 | +1.19% | 4/5 |

P2 shows no clear wait-placement advantage. P12 differences are small observations from one allocation and five rounds; neither statistical significance nor effective underlying communication overlap is established. The slower 2048/P2/SR sample of 5.331092s passed recorded checks and remains included.

Earlier production jobs showed 16.61% and 14.01% SR-to-OV reductions at 2048/P2. This diagnostic does not establish early interior computation as their cause. Its program, allocation and time differ; it neither invalidates those raw observations nor identifies their mechanism.

## Limitations and completion

The [evidence index](../evidence/ab_final_2026-10-28/README.md) documents seven audited complete archives. The original 1498804 complete archive remains unavailable.

Shared load, scheduling/frequency, cache/bandwidth/NUMA and MPI progress remain unmeasured explanations. No large-grid pointwise proof, convergence-time benchmark or multi-node PBS validation is claimed; the recorded `libpbs.so.0` warning remains unresolved. No further experiments are planned this round. Phase instrumentation, OpenMP/hybrid, multi-node, weak scaling and two-dimensional decomposition are outside this A/B update.

Remaining work is team review of names/IDs, actual contributions, individual code understanding and the report/figures. These confirmations require the members themselves.

AI disclosure: OpenAI Codex assisted with solver/tooling, checks, audits, analysis, figures and report editing. The user performed Vanda authentication, upload, PBS submission, final-state capture and download.

Evidence: [final index](../evidence/ab_final_2026-10-28/README.md), [scaling/asymmetric analysis](../evidence/vanda_1501884_ab_supplement/analysis_reviewed.md), [diagnostic analysis](../evidence/vanda_1502229_mpi_wait/analysis_reviewed.md).

Figures: [1501884 traces](../evidence/ab_summary_2026-10-28/round_times.png) show nine formal rounds for the displayed P1/4/12 configurations and serial (P2 remains in the CSV); [diagnostic traces](../evidence/vanda_1502229_mpi_wait/round_times.png) show five rounds for all diagnostic configurations. Measurements are sequential. The [historical comparison](../evidence/ab_summary_2026-10-28/historical_context.png) keeps allocations separate; min–max bars are not confidence intervals.