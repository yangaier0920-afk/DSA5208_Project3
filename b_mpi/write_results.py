#!/usr/bin/env python3
"""Build a factual English results supplement from audited CSV only."""
import csv,json,pathlib,datetime
root=pathlib.Path('results/final_202611/B_mpi');analysis=root/'analysis'
rows=list(csv.DictReader((analysis/'summary.csv').open())) if (analysis/'summary.csv').exists() else []
audit=json.loads((analysis/'audit.json').read_text()) if (analysis/'audit.json').exists() else {}
status=json.loads((root/'job_status.json').read_text()) if (root/'job_status.json').exists() else []
lines=['# B: measured results and remaining work','', 'Generated '+datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')+'.','',f'{len(rows)} of 29 planned performance configurations have three audited formal samples. Warmups, local checks, incomplete configurations and failed launch attempts are excluded; earlier successful samples from interrupted jobs are retained after individual audit. This is a partial result set until all required configurations finish.','', '| Suite | Global mesh | P×T | Nodes | Median [min, max] seconds | Speedup / layout gain | Efficiency |','|---|---|---:|---:|---:|---:|---:|']
if audit.get('core_complete'):lines[4]='Core closeout complete: 20 scaling configurations and 8 paired-layout configurations supply 84 formal samples, plus 3 diagnostics. The main table below has 26 IDs (78 samples); two extra paired pure-MPI controls supply 6 samples and are in hybrid_summary.csv. Scaling uses the matched-memory cohort; hybrid denominators use their own paired allocation. Optional extensions are listed separately.'
for r in sorted(rows,key=lambda r:(r['suite'],int(r['nx']),int(r['cores']),-int(r['P']))):
 gain=f"{float(r['speedup']):.3f}" if r['speedup'] else 'pending baseline';eff=f"{100*float(r['efficiency']):.2f}%" if r['efficiency'] else '—'
 lines.append(f"| {r['suite']} | {r['nx']}×{r['ny']}×{r['nz']} | {r['P']}×{r['T']} | {r['nodes']} | {float(r['median']):.6f} [{float(r['minimum']):.6f}, {float(r['maximum']):.6f}] | {gain} | {eff} |")
lines+=['','All times cover K=1000 sweeps. Strong speedups use MPI P1 except 512³ (MPI P72). Weak efficiency is T1/TP. Hybrid gain uses equal-total-core pure MPI. These definitions must not be interchanged.','', '## Observations supported by completed measurements','']
for n in (128,256,512):
 series=sorted([r for r in rows if r['suite']=='strong' and int(r['nx'])==n and r['speedup']],key=lambda r:int(r['P']))
 if len(series)>1:
  r=series[-1];lines.append(f"For {n}³, the largest completed point is P={r['P']} on {r['nodes']} nodes: speedup {float(r['speedup']):.3f} and efficiency {100*float(r['efficiency']):.2f}%. Its timing range is retained in the table; differences in rank count and node placement must both be considered.")
weak=sorted([r for r in rows if r['suite']=='weak' and r['efficiency']],key=lambda r:int(r['P']))
if len(weak)>1:
 r=weak[-1];lines.append(f"At the largest completed weak point, P={r['P']}, time per sweep is {float(r['median'])/1000:.6g} s and weak efficiency is {100*float(r['efficiency']):.2f}%. Each rank owns 64³ points, but the global mesh and neighbor pattern differ from P1.")
lines+=['','These observations alone do not identify a unique performance cause. Read them together with the communication diagnostics, exact node allocation, shared-node conditions and layout comparisons. All valid slow samples remain included.','', '## Communication diagnostics','']
if (analysis/'diagnostics.csv').exists():
 ds=list(csv.DictReader((analysis/'diagnostics.csv').open()));lines+=['| P | Slowest rank | Total | Update | Pack/unpack | Communication/wait | Other measured | Uninstrumented | Rank-total range |','|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for r in ds:lines.append('| '+ ' | '.join([r['P'],r['slowest_rank']]+[f"{float(r[k]):.6f}" for k in ('total','update','pack_unpack','communication_wait','swap','uninstrumented')]+[f"[{float(r['min_rank_total']):.6f}, {float(r['max_rank_total']):.6f}]"] )+' |')
 lines+=['','Seconds accumulated over 1000 sweeps. Each row uses all phases from one rank: the rank with maximum total duration. Communication includes waiting, and timer overhead is present. This is explanatory data from one run per point.']
else:lines.append('No completed diagnostic has yet passed the full job acceptance gate.')
lines+=['','## Job status','', '| Job | State | Exit |','|---|---|---|']
for j in status:lines.append(f"| {j['job']} | {j.get('state','query error')} | {j.get('exit_status','')} |")
lines+=['','Q means queued, R running, F finished; successful acceptance requires per-command exit zero and data checks. Earlier successful samples of a job that later exits 1 on a separate failed launch are retained; missing repeats are supplemented on a matching allocation. Cancelled launch attempts have no accepted results. The first validation requested two nodes but used one; the corrected validation explicitly verified two-node execution.','', '## Figures and reproducibility','', 'See the PNG/PDF figures and CSV in `results/final_202611/B_mpi/analysis`. Plot error bars cover the full observed min/max. Time and CPU axes are logarithmic; efficiency is a percentage. `b_mpi/README.md` and `docs/final_B_mpi.md` define design, measurement scope and mathematical validation. Raw logs stay internal and are excluded from the final submission.']
pathlib.Path('docs/B_RESULTS_2026-11-07.md').write_text('\n'.join(lines)+'\n')
print(f'wrote results supplement: {len(rows)} configurations')
