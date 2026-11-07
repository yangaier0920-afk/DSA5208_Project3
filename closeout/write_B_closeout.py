import csv,json,pathlib
P=pathlib.Path;root=P('results/final_202611/B_mpi');rows=list(csv.DictReader((root/'analysis/summary.csv').open()));hyb=list(csv.DictReader(P('closeout/hybrid_summary.csv').open()));diag=list(csv.DictReader((root/'analysis/diagnostics.csv').open()));review=list(csv.DictReader(P('closeout/review144/summary.csv').open()))[0]
def find(n,p):return next(r for r in rows if r['suite']=='strong' and int(r['nx'])==n and int(r['P'])==p)
def f(x):return f'{float(x):.6f}'
chapter=P('docs/final_B_mpi.md');old=chapter.read_text();backup=root/'legacy_final_B_mpi.md'
if not backup.exists():backup.write_text(old)
prefix=old[:old.index('## Measured scaling and hybrid results')];suffix=old[old.index('## Reproduction and AI usage'):]
start=prefix.index('Status,');end=prefix.index('## Parallel design')
prefix=prefix[:start]+'''Status, 7 November 2026 (Singapore time): technical closeout is complete.
The report uses 20 scaling configurations and eight paired-layout configuration
occurrences, each with three formal samples: 84 formal samples in total, plus
three communication diagnostics. The main numerical table has 26 configuration
IDs and 78 samples; two additional pure-MPI paired controls supply six samples.
Local and real two-node validation passed. Optional 432/720-core points remain
queued and are not reported as completed. Author identification and personal
contribution declarations are omitted at the user's request.

''' + prefix[end:]
prefix=prefix.replace('four 36-core nodes / nine 32-core nodes to use fragmented capacity;\nthe 72-core hybrid comparison retains its single-node allocation.', 'four 36-core nodes / nine 32-core nodes to use fragmented capacity.\nThe final scaling P72 point uses three 24-core allocations in the same host\nmemory-capacity class; its separate hybrid comparison retains the original\nsingle-node allocation and its own paired MPI baseline.')
body='''## Measured scaling and hybrid results

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

'''
for n in [128,256]:
 a=find(n,72);b=find(n,288)
 body+=f'For {n}³, the standardized P72 median is {f(a["median"])} s (speedup {float(a["speedup"]):.3f}, efficiency {100*float(a["efficiency"]):.2f}%). P288 takes {f(b["median"])} s (speedup {float(b["speedup"]):.3f}, efficiency {100*float(b["efficiency"]):.2f}%). The small-grid and large-grid efficiencies differ substantially.\n\n'
r=find(256,144);rr=find(512,288)
body+=f'''The original 256³/P144 median is {f(r['median'])} s, with range
[{f(r['minimum'])}, {f(r['maximum'])}] s. It is retained even though the
curve is nonmonotonic. The independent four-host review gives
{f(review['median'])} s, range [{f(review['minimum'])}, {f(review['maximum'])}] s.
The host sets partly overlap and conditions are shared; this reproduces high
waiting in the tested allocations, but does not establish a universal
intrinsic defect at exactly 144 ranks or identify a unique root cause.

For 512³, the P72 baseline is {f(find(512,72)['median'])} s on three hosts.
P288 takes {f(rr['median'])} s, giving S72={float(rr['speedup']):.3f} and
E72={100*float(rr['efficiency']):.2f}%. This is relative-to-72 scaling, not
speedup relative to one rank. The 720-core point remains omitted.

### Weak scaling

Each rank owns 64³ interior points. The global domain remains the unit cube,
so grid spacing and the discrete problem change with P. The controlled
quantity is point-update work per rank, not precision or equal solution time.

| P | Nodes | ms per sweep | Weak efficiency T1/TP |
|---:|---:|---:|---:|
'''
for r in sorted([x for x in rows if x['suite']=='weak'],key=lambda x:int(x['P'])):body+=f"| {r['P']} | {r['nodes']} | {f(r['median'])} | {100*float(r['efficiency']):.2f}% |\n"
body+='''
The fixed local work does not keep time constant. Neighbor counts, cross-node
messages, shared-memory resources and scheduling can change. The P144 anomaly
is retained in both strong and weak curves; phase evidence helps locate the
loss but cannot isolate all system causes.

### Paired MPI+OpenMP layouts

| Total cores | P×T | Nodes | Median [min, max] seconds | Paired MPI / time |
|---:|---|---:|---:|---:|
'''
for r in sorted(hyb,key=lambda x:(int(x['cores']),-int(x['P']))):body+=f"| {r['cores']} | {r['P']}×{r['T']} | {r['nodes']} | {f(r['median'])} [{f(r['minimum'])}, {f(r['maximum'])}] | {float(r['speedup']):.3f} |\n"
body+='''
At 72 cores, all three hybrids are slower than the single-node paired MPI
control; even the best hybrid minimum exceeds the MPI maximum. At 144 cores
in the explicitly controlled review allocation, all three mixed layouts are
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
'''
for r in sorted(diag,key=lambda x:int(x['P'])):
 nodes={72:3,144:4,288:9}[int(r['P'])];body+=f"| {r['P']} | {nodes} | {f(r['total'])} | {f(r['update'])} | {f(r['pack_unpack'])} | {f(r['communication_wait'])} | {100*float(r['communication_wait'])/float(r['total']):.2f}% |\n"
body+='''
The large original P144 waiting interval persists in the independent review.
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

'''
chapter.write_text(prefix+body+suffix)
