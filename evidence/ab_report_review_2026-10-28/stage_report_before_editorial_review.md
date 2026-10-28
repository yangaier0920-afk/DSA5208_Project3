# DSA5208 Project 3: A/B Progress Report

Draft for human review, 28 October 2026. Not sent. Scope: serial baseline and correctness (A), pure MPI (B). Team names, student IDs, actual contributions and individual code understanding require human confirmation.

## Implementation and measurement

We implemented double-precision Jacobi iteration for the two-dimensional Laplace equation on a unit square. Performance runs use boundary values u=x+y and a zero interior initial state. MPI ranks own contiguous row blocks and two halo rows; the first n mod P ranks receive one extra row. Non-divisible partitions are supported, and P>n is rejected.

The blocking scheme exchanges halos with MPI_Sendrecv before updating. The nonblocking scheme posts receives/sends, computes interior rows, waits, then updates the first/last local rows, including one-row and two-row cases. Positive-tolerance runs use a global maximum update for synchronized stopping. Performance runs fix K=1000 and tolerance=0; they do not measure time to convergence.

All performance jobs used one Vanda node, 12 CPUs/4GB, GCC 12.2.0, OpenMPI 4.1.5 and -std=c++17 -O2 -Wall -Wextra -Wpedantic, without OpenMP. Timers cover iteration-region communication, computation and required reductions, reporting the maximum rank time. Initialization, final checks, gathering, process startup and output are excluded.

## Serial baseline and correctness

Two controlled jobs investigated an approximately twofold MPI P=1 advantage over the original serial code. In job 1499842, median times were 3.496400s (original serial), 3.469020s (iteration-local reduction), 1.723135s (row-local reduction) and 1.746897s (MPI P=1). Controlled changes and Linux disassembly support per-point stack traffic for the original maximum-update reduction as the main source in that environment, rather than vectorization. Subsequent runs use jacobi_serial_row_update.cpp; old source/results remain unchanged, and new serial times never replace old-job baselines.

Four scaling jobs each passed 88 numerical executions and four expected rejections, including 172 total full-grid comparisons with independent small-grid Python references. Large performance grids are checked for workload and global metrics, not pointwise equality.

Job 1501884 added the asymmetric harmonic problem u=x+2y+xy, with x as column coordinate and y as row coordinate. All 31 serial/MPI executions passed, covering unequal partitions, one/two rows per rank, both schemes and stopping. Maximum pointwise difference was 8.88e-16. All seven n=7 convergence configurations stopped after 330 iterations, with analytic error 1.25e-11 and residual infinity norm 2.52e-10. These thresholds are not extrapolated to large grids. At K=1000, the original performance problems still have analytic errors about 1.859/1.925 for n=1024/2048.

## Scaling results and variability

SR and OV denote sendrecv and overlap, respectively. Each scaling dataset has nine configurations, one warmup and nine formal measurements per configuration. Speedup is the ratio of medians relative to that dataset's own serial baseline. Same-strategy MPI P=1 speedups are also retained separately. All samples are kept.

| Job / node | n | Serial median (s) | P12 SR / OV (s) | Speedup vs own serial SR / OV |
|---|---:|---:|---:|---:|
| 1499881 / IN-006 | 1024 | 2.066070 | 0.224262 / 0.216749 | 9.213 / 9.532 |
| 1500271 / IN-003 | 1024 | 1.527579 | 0.217869 / 0.217064 | 7.011 / 7.037 |
| 1500222 / IN-003 | 2048 | 6.842698 | 1.168184 / 1.166647 | 5.858 / 5.865 |
| 1501884 / IN-005 | 1024 | 1.749200 | 3.101710 / 0.991551 | 0.564 / 1.764 |
| 1501884 / IN-005 | 2048 | 7.650589 | 4.192806 / 2.828012 | 1.825 / 2.705 |


The first three jobs showed decreasing median runtime with increasing P. Job 1501884 tested both sizes within one allocation and fixed CPU/rank mapping, alternating scale-block order and rotating configurations. Each configuration covered nine within-scale positions; nine rounds do not balance all eighteen global positions.

However, its n=1024/P12/sendrecv times changed from 3.102–3.504s in r0–r4 to 0.213–0.224s in r5–r8, while serial and P1 became slower later. The resulting n=1024 median scaling is not monotonic, and P12/sendrecv is slower than its serial baseline. These unfavorable results remain included. Production source and binaries match earlier versions, so version changes do not explain that variability. Same allocation and fixed mapping do not guarantee stable runtime.

![All formal samples in job 1501884](../evidence/ab_summary_2026-10-28/round_times.png)

## Completed wait-placement diagnostic

Job 1502229 ran an independent, uninstrumented diagnostic at the three specified configurations. It compares blocking sendrecv, nonblocking communication with immediate Waitall (IM), and nonblocking communication with interior computation before Waitall (OV). IM and OV share numerical work, partitioning and interior/edge computation order; only wait placement changes. SR versus IM additionally changes update ordering/partitioning and possibly code generation, so it is not a pure API-cost comparison.

All 45 correctness executions passed before timing, including 18 production and 27 diagnostic runs. Of these, 35 output complete small grids; the other 10 use independent global metrics at n=12/24. Maximum pointwise difference was 2.22e-16, and five original-problem n=7 convergence configurations stopped after 324 iterations. This differs from the asymmetric case above.

Performance uses the diagnostic binary only: each combination/scheme has one warmup and five formal measurements. Triplets run adjacently with rotating order. Five rounds give one or two observations per position, not exact balance.

| n / P | SR median (s) | IM median (s) | OV median (s) | OV reduction vs IM | OV faster rounds |
|---|---:|---:|---:|---:|---:|
| 2048 / 2 | 4.434342 | 4.399289 | 4.406850 | -0.17% | 2/5 |
| 2048 / 12 | 1.285498 | 1.263220 | 1.250628 | +1.00% | 4/5 |
| 1024 / 12 | 0.221087 | 0.219135 | 0.216518 | +1.19% | 4/5 |


At 2048/P2, OV showed no clear advantage over IM: its median was 0.17% higher and it won 2/5 rounds. OV was only 0.62% faster than diagnostic SR by the ratio of medians. One SR sample was 5.331092s versus 4.420–4.458s for the other four; it passed workload/numerical/affinity checks and remains included.

At P12, OV was about 1.00% and 1.19% faster than IM by the ratio of medians, winning 4/5 rounds in both cases. These are small observed scheduling differences from one allocation and five rounds; statistical significance and effective underlying communication overlap have not been established.

Earlier production 2048/P2 jobs reported 16.61% and 14.01% SR-to-OV reductions. The new diagnostic does not substantiate attributing those large differences to early interior computation. It is not an exact production-binary performance repeat, and allocation/time also differ; it neither invalidates the historical raw data nor identifies their cause. Production and diagnostic samples/baselines remain separate.

![All diagnostic formal samples](../evidence/vanda_1502229_mpi_wait/round_times.png)

## Evidence, limitations and stopping point

All three supplementary experiments are complete. Job 1501884's 646-file archive and job 1502229's 222-file archive were verified member by member, alongside all structured JSON, hashes, workload, execution-order and binding records. The latter includes 45 checks, 54 performance executions and 673 pre-exec bindings; PBS finished with exit 0 in 4m45s.

A local audit initially rejected three CV values differing by at most 2.22e-16 between Python environments. Only derived CV comparison now uses a strict rounding tolerance; raw timings, medians, samples and comparison records remain exact. Raw files and cluster code were unchanged, and no cluster rerun occurred.

No samples or entire jobs were discarded. Shared-node interference, scheduling/frequency, memory/cache/NUMA effects and MPI progress remain unmeasured explanations. No large-grid pointwise proof, convergence-time benchmark, multi-node PBS validation or universal overlap benefit is claimed. The libpbs.so.0 warning remains recorded, and the complete original 1498804 archive is still unavailable.

We will now finalize the report and human review, without further experiments for this round. Phase instrumentation, OpenMP/hybrid work, multi-node runs, weak scaling and two-dimensional decomposition remain outside this A/B update.

AI disclosure: OpenAI Codex assisted with solver/tooling, preparation, local checks, audits, analysis and figures. The user performed Vanda authentication, upload, PBS submission, final-state capture and download. Actual team contributions and code understanding require human verification. No email was sent and no Git commit/push was made.

Evidence: [final evidence index](../evidence/ab_final_2026-10-28/README.md), [diagnostic analysis](../evidence/vanda_1502229_mpi_wait/analysis_reviewed.md), [scaling and asymmetric analysis](../evidence/vanda_1501884_ab_supplement/analysis_reviewed.md).
