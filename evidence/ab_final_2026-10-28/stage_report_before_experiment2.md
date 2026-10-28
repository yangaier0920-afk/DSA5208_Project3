# DSA5208 Project 3: A/B Progress Report

Draft for human review, 28 October 2026. Not sent. Scope: serial baseline and correctness (A), pure MPI (B). Member names, student IDs, actual contributions and individual understanding must be checked by the team before sharing.

## Implementation and measurement

We implemented double-precision Jacobi iteration for the two-dimensional Laplace equation on a unit square. The performance problem uses fixed boundary values u=x+y and a zero interior initial state. Each MPI rank owns a contiguous row block and two halo rows; the first n mod P ranks receive one extra row. Non-divisible partitions are supported, and P>n is rejected.

The blocking scheme exchanges halos with MPI_Sendrecv before updating. The nonblocking scheme posts receives and sends, computes interior rows, waits, and then updates boundary rows, including one-row and two-row partitions. Positive-tolerance runs use a global maximum update for synchronized stopping. Performance runs fix K=1000 and tolerance=0; they do not measure time to convergence.

All reported performance jobs used one Vanda node, 12 CPUs/4GB, GCC 12.2.0, OpenMPI 4.1.5 and -std=c++17 -O2 -Wall -Wextra -Wpedantic, without OpenMP. Timers cover the iteration region, including required communication and reductions, and report the maximum rank time. Initialization, final error/residual checks, grid gathering, process startup and output are excluded.

## Serial baseline

Two controlled diagnostic jobs investigated an approximately twofold advantage of MPI P=1 over the original serial code. In job 1499842, median times were 3.496400s for the original serial code, 3.469020s for an iteration-local reduction candidate, 1.723135s for the row-local reduction candidate, and 1.746897s for MPI P=1. Controlled changes and Linux disassembly support per-point stack traffic for the original maximum-update reduction as the main source of this difference in that environment. This was not a vectorization improvement and is not a general claim about other platforms.

Subsequent measurements use jacobi_serial_row_update.cpp. Original source and historical results remain unchanged; new serial times are never combined with parallel times from older jobs.

## Correctness evidence

Each of four audited MPI jobs contains the same structured validation suite: 88 numerical executions and four expected input rejections. Across these suites, 172 executions include complete small grids compared with an independent Python reference. Large performance grids are checked for workload and matching global metrics, not pointwise equality.

Job 1501884 added an independent asymmetric problem, u=x+2y+xy, with x as column coordinate and y as row coordinate. This harmonic function helps distinguish coordinate and boundary swaps. All 31 serial/MPI executions passed full-grid and independent metric checks, covering non-divisible partitions, one/two rows per rank, both communication schemes and positive-tolerance stopping. The largest pointwise difference was 8.88e-16. All seven n=7 convergence configurations stopped after 330 iterations, with maximum analytic error 1.25e-11 and residual infinity norm 2.52e-10. These small-grid thresholds are not extrapolated to large grids.

For n=1024/2048, K=1000 remains far from convergence: maximum analytic errors are approximately 1.859/1.925. The global metrics match the corresponding historical runs.

## Performance results and the new controlled comparison

Each dataset has nine configurations: serial, plus MPI P=1/2/4/12 using both schemes. Each configuration has one warmup and nine formal measurements. Speedup is the ratio of medians relative to that dataset's own serial baseline. Same-strategy MPI P=1 speedups are also retained in the accompanying tables. No samples were removed.

| Job / node | n | Serial median (s) | P=12 SR / OV (s) | Speedup vs own serial SR / OV |
|---|---:|---:|---:|---:|
| 1499881 / IN-006 | 1024 | 2.066070 | 0.224262 / 0.216749 | 9.213 / 9.532 |
| 1500271 / IN-003 | 1024 | 1.527579 | 0.217869 / 0.217064 | 7.011 / 7.037 |
| 1500222 / IN-003 | 2048 | 6.842698 | 1.168184 / 1.166647 | 5.858 / 5.865 |
| 1501884 / IN-005 | 1024 | 1.749200 | 3.101710 / 0.991551 | 0.564 / 1.764 |
| 1501884 / IN-005 | 2048 | 7.650589 | 4.192806 / 2.828012 | 1.825 / 2.705 |


The first three jobs showed decreasing median runtime as P increased. The latest job tested both sizes within one allocation, using one pair of performance binaries and a fixed CPU/rank mapping. Scale blocks alternated order between formal rounds, while configuration order rotated within each scale. Every configuration covered nine within-scale positions; nine rounds do not balance all eighteen cross-scale positions.

The latest data show substantial time variation. For n=1024/P=12/sendrecv, r0–r4 took 3.102–3.504s, while r5–r8 took 0.213–0.224s. Serial and MPI P=1 instead became slower later in the job. Thus, the latest n=1024 median runtime does not decrease monotonically with P; P=12/sendrecv is slower than its own serial baseline. The unfavorable result is retained alongside all earlier jobs. The performance source files and binaries match the historical versions exactly, so a program-version change does not explain the difference.

![All formal samples from the latest allocation](../evidence/ab_summary_2026-10-28/round_times.png)

## Communication interpretation and remaining limits

For n=2048/P=2, overlap reduced the ratio-of-medians runtime by 14.01% in the latest job and was faster in 7/9 rounds, compared with 16.61% and 9/9 in the earlier 2048 job. The direction reappeared, but its consistency and magnitude differ. At n=1024/P=2, overlap was 1.45% slower by the same median-based measure.

The latest P=12 reductions of 68.03% (1024) and 32.55% (2048) accompany strong chronological variation. They are descriptive differences between medians, not measured overlap fractions. For comparison, the medians of per-round percentage reductions are 22.79% and 4.85%, respectively; these are different statistics. Sequential same-round comparisons do not eliminate time-varying conditions.

The same-allocation design controls binaries and CPU mapping more closely than cross-job comparisons, but does not isolate a pure problem-size effect. Shared-node interference, scheduling/frequency changes, memory/cache/NUMA effects and MPI progress remain unmeasured explanations. We have not established effective underlying communication overlap or universal superiority of the nonblocking scheme.

## Current stopping point and next work

The latest raw archive contains 646 files, checked member by member. Source/binary hashes, all structured numerical records, 180 performance executions, 780 pre-exec affinity records, execution order and recomputed statistics passed audit. The libpbs.so.0 warning remains recorded; successful single-node runs do not validate multi-node PBS integration. The complete original archive for job 1498804 is still unavailable.

The two priority supplementary experiments are complete. A bounded nonblocking-immediate-wait diagnostic has now been prepared for n=2048/P=2, n=2048/P=12 and n=1024/P=12, with five formal measurements per scheme. Its cluster execution and results are pending, so the tables above still cover only the four audited jobs. Optional phase instrumentation is omitted. After this diagnostic we will return to the report and human review, retaining inconclusive outcomes without automatic reruns. OpenMP/hybrid work, multi-node runs, weak scaling and two-dimensional decomposition remain outside the present A/B scope.

AI disclosure: OpenAI Codex assisted with solver/tooling code, experimental preparation, local checks, raw-data audits, analysis and figures. The user performed Vanda authentication, upload, PBS submission and download. The team must verify actual individual contributions and code understanding before sharing this draft. No email was sent and no Git commit/push was made.

Evidence: [reviewed Chinese analysis](../evidence/vanda_1501884_ab_supplement/analysis_reviewed.md), [all datasets and exact CSVs](../evidence/ab_summary_2026-10-28/README.md).
