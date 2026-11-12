# B feedback follow-up / 9 November 2026

## Status

> **12 November update:** PBS has recovered. All 39 required follow-up
> configurations (125 formal samples) and four new diagnostics have passed the
> independent audit. Exclusive P1, P72 ablation and both P144 allocations are
> complete; see `../nov12/final_results_20261112/README.md`. Original-host probes
> are queued supplements; the optional 2D extension has also completed. New submissions use
> scheduler-selected hosts with FQDN-normalized exclusions, and the baseline
> runs independently. `--fixed-reference-hosts` reproduces the original Nov9
> request. The design/status below is retained as a historical protocol.


Prepared and locally validated. **No new formal Vanda runtime is claimed.**
SSH access works, but repeated PBS queries on 9 November returned connection
refused / errno 15010. All submission code checks scheduler health first and
refuses to invent job IDs or run a benchmark on the login node.

The November 7 source `b_mpi/jacobi_cart.cpp` and all earlier raw samples remain
unchanged. New experimental code is `jacobi_cart_tuned.cpp`, reproducibly derived
by `prepare_solver.py`.

## Predeclared experiments

| Job | Allocation and workload | Purpose |
|---|---|---|
| clean144 | Nine non-overlapping reference hosts ×16 ranks; 128³/256³/512³ strong, 64³/rank weak, one axis diagnostic | Test pure MPI on a different host set and rank placement |
| paired144 | Four of those reference hosts ×36 cores; full three-size/weak/three-hybrid matrix and axis diagnostic | Repeat the complete 144-core matrix without any old 144 host; supply matched MPI control |
| baseline | One entire exclusive 72-core host, one rank pinned; 128³/256³, one warmup + five formal samples, plus same-core A serial control | Replace the noisy shared P1 baseline only after real measurements; examine baseline gaps |
| optimize72 | One entire exclusive 72-core host; four original layouts and five experimental variants per layout | Separate packing, first writes and persistent-region effects; one warmup + three formal samples |
| suspect_diag | Original four-host layout, one 256³ axis diagnostic | Compare directions/participating ranks in the high-wait setting |
| link_reference / link_suspect | Two ranks, one per host; 8/32768/65536/262144-byte ping-pong, warmup + three windows | Compare CN-003/CN-110 with CN-011/CN-108, without calling it a complete network diagnosis |

The reference set is CN-003/110/126/136/139/141/143/145/146. It is disjoint from
all hosts in both earlier 144-core allocations. Nine hosts with 16 cores each
cannot support the 4×36 thread layout: this is why pure-MPI and full hybrid
jobs are distinct. Each hybrid comparison has its own same-allocation baseline.
If only the nine-host test recovers, host identity is still confounded with
node count/ranks per host. The four-host test and link probes are needed before
attributing the problem to CN-011/CN-108; even then a hardware fault is not
proven uniquely. Actual timings need not be monotonic and no sample is rejected
for being slow. The baseline 5% deviation target is reported, not forced by
selective reruns or deleting samples.

## Experimental variants

- `baseline`: experimental allocation representation, serial initialization,
  serial packing and per-sweep OpenMP entry.
- `parallel_pack`: parallel face pack/unpack only.
- `first_touch`: parallel initialization only, with truly uninitialized `new[]`
  storage so a serial vector zero-fill has not already touched the pages.
- `persistent`: persistent OpenMP team only; MPI remains on the main thread.
- `optimized`: all three changes together.

The original MPI/non-OpenMP and original hybrid binaries are included in the
same job as external references. Compare each optimization against the matched
experimental baseline to avoid attributing compiler/container effects to an
optimization. NUMA means memory access costs depend on placement; parallel
first writes are implemented, but actual physical page distribution is not
independently measured. A rank contained in one socket may gain little.

`rank_axis_seconds` stores x/y/z communication/wait, then x/y/z pack/unpack.
`rank_topology` stores coordinates, low/high neighbors for each axis, and
local dimensions. `rank_hosts` maps rank to host. Report both neighbors of a
Sendrecv axis; its aggregated interval does not uniquely isolate one link.
No inter-rank barrier is added per sweep. Instrumented phase runs are separate
from formal timings. Persistent-team synchronization is included in the timed
work. First-write initialization and all final diagnostics remain outside
iteration timing.

## Local checks (correctness only)

```sh
python3 b_mpi/nov09/prepare_solver.py
mpicxx -std=c++17 -O2 -fopenmp b_mpi/nov09/jacobi_cart_tuned.cpp -o build/jacobi_cart_tuned
python3 b_mpi/nov09/validate_variants.py --binary build/jacobi_cart_tuned --out NEW_LOCAL_CHECK_DIR
```

On this Mac replace -fopenmp with the libomp flags in b_mpi/README.md.
Five variants ×six mathematical/partition/thread cases passed locally; the
maximum oracle error was 7.55e-15. The runner smoke is labelled local-only and
excluded by the analysis. It is not school-cluster performance evidence.

## Cluster operation after PBS recovers

Upload these sources plus the original B source, affinity wrapper, runtime
modules, A serial-scaling source and root module file to a new project folder.
No compilation is performed on a login node. Inspect current node resources,
project balance and requested placements; regenerate with a valid project:

```sh
python3 b_mpi/nov09/make_feedback_jobs.py --project YOUR_PROJECT
python3 b_mpi/nov09/submit_feedback.py --submit
```

The main chain uses afterok dependencies to avoid simultaneous same-user jobs
on overlapping hosts. A failed submission saves a PARTIAL manifest and stops;
it never silently submits duplicate jobs. Every formal invocation saves its
command, requested OpenMP settings, raw JSON/stderr, source/binary hashes,
actual host/core masks and metadata. Baseline A serial is pinned to the actual
core used by MPI P1; compiler vectorization reports are retained internally.

```sh
python3 b_mpi/nov09/collect_feedback.py
python3 b_mpi/nov09/analyze_feedback.py --input results/final_202611/B_nov09 --out results/final_202611/B_nov09/analysis
```

Only completed jobs with independent PBS exit zero, exact repeats, correct
workload/numerics and disjoint allocated CPU masks enter formal summaries.
The analysis produces per-axis rank/host/neighbor tables and ping-pong RTT
ranges. These are not confidence intervals or fitted alpha/beta constants.
Update main scaling/hybrid figures only after these checks; keep the original
144-core points as explicitly labelled historical high-wait observations.

Existing-data explanation tables are generated separately by
`update_existing_analysis.py`. They cover relative weak efficiencies, all
P12/P36 strong points and observed baseline sensitivity. They do not create
new measurements. Optional 432/720-core jobs cannot currently be verified
because PBS is unreachable; their last known state is not treated as current
success. The optional 2D scaling sweep is deferred behind the required checks.
