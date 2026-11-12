> **12 November 2026:** the required B feedback suite is complete and audited.
> See [final results and raw evidence](nov12/final_results_20261112/README.md),
> [the revised B chapter](../docs/final_B_mpi.md), and
> [reproduction instructions](nov12/README.md). The original `jacobi_cart.cpp`
> remains frozen. Experimental variants are in `nov09/jacobi_cart_tuned.cpp`;
> use an explicit `--variant` (the packing-only treatment has the clearest
> measured benefit). Historical instructions and observations below are retained.

> 2026-11-07 技术收尾：主扩展曲线改为同 CPU/内存容量族；P72/P144/P288 实际为 3/4/9 主机。混合配比独立成对，不能从主曲线换用分母。20 组扩展加 8 组成对比较，共 84 次正式样本；主表 26 个 ID 的 78 次与配对专用基准 6 次分开记录。最新章节和合稿见 docs/final_B_mpi.md、docs/final_report_review.md。

# Member B: Cartesian MPI and MPI+OpenMP experiments

This directory implements the 2026-11-03 plan. The older root-level
`jacobi_mpi.cpp` is the historical 2D Laplace solver and is unchanged.

## Build and validation

On Vanda compute nodes, source `b_mpi/runtime_modules.sh` from the project root.
On a GNU/Open MPI compute node, `make b-mpi` builds both executables.
Equivalent explicit commands:

```sh
mkdir -p build
mpicxx -std=c++17 -O2 -Wall -Wextra -Wpedantic b_mpi/jacobi_cart.cpp -o build/jacobi_cart_mpi
mpicxx -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp b_mpi/jacobi_cart.cpp -o build/jacobi_cart_hybrid
python3 b_mpi/verify_b.py --binary build/jacobi_cart_hybrid --launcher 'mpirun --bind-to none' --out results/B_validation_NEW
```

On this Mac, replace `-fopenmp` with
`-Xpreprocessor -fopenmp -I/opt/homebrew/opt/libomp/include -L/opt/homebrew/opt/libomp/lib -lomp`.
Use `--launcher 'mpirun --oversubscribe --bind-to none'` only for local validation.
The validation output directory must not exist.

The solver accepts `--dim 2|3 --nx N --ny N --nz N --px P --py P --pz P
--iterations K --diagnostic 0|1`. The process-grid product must match MPI size;
empty subdomains are rejected. In 2D, pz=1 and nz is internally one layer.
`--grid PREFIX` saves interior values in one CSV per rank, outside timing.

MMS problems and boundary/RHS match the meeting plan: the linear term is
x+2y (+3z), and sine frequencies are (1,2) or (1,2,3).
Validation uses the independent discrete sine eigenvalue, including a separate
one-step oracle to expose errors hidden by eventual convergence. Cases cover
7³ with P=1 and P=8, uneven 9×7×5 with P=8/T=2, 2D 7² with P=2/T=2,
and thin local domains. The validation PBS job spreads P=8 across two nodes.

## Design and timing

Nonperiodic Cartesian block partitioning gives each rank its local interior
and a one-cell halo. Each dimension uses quotient/remainder ownership and
initializes from global coordinates. Six 3D faces (four 2D faces) are packed
explicitly; edges/corners are unnecessary for the stencil. Two blocking
MPI_Sendrecv calls per axis exchange the old solution. MPI_PROC_NULL preserves
physical boundaries. Two solution arrays and a precomputed RHS are allocated.

All MPI calls are on the main thread. The hybrid executable requests and checks
MPI_THREAD_FUNNELED; its local update uses static OpenMP work sharing. The pure
MPI executable is compiled without OpenMP and is used for every T=1 formal
configuration. Hybrid thread count is measured and checked on every rank.
Repeated fork/join is an implementation cost included in hybrid timing.

The timer starts after a barrier and covers K=1000 halo/update/swap iterations.
The reported time is the maximum rank duration. There is no per-iteration
residual reduction or barrier. Initial/final residual, final halo refresh,
error checks, output and rank timing collection are outside the timer.
`relative_residual` is the global L2 residual divided by its initial value.
Fixed work is not a convergence claim. Large-grid discrete error need not be
small after only 1000 iterations.

Diagnostics use the same algorithm with additional timers for update,
pack/unpack, blocking communication/wait and buffer swap. `rank_timings` rows
are `[total, update, pack_unpack, communication_wait, swap]`, indexed by rank.
Uninstrumented loop/timer costs are total minus the component sum. Analyze the
components of the slowest total-time rank together; never add independent
rank maxima. Blocking communication includes waiting for peers and does not
measure pure network transmission. Diagnostic runs are separate from formal
samples and have timer overhead.

## Formal matrix and PBS

`run_b.py:matrix()` is the source of the planned 29 performance configurations
(16 strong, seven weak, six extra hybrid layouts) and three diagnostics.
Every performance configuration has one warmup and three retained samples,
with configuration order rotated between rounds. Each sample starts a fresh
process. Diagnostics run once without a warmup, as specified in the plan.

```sh
python3 b_mpi/make_jobs.py
qsub b_mpi/jobs/b_validate.pbs
# After validation, submit the required resource groups:
qsub b_mpi/jobs/b_288.pbs
qsub b_mpi/jobs/b_1.pbs
qsub b_mpi/jobs/b_72.pbs
# Remaining groups: 144, 12, 36, 8, 432, 720.
```

The current project is `personal-e1561365`. The free CPU queue caps jobs at
160 cores, so it cannot deliver the required >=256-core result. Check current
project balance and queue limits before reuse. Compile only on compute nodes.
Current formal jobs use project CPU nodes and save actual topology and CPU
model. Allocation changes made after submission are in `jobs_submitted.json`;
PBS's actual qstat record is authoritative. A single-node 72-core allocation
is retained for the core hybrid comparison. The 144/288-core groups can use
four 36-core nodes / nine 32-core nodes when whole nodes are unavailable. This changes
cross-node communication and must be described in the report.

The driver discovers actual hosts from PBS_NODEFILE and maps ranks with
`--hostfile "$PBS_NODEFILE" --mca ras ^tm --mca plm rsh` and
`ppr:ranks_per_host:node:PE=threads --bind-to core`. It checks actual ranks,
threads and node count, and saves every command, OpenMP environment, binding
stderr, raw JSON, source/binary hashes, source snapshot and hardware probes.
No CPU oversubscription is enabled for formal experiments. Per-host hardware
must match within a group. Compare CPU models and compiler flags across groups
before merging a curve. Runtime slowdown is not a reason to discard a sample.

## Analysis and handoff

Download the complete job directory into `results/final_202611/B_mpi/`, retaining
its original directory name. Preserve final qstat and PBS exit status too.

```sh
python3 b_mpi/analyze_b.py --input results/final_202611/B_mpi --out results/final_202611/B_mpi/analysis
```

Analysis excludes local/smoke/warmup samples and incomplete configurations.
A completed individual sample from an interrupted job may be retained if
the launcher returned zero, the solver JSON and binding pass audit, and
source/hardware/workload match. A later independent startup failure does
not invalidate earlier successful measurements. Resume runs preserve their
repeat numbers, add a fresh warmup on the new allocation, and fill only
missing samples; allocation changes remain documented. It requires
three unique repeats and K=1000. Check hardware, PBS exit status, binding and
cross-configuration residual agreement as part of acceptance. CSV and figures
show median/min/max. Strong scaling uses MPI P1 except 512³, whose baseline is
P72. Weak efficiency is T1/TP, without dividing by P. Hybrid layout improvement
is the equal-total-core pure-MPI time divided by hybrid time. The script does
not invent a value if a baseline or formal data is missing.

`docs/final_B_mpi.md` records the actual state and report material. Do not call
queued jobs completed experiments. Internal logs and raw job folders must be
excluded from the final submission package; submit source, README, necessary
PBS/analysis scripts, concise numeric CSV and report figures only.

Site launch diagnostic: adding /opt/pbs/lib enables the PBS plugins and fixed
real two-node validation, but a separate CN-152 hello test showed that TM
launch plus core binding stalls (timeout 124), while explicit PBS hostfile
with the rsh launcher and the same core binding exits zero. Formal runs use
the latter launcher, restricted to allocated hosts; failed startup jobs have
no accepted samples and remain documented in the manifest.

Job 1529209 encountered hwloc_set_cpubind bitmap 0 on GN-A40-079 during
512³/P288 repeat 2, before the application launched. The failed attempt has
no accepted record. Earlier valid samples and the diagnostic are retained;
1529218 supplements only missing formal samples on matching CPU hardware.

To reproduce figures from the concise CSV without raw logs:

```sh
python3 b_mpi/plot_b.py --csv results/final_202611/B_mpi/analysis/summary.csv --out reproduced_figures
```

Matplotlib is required locally for plotting. The pure numerical runners need
only Python's standard library. `package_b.py` builds a source/report/figure
whitelist ZIP and excludes raw logs, qstat, executables and terminal output.

## Closeout cohorts and reconstruction

`closeout/prepare_cohorts.py` selects sources by the predeclared memory/affinity review, not runtime. Main scaling uses the nominal 512-GB host class; the original 144-core slow series is retained and an independent review is separate. The original mixed-capacity results remain under `results/final_202611/B_mpi_legacy_analysis_20261107` and raw job folders.

The paired `hybrid_summary.csv` has eight rows, including pure-MPI controls for each allocation. Its 72-core single-host and 144-core four-host control medians are independent of the primary scaling curve. `plot_b.py` automatically reads an adjacent hybrid_summary.csv, or accepts `--paired-csv PATH`. For the integrated figures use `python3 closeout/plot_report.py`.

The additional Linux-only `exec_affinity.py` records every rank's actual OS mask before the numerical binary, outside timing. Formal launches explicitly export OpenMP settings, PATH and LD_LIBRARY_PATH to remote workers. The closeout audit verifies mask size, subset of allocated CPU masks and per-host nonoverlap for 63 supplementary calls, including warmups and diagnostics.
