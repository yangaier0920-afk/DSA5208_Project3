> 2026-11-09 feedback correction: see B_FEEDBACK_ANALYSIS_2026-11-09.md for baseline sensitivity, complete scaling tables and alternative weak references. New disjoint-host/baseline/optimization jobs are prepared but have no accepted result while PBS is unavailable.

# B: Cartesian MPI, hybrid execution and communication

Status, 7 November 2026 (Singapore time): technical closeout is complete.
The report uses 20 scaling configurations and eight paired-layout configuration
occurrences, each with three formal samples: 84 formal samples in total, plus
three communication diagnostics. The main numerical table has 26 configuration
IDs and 78 samples; two additional pure-MPI paired controls supply six samples.
Local and real two-node validation passed. Optional 432/720-core points have no accepted result. They were last known
to be queued; their current status cannot be queried while PBS is unreachable. Author identification and personal
contribution declarations are omitted at the user's request.

## Parallel design

P denotes the MPI rank count, T the OpenMP threads per rank, C=P×T the
physical core count, K the sweep count, and N the total interior unknowns.
A halo is a layer holding neighboring ranks' values.

The manufactured Poisson problem uses a five-point stencil in two dimensions
and a seven-point stencil in three. Nonperiodic Cartesian block decomposition
maps each rank to a rectangular subdomain. Quotient/remainder partitioning
supports nondivisible global dimensions. Each rank stores its own interior,
one halo layer, two solution buffers and the precomputed right-hand side.
Initialization uses global coordinates; Dirichlet boundaries are initialized
in both buffers and never overwritten by communication.

The primary strategy explicitly packs faces and uses blocking MPI_Sendrecv.
Only face neighbors are necessary. The two-dimensional path exchanges four
faces and the three-dimensional path six. Every sweep updates the local
interior from the previous buffer and then swaps buffers. Residual checks
refresh the final halo before evaluating the global residual.

Pure MPI is built without OpenMP. MPI+OpenMP distributes local rows through
static work sharing while keeping MPI calls on the initializing thread;
MPI_THREAD_FUNNELED support and actual team sizes are checked. Threads are
placed within the cores assigned to their rank. This implementation enters a
parallel region every sweep, so its measured cost includes repeated team
entry/synchronization. Fewer ranks can reduce the number of messages but
change face size, NUMA placement and thread overhead simultaneously.

## Validation

The reference is the exact discrete manufactured solution, whose sine
amplitude is the continuous RHS coefficient divided by the discrete stencil
eigenvalue. This separates implementation error from spatial discretization
error. An independent one-sweep check also tests the transient stencil and
boundary contributions before convergence can mask a defect.

| Purpose | Case | Result |
|---|---|---|
| Serial/rank equivalence and face exchange | 7³, P=1 and P=8, K=1000 | PASS |
| Nondivisible ownership and threads | 9×7×5, P=8, T=2, K=1000 | PASS |
| Nonzero 2D RHS | 7², P=2, T=2, K=1000 | PASS |
| One-cell local axes | 2×3×2, P=4, K=1000 | PASS |
| Independent transient stencil | 9×7×5, P=8, T=2, K=1 | PASS |

The six local cases had maximum oracle error 7.55e-15. Vanda job
1529159.stdct-mgmt-02 completed with PBS exit status zero and maximum oracle error
7.11e-15, but actually ran on one node because the MPI PBS plugin could not
load libpbs.so.0. This was detected from the program-reported node count.
Corrected job 1529188.stdct-mgmt-02 passed with exit zero and an explicit
assertion that P=8 used two physical nodes. Its maximum oracle error was
7.11e-15. The fixed environment adds /opt/pbs/lib to LD_LIBRARY_PATH. Boundary error was within 1e-12 and converged discrete-solution error
within 1e-9. A separate local pure-MPI 7³ result agreed with A's serial solver:
identical reported discrete maximum error (2.72e-15) and global L2 residuals
differing by approximately 1.10e-14. These checks establish numerical
correctness, not the performance of large configurations.

## Experimental method and acceptance

Every performance case fixes K=1000, performs one warmup and retains three
fresh-start measurements. Report median and actual min/max. Iteration time
includes halo packing/exchange, local updates, OpenMP synchronization where
applicable and buffer swaps. The maximum rank duration is reported. Setup,
initial/final residual, final verification and file output are excluded.
No per-sweep residual reduction is performed. Fixed iteration count does
not imply convergence.

B1 covers 128³ and 256³ at P=1/12/36/72/144/288, and 512³ at
P=72/144/288/720. B2 fixes 64³ points per rank at
P=1/8/72/144/288/432/720. B3 compares four rank/thread layouts at each of
72 and 144 total cores on 256³. B4 records one separate stage diagnostic at
P=72/144/288. Actual resource layout is recorded per job. The 144- and
288-core jobs request four 36-core nodes / nine 32-core nodes to use fragmented capacity.
The final scaling P72 point uses three 24-core allocations in the same host
memory-capacity class; its separate hybrid comparison retains the original
single-node allocation and its own paired MPI baseline.

For strong scaling, S(P)=T(1)/T(P) and E(P)=S(P)/P. The 512³ series uses
S72(P)=T(72)/T(P) and E72(P)=S72(P)/(P/72), explicitly relative to 72 cores.
Weak efficiency is Ew(P)=Tweak(1)/Tweak(P); local work is fixed but the global
mesh and its spacing change. Hybrid layout improvement at total core count C
is G=T_MPI(C)/T_hybrid(P,T), with C=P×T. Node placement must be matched and
reported when interpreting this comparison.

Before accepting results, check actual hardware, rank/core binding, node and
thread counts, K, finite metrics, boundary values, source/compiler identity,
cross-layout numerical agreement, three retained samples and successful PBS
completion. CPU models must match across each plotted curve. Submission and
resource allocation alone do not satisfy the >=256-core requirement.

## Communication model and planned interpretation

For an interior local domain lx×ly×lz with six neighbors, outgoing face data
per sweep are Vsend=8(2lylz+2lxlz+2lxly) bytes in double precision. Faces
without a physical neighbor are subtracted. This counts sent bytes once;
receives contribute an equal volume. A qualitative per-sweep model is

T ≈ γ lx ly lz + α m + β Vsend + Tpack + Tsync.

Here m is the number of outgoing messages, α the message latency contribution,
β the transfer cost per byte and γ the local update cost per point. These
parameters are explanatory and are not fitted network microbenchmarks.
At fixed global size, local computation decreases as N/P, whereas near-cubic
face area decreases as (N/P)^(2/3); relative communication exposure therefore
grows. At fixed local work, face dimensions are nearly constant, but neighbor
counts, network contention and the fraction of remote neighbors can change.

Diagnostic timers separate local updates, packing/unpacking, blocking
communication/wait and swaps. Use all components from the rank with the
largest total duration, and separately report the spread of rank totals.
Independent maxima from different ranks cannot be added. Communication
intervals include waiting for slower peers and are not pure network time.
Timer/loop overhead remains visible as uninstrumented time; diagnostic
samples do not replace performance measurements.

## Measured scaling and hybrid results

### Cohort definition and provenance

All accepted CPU models are Xeon Platinum 8452Y, two 36-core sockets and SMT
off. Primary scaling now matches the nominal 512-GB host capacity class
(approximately 501 GB scheduler-advertised memory), checked against the node
catalogue and CPU metadata. Actual node counts are 1 at P1/8/12/36, 3 at P72,
4 at P144 and 9 at P288. Node placement and shared-system load still vary;
matching capacity class is not proof that all system conditions are identical.

The single-node 72-core hybrid comparison remains on CN-162, a larger-memory
host, and uses only its own MPI control. The final 144-core hybrid comparison
uses the controlled review allocation, with explicit remote OpenMP environment
propagation and actual OS masks. Its MPI control is separate from the original
P144 main-curve point. These paired denominators must not be replaced by the
main scaling CSV's P72/P144 times. `hybrid_summary.csv` contains all eight
paired configurations and explicitly records their control times/cohorts.

All original mixed-capacity results, the original slow 144-core observations,
and earlier hybrid results remain in the legacy cohort. New sources were
selected for the planned hardware/affinity review, not according to speed.
The original P144 scaling samples remain in the main curve.

### Strong scaling

For 128³, the standardized P72 median is 0.337059 s (speedup 14.867, efficiency 20.65%). P288 takes 0.294310 s (speedup 17.026, efficiency 5.91%). The small-grid and large-grid efficiencies differ substantially.

For 256³, the standardized P72 median is 1.238393 s (speedup 36.761, efficiency 51.06%). P288 takes 0.632244 s (speedup 72.005, efficiency 25.00%). The small-grid and large-grid efficiencies differ substantially.

The original 256³/P144 median is 13.854904 s, with range
[12.601303, 14.110585] s. It is retained even though the
curve is nonmonotonic. The four-host repeat sharing CN-011 and CN-108 with the original allocation gives
14.113334 s, range [13.825400, 14.342317] s.
The host sets partly overlap and conditions are shared; this reproduces high
waiting in the tested allocations, but does not establish a universal
intrinsic defect at exactly 144 ranks or identify a unique root cause.

For 512³, the P72 baseline is 9.755425 s on three hosts.
P288 takes 3.273120 s, giving S72=2.980 and
E72=74.51%. This is relative-to-72 scaling, not
speedup relative to one rank. The 720-core point remains omitted.

### Weak scaling

Each rank owns 64³ interior points. The global domain remains the unit cube,
so grid spacing and the discrete problem change with P. The controlled
quantity is point-update work per rank, not precision or equal solution time.

| P | Nodes | ms per sweep | Weak efficiency T1/TP |
|---:|---:|---:|---:|
| 1 | 1 | 0.392329 | 100.00% |
| 8 | 1 | 0.862284 | 45.50% |
| 72 | 3 | 1.372183 | 28.59% |
| 144 | 4 | 13.575610 | 2.89% |
| 288 | 9 | 1.911628 | 20.52% |

The fixed local work does not keep time constant. Neighbor counts, cross-node
messages, shared-memory resources and scheduling can change. The P144 anomaly
is retained in both strong and weak curves; phase evidence helps locate the
loss but cannot isolate all system causes.

### Paired MPI+OpenMP layouts

| Total cores | P×T | Nodes | Median [min, max] seconds | Paired MPI / time |
|---:|---|---:|---:|---:|
| 72 | 72×1 | 1 | 1.441737 [1.437858, 1.544236] | 1.000 |
| 72 | 12×6 | 1 | 1.812523 [1.804147, 1.853521] | 0.795 |
| 72 | 6×12 | 1 | 1.628238 [1.614789, 1.628980] | 0.885 |
| 72 | 2×36 | 1 | 1.973561 [1.972097, 2.014452] | 0.731 |
| 144 | 144×1 | 4 | 14.113334 [13.825400, 14.342317] | 1.000 |
| 144 | 24×6 | 4 | 6.957972 [6.698904, 7.652053] | 2.028 |
| 144 | 12×12 | 4 | 7.393277 [7.245681, 7.698748] | 1.909 |
| 144 | 4×36 | 4 | 7.874100 [7.437435, 9.007569] | 1.792 |

At 72 cores, all three hybrids are slower than the single-node paired MPI
control; even the best hybrid minimum exceeds the MPI maximum. At 144 cores
in the earlier high-wait allocation, all three mixed layouts are
faster than its paired MPI control (gains approximately 1.79–2.03), and their
ranges do not overlap that MPI range. Three samples are not a confidence
interval or a guarantee on a different allocation.

The earlier 144-core hybrid cohort had different outcomes and remains in the
legacy tables. The review changes remote environment propagation and host
placement/system state together; differences cannot be assigned to affinity
alone. Reducing ranks changes messages, subdomains and cache/NUMA sharing as
well as adding threads, so no single cause is quantitatively isolated.

### Communication/wait diagnostics

Each row below uses all phases from the rank with the largest total duration;
no independent per-phase maxima from other ranks are added. The three
instrumented runs are separate from formal performance medians.

| P | Nodes | Total s | Update s | Pack/unpack s | Communication/wait s | Wait fraction |
|---:|---:|---:|---:|---:|---:|---:|
| 72 | 3 | 1.172958 | 0.651368 | 0.120575 | 0.399991 | 34.10% |
| 144 | 4 | 14.042913 | 0.240497 | 0.084609 | 13.716785 | 97.68% |
| 288 | 9 | 0.628623 | 0.134376 | 0.053438 | 0.439661 | 69.94% |

The large original P144 waiting interval persists in the overlapping-node repeat.
It is a blocking communication/wait interval, not pure wire time; rank
scheduling, communication progress and fabric conditions can contribute.
The cost model explains relative exposure as local domains shrink, but does
not explain the nonmonotonic point by core count alone. Timer overhead and
small uninstrumented intervals remain in the full diagnostic CSV.

### Audit, numerical consistency and limits

The supplemental 63 calls, including warmups and diagnostics, passed actual
OS CPU-mask size, allocation-subset and per-host nonoverlap checks for every
rank. Explicit -x propagation carries OpenMP settings and runtime paths to
remote workers. One-rank/whole-allocation PE=36 cases are thereby verified
rather than relying only on Open MPI's all-available-processors message.
The manufactured solution, K, source hash, finite metrics, boundary values,
actual ranks/threads/hosts and residual agreement are checked independently.

Earlier completed samples from an interrupted 288-core attempt remain in the
legacy evidence. A failed startup has no accepted result. No valid slow
sample was removed because of its speed. The standardized cohort is a
separate documented experiment; it is not an undocumented replacement of
individual observations in the old cohort.

Figures and concise CSVs are under `results/final_202611/B_mpi/analysis/`.
The integrated report uses `closeout/figures/`; these regenerate from numerical
CSV, not terminal logs. Strong and weak curves use logarithmic CPU/time axes;
efficiency is linear in percent, and min/max reflect all three formal samples.

### Overall design discussion

MPI makes distributed ownership and halo dependency explicit. OpenMP shares
the local work over assigned cores but can change message count, memory
sharing and synchronization costs. C's GPU uses a different device memory
space; its own paired CPU/GPU baselines must remain within C's allocation.
The study uses synthetic MMS inputs and makes no real-data inference.

## Reproduction and AI usage

Implementation, commands, PBS generation and measurement details are in
`b_mpi/README.md`. The exact submitted job IDs and resource changes are in
`b_mpi/jobs_submitted.json`. Internal evidence is under
`results/final_202611/B_mpi/`; do not include logs or terminal transcripts in
the final submission archive.

AI assisted implementation, independent checking, experiment tooling and
this draft. The member must review the code and findings and fill in their
own name, student ID and actual contribution. No personal understanding or
member sign-off is asserted here.

## Qualification after the 9 November feedback

The two earlier four-node allocations share CN-011 and CN-108 and are not
independent with respect to node identity. Their mixed-layout gains are
conditional on a high-wait MPI reference; a healthy-platform benefit is not
established. New disjoint-node nine-host pure MPI and four-host full-layout
experiments are separate, with their own baselines. Directional diagnostics
report both neighbors participating in each axis's Sendrecv calls; a large
interval does not uniquely identify one faulty physical link.

Parallel packing, genuine parallel first writes to uninitialized allocations,
a persistent OpenMP region and their combination are implemented in a separate
experimental source. The original measured source remains unchanged. An
aligned experimental baseline separates allocation/container/compiler effects
from the individual optimization switches. Thirty local mathematical checks
pass across the five variants, but no cluster speedup is claimed without
completed cluster measurements. In particular, ranks confined to one NUMA
socket may show little first-touch benefit; page placement has not been
independently measured.
