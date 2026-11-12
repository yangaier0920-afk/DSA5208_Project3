#!/usr/bin/env python3
"""Publish audited observations, retaining historical points and all samples."""
import csv
import statistics
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / 'results/final_202611/B_nov12'
OUT = ROOT / 'b_mpi/nov12/final_results_20261112'
OUT.mkdir(parents=True, exist_ok=True)

def read(p):
    return list(csv.DictReader(p.open())) if p.exists() else []

def write(name, rows):
    if not rows:
        return
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

def table(rows, keys):
    return '| ' + ' | '.join(keys) + ' |\n|' + '|'.join(['---'] * len(keys)) + '|\n' + ''.join(
        '| ' + ' | '.join(str(r.get(k, '')) for k in keys) + ' |\n' for r in rows)

new = read(IN / 'analysis/summary.csv')
old = read(ROOT / 'results/final_202611/B_mpi/analysis/summary.csv')
opt = read(IN / 'optional_analysis/summary.csv') or read(OUT/'optional_summary.csv')
states_file = ROOT / 'results/final_202611/B_nov09/job_status.json'
states = json.loads(states_file.read_text()) if states_file.exists() else []
snapshot = datetime.fromtimestamp(states_file.stat().st_mtime, timezone(timedelta(hours=8))).isoformat() if states_file.exists() else 'unknown'
collection_snapshot=states_file.with_name('collection_snapshot.json')
if collection_snapshot.exists():snapshot=json.loads(collection_snapshot.read_text())['time_singapore']
submission=ROOT/'results/final_202611/B_nov09/submitted_jobs.json'
if submission.exists():
    manifest=json.loads(submission.read_text())
    names={r['job']:r['name'] for r in manifest['submitted']}
    states=[dict(experiment=names.get(r['job'],'unknown'),**r) for r in states]
    shutil.copyfile(submission,OUT/'submission_history.json')

audit = json.loads((IN / 'analysis/audit.json').read_text())
raw_jobs={json.loads(p.read_text()).get('job') for p in
          (ROOT/'results/final_202611/B_nov09').rglob('metadata.json')}
if not set(audit['accepted_jobs'])<=raw_jobs:
    raise SystemExit('Extract final_results_20261112/raw_evidence.zip at the repository root before rebuilding.')
for job in ('1529169','1529170'):
    if not (ROOT/'results/final_202611/B_mpi'/f'Vanda_{job}.stdct-mgmt-02'/'data'/'metadata.json').exists():
        raise SystemExit('Optional raw evidence missing; extract raw_evidence.zip before rebuilding.')
for p in (IN / 'analysis').glob('*.csv'):
    shutil.copyfile(p, OUT / p.name)
shutil.copyfile(IN / 'analysis/audit.json', OUT / 'audit.json')
write('optional_summary.csv', opt)
write('historical_summary.csv',old)
write('four_host_144.csv',[v for v in new if v['mode']=='paired144'])
axis_rows=read(IN/'analysis/axis_rank_pairs.csv')
axis_summary=[]
for key in sorted({(r['job'],r['mode'],r['case'],r['axis']) for r in axis_rows}):
    part=[r for r in axis_rows if (r['job'],r['mode'],r['case'],r['axis'])==key]
    worst=max(part,key=lambda r:float(r['communication_wait_seconds']))
    cross=[r for r in part if any(r[k] not in (r['host'],'boundary') for k in ('low_host','high_host'))]
    wc=max(cross,key=lambda r:float(r['communication_wait_seconds'])) if cross else None
    axis_summary.append(dict(job=key[0],mode=key[1],case=key[2],axis=key[3],
        median_wait=statistics.median(float(r['communication_wait_seconds']) for r in part),
        maximum_wait=float(worst['communication_wait_seconds']),rank_at_max=worst['rank'],
        host=worst['host'],low_host=worst['low_host'],high_host=worst['high_host'],
        ranks_with_cross_host_neighbor=len(cross),
        maximum_cross_host_wait=float(wc['communication_wait_seconds']) if wc else '',
        cross_host_rank=wc['rank'] if wc else '',cross_host=wc['host'] if wc else '',
        cross_low_host=wc['low_host'] if wc else '',cross_high_host=wc['high_host'] if wc else ''))
write('axis_summary.csv',axis_summary)
phases=[]
for meta in (ROOT/'results/final_202611/B_nov09').rglob('metadata.json'):
    m=json.loads(meta.read_text())
    if m.get('job') not in audit['accepted_jobs']:continue
    for record in meta.parent.glob('*.record.json'):
        r=json.loads(record.read_text())
        if not r['config']['diagnostic']:continue
        v=r['result'];rank=max(range(len(v['rank_timings'])),key=lambda i:v['rank_timings'][i][0])
        t=v['rank_timings'][rank]
        phases.append(dict(job=m['job'],mode=m['mode'],case=r['config']['id'],rank=rank,
            host=v['rank_hosts'][rank],total=t[0],update=t[1],pack_unpack=t[2],communication_wait=t[3],
            other=t[4],unattributed=t[0]-sum(t[1:]),communication_pct=100*t[3]/t[0],pack_pct=100*t[2]/t[0]))
write('phase_summary.csv',phases)
paired=[r for r in new if r['mode']=='paired144']
if paired:
    base=next(r for r in paired if r['case']=='strong256')
    write('hybrid_144_comparison.csv',[dict(layout=r['P']+'x'+r['T'],median=float(r['median']),
        minimum=float(r['minimum']),maximum=float(r['maximum']),same_allocation_MPI_over_layout=float(base['median'])/float(r['median']))
        for r in sorted(paired,key=lambda r:-int(r['P'])) if r['case']=='strong256' or r['case'].startswith('pair_')])
required={('baseline',f'{b}_{n}') for b in ('mpi','serial') for n in (128,256)}
required|={(m,'strong'+str(n)) for m in ('clean144','paired144') for n in (128,256,512)}
required|={(m,'weak64') for m in ('clean144','paired144')}
required|={('paired144',p) for p in ('pair_24x6','pair_12x12','pair_4x36')}
required|={('optimize72',f'{v}_{p}x{t}') for v in ('original','baseline','parallel_pack','first_touch','persistent','optimized') for p,t in ((72,1),(12,6),(6,12),(2,36))}
actual={(r['mode'],r['case']) for r in new}
(OUT/'core_task_audit.json').write_text(json.dumps({'core_complete':required<=actual,
    'required_configurations':len(required),'accepted_core_configurations':len(required&actual),
    'missing':sorted(required-actual),'new_formal_samples':sum(int(r['samples']) for r in new),
    'core_formal_samples':sum(int(r['samples']) for r in new if (r['mode'],r['case']) in required),
    'new_diagnostic_runs':len(phases),'core_diagnostic_runs':sum(r['mode']!='twod' for r in phases),'baseline_five_percent_target_met':all(r['baseline_five_percent_target_met']=='True' for r in new if r['mode']=='baseline'),
    'optional_2d_complete':{('twod',f'twod512_p{p}') for p in (1,12,36,72)}<=actual,
    'optional_original_host_jobs':[r for r in states if r.get('experiment') in ('suspect_diag','link_suspect')]},indent=2))
write('PBS_status.csv', [dict(experiment=r.get('experiment','unknown'),job=r['job'], state=r.get('state','unknown'),
                            exit_status=r.get('exit_status'), comment=r.get('comment','').rstrip()) for r in states])

strong = []
for r in old + opt:
    if r['suite'] != 'strong':
        continue
    n, p = int(r['nx']), int(r['P'])
    candidates = [v for v in new if v['case'] == 'strong'+str(n) and v['mode'] == 'clean144'] if p == 144 else []
    if p == 1:
        candidates = [v for v in new if v['mode'] == 'baseline' and v['case'] == f'mpi_{n}']
    v = candidates[0] if candidates else r
    strong.append(dict(n=n, P=p, median=float(v['median']), minimum=float(v['minimum']),
                       maximum=float(v['maximum']), provenance=(v.get('job') or 'Nov7/8 audited archive'),
                       cohort='updated' if candidates else 'historical', speedup=0.0, efficiency=0.0))
for r in strong:
    bp = 72 if r['n'] == 512 else 1
    b = next(v for v in strong if v['n'] == r['n'] and v['P'] == bp)
    r['speedup'] = b['median']/r['median']
    r['efficiency'] = r['speedup']/(r['P']/bp)
write('strong_scaling.csv', sorted(strong, key=lambda r:(r['n'],r['P'])))

weak = [dict(P=int(r['P']), median=float(r['median']), minimum=float(r['minimum']),
             maximum=float(r['maximum']), provenance='Nov7/8 audited archive', E1=0., E8=0., E72=0.)
        for r in old+opt if r['suite']=='weak']
for r in weak:
    if r['P'] == 144:
        candidates = [v for v in new if v['mode']=='clean144' and v['case']=='weak64']
        if candidates:
            v=candidates[0]
            for k in ('median','minimum','maximum'):r[k]=float(v[k])
            r['provenance']=v['job']
    for p in (1,8,72):
        b=next(v for v in old if v['suite']=='weak' and int(v['P'])==p)
        r['E'+str(p)]=float(b['median'])/r['median'] if r['P']>=p else ''
write('weak_scaling.csv',sorted(weak,key=lambda r:r['P']))

plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
fig, axes=plt.subplots(1,2,figsize=(10,3.5))
for n in (128,256,512):
    rs=sorted([r for r in strong if r['n']==n],key=lambda r:r['P'])
    axes[0].errorbar([r['P'] for r in rs],[r['median'] for r in rs],
        yerr=[[r['median']-r['minimum'] for r in rs],[r['maximum']-r['median'] for r in rs]],
        marker='o',capsize=3,label=f'{n} cubed')
    axes[1].plot([r['P'] for r in rs],[100*r['efficiency'] for r in rs],'o-',label=f'{n} cubed; base P{72 if n==512 else 1}')
for v in new:
    if v['mode']=='paired144' and v['case'].startswith('strong'):
        m=float(v['median'])
        axes[0].errorbar([144],[m],yerr=[[m-float(v['minimum'])],[float(v['maximum'])-m]],
                         marker='D',markerfacecolor='none',color='black',capsize=3,linestyle='none',zorder=5)
for ax in axes:
    ax.set_xscale('log');ax.set_xticks([1,12,36,72,144,288,720],[str(p) for p in [1,12,36,72,144,288,720]])
    ax.set_xlabel('MPI ranks / physical cores');ax.grid(alpha=.2);ax.legend(fontsize=7)
axes[0].set_yscale('log');axes[0].set_ylabel('Iteration time (s), K=1000')
axes[0].set_title('Open diamonds: separate four-host P144 control')
axes[1].set_ylabel('Strong efficiency (%)');fig.tight_layout();fig.savefig(OUT/'strong_scaling.png',dpi=180);plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(10,3.5))
rs=sorted(weak,key=lambda r:r['P']);xs=[r['P'] for r in rs]
axes[0].errorbar(xs,[r['median'] for r in rs],
    yerr=[[r['median']-r['minimum'] for r in rs],[r['maximum']-r['median'] for r in rs]],marker='o',capsize=3)
axes[0].set_ylabel('Milliseconds per sweep (K=1000)')
axes[0].set_yscale('log')
for v in new:
    if v['mode']=='paired144' and v['case']=='weak64':
        m=float(v['median'])
        axes[0].errorbar([144],[m],yerr=[[m-float(v['minimum'])],[float(v['maximum'])-m]],
                        marker='D',markerfacecolor='none',color='black',capsize=3,linestyle='none',
                        label='Separate four-host P144')
        axes[0].legend(fontsize=7)
for p in (1,8,72):
    part=[r for r in rs if r['P']>=p]
    axes[1].plot([r['P'] for r in part],[100*r['E'+str(p)] for r in part],'o-',label=f'P{p} reference')
axes[1].legend();axes[1].set_ylabel('Weak efficiency (%)')
for ax in axes:ax.set_xscale('log');ax.set_xlabel('MPI ranks / physical cores');ax.grid(alpha=.2)
fig.tight_layout();fig.savefig(OUT/'weak_scaling.png',dpi=180);plt.close(fig)

ablation=[v for v in new if v['mode']=='optimize72']
if ablation:
    fig,ax=plt.subplots(figsize=(9,4))
    labels=['original','baseline','parallel_pack','first_touch','persistent','optimized']
    for p,t in ((72,1),(12,6),(6,12),(2,36)):
        rs=[next(v for v in ablation if int(v['P'])==p and v['variant']==key) for key in labels]
        ax.errorbar(range(6),[float(r['median']) for r in rs],
            yerr=[[float(r['median'])-float(r['minimum']) for r in rs],
                  [float(r['maximum'])-float(r['median']) for r in rs]],marker='o',capsize=3,label=f'{p} x {t}')
    ax.set_xticks(range(6),labels,rotation=12);ax.set_yscale('log');ax.set_ylabel('Iteration time (s), 256 cubed')
    ax.grid(alpha=.2);ax.legend();fig.tight_layout();fig.savefig(OUT/'optimization_ablation.png',dpi=180);plt.close(fig)

sections=['# B follow-up results — 12 November 2026\n',
    'Only independently completed PBS jobs with exit zero enter the tables. Times are medians of all three formal samples (five for P1), after one warmup. Min/max bars are observed ranges, not confidence intervals. Slow samples are retained.\n',
    '## Scheduler status (snapshot, not live)\n', f'Last collected: {snapshot}. This is a saved scheduler snapshot; uncompleted jobs may have progressed.\n', table(states,['experiment','job','state','exit_status']),
    '## Audited new measurements\n', table(new,['job','mode','case','P','T','median','minimum','maximum','max_deviation_pct']),
    '## Optional 432/720-core results recovered from 8 November\n',table(opt,['id','nodes','median','minimum','maximum']),
    '## Interpretation and limits\n',
    '- The nine-host P144 rerun is separate from the four-host hybrid control. Its host count/ranks per host changed; recovery cannot uniquely identify faulty hardware. No monotonicity acceptance filter is used.\n',
    '- The main P144 pure-MPI series uses the predeclared nine-host cohort; open diamonds show the four-host paired control. The old and new four-host high-wait observations are retained separately. This is a comparison of declared layouts, not sample selection by speed. Hybrid gains always use their own four-host MPI denominator.\n',
    '- New exclusive P1 samples replace the old shared-node P1 denominator only when the full five-repeat job is audited. The old weak-P1 (64 cubed) denominator is retained and labelled by the reference efficiencies E1/E8/E72.\n',
    '- Cross-core scaling combines allocations and dates on the same CPU model; occupancy, NUMA placement, CPU frequency and node topology can differ. A serial controls use the actual same core as MPI P1.\n',
    '- Optimization gains must use the matched experimental baseline. The original binary is an external reference because the experimental source changes the allocation representation. First touch is implemented but actual NUMA page placement is not independently measured.\n',
    '- Axis communication/wait totals aggregate both neighbors. Rank/host/neighbor tables identify participants, not a uniquely faulty one-way link. Link RTTs are descriptive windows, not fitted network alpha/beta constants.\n',
    '- Optional 2D and 3D problems have different work sizes and decompositions; compare trends rather than claiming a dimension-only runtime advantage.\n',
    '## Report\n\n[Six-page B completion supplement](../../../output/pdf/DSA5208_B_Completed_Experiments_20261112.pdf).\n\n## Figures\n\n![Strong scaling](strong_scaling.png)\n\n![Weak scaling](weak_scaling.png)\n']
if ablation:sections.append('\n![Optimization ablation](optimization_ablation.png)\n')
sections.append('\n## Measured conclusions\n')
for r in new:
    if r['mode']=='clean144' and r['case'].startswith('strong'):
        n=int(r['nx'])
        h=next(v for v in old if v['suite']=='strong' and int(v['P'])==144 and int(v['nx'])==n)
        sections.append(f"- Nine-host {n} cubed P144: {float(r['median']):.6f} s "
                        f"[{float(r['minimum']):.6f}, {float(r['maximum']):.6f}], "
                        f"versus historical four-host {float(h['median']):.6f} s. "
                        "This establishes a different observed operating regime, with host/layout/date confounding.\n")
slow=read(IN/'analysis/slowest_rank_axes.csv')
for job in sorted({r['job'] for r in slow}):
    part=[r for r in slow if r['job']==job]
    r=max(part,key=lambda r:float(r['communication_wait_seconds']))
    sections.append(f"- Diagnostic {job}, slowest rank {r['rank']} ({r['host']}): "
                    f"largest axis wait is {r['axis']}, {float(r['communication_wait_seconds']):.6f} s; "
                    f"participants {r['low_host']} / {r['high_host']}. Instrumented and formal runtimes are separate.\n")
baseline=[r for r in new if r['mode']=='baseline']
if baseline:
    for n in (128,256):
        mpi=next(r for r in baseline if r['case']==f'mpi_{n}')
        serial=next(r for r in baseline if r['case']==f'serial_{n}')
        sections.append(f"- Exclusive same-core {n} cubed: MPI P1 {float(mpi['median']):.6f} s, "
                        f"A serial {float(serial['median']):.6f} s; maximum median deviations "
                        f"{float(mpi['max_deviation_pct']):.2f}% / {float(serial['max_deviation_pct']):.2f}%. "
                        "All five formal samples are retained, whether or not the 5% target is met.\n")
if ablation:
    gains=[]
    for r in ablation:
        b=next(v for v in ablation if v['P']==r['P'] and v['variant']=='baseline')
        gains.append(dict(layout=r['P']+'x'+r['T'],variant=r['variant'],median=float(r['median']),
                          baseline_over_variant=float(b['median'])/float(r['median'])))
    write('optimization_gains.csv',gains)
    sections += ['\n### All optimization outcomes\n',table(gains,['layout','variant','median','baseline_over_variant']),
                 '\nRatios above one mean faster than the matched experimental baseline. '
                 'Ratios for the original binary are descriptive, not isolated optimization effects. '
                 'The combined treatment includes extra synchronization; parallel packing or a persistent region '
                 'is not assumed beneficial at every subdomain/thread count.\n']
twod=[r for r in new if r['mode']=='twod']
if twod:
    b=next(r for r in twod if int(r['P'])==1)
    rows=[dict(P=int(r['P']),median=float(r['median']),speedup=float(b['median'])/float(r['median']),
               efficiency=float(b['median'])/float(r['median'])/int(r['P'])) for r in twod]
    rows.sort(key=lambda r:r['P'])
    write('two_dimensional_scaling.csv',rows)
    sections += ['\n### Optional 2D 512 x 512, K=1000\n',table(rows,['P','median','speedup','efficiency'])]
(OUT/'README.md').write_text('\n'.join(sections))
chapter='''# B: Cartesian MPI, hybrid execution and communication

Final core follow-up: 12 November 2026. All 39 required configurations,
125 new formal samples and four separate diagnostic runs passed the audit.
The completed optional P432/P720 jobs add three configurations and nine
formal samples. Remaining queued supplements are explicitly identified below.
Author identities and personal contribution declarations remain omitted.

## Parallel design and timing contract

The solver uses a Cartesian block decomposition of the interior grid with
uneven remainders assigned to low-coordinate ranks. Five-/seven-point Jacobi
stencils need face halos but no edge/corner exchange. Each face is packed,
exchanged with blocking MPI_Sendrecv, and unpacked before the update; swapping
two solution arrays preserves Jacobi semantics. MPI_THREAD_FUNNELED restricts
MPI calls to the main thread. The original Nov7 solver is byte-preserved.

Performance runs execute exactly K=1000 sweeps. Initialization, residual
evaluation and host/topology collection are outside the iteration timer;
the maximum rank time is reported. Every non-baseline configuration uses
one warmup plus three measured repetitions; the exclusive P1 controls use
five measured repetitions. Separate instrumented runs record per-rank phase
and x/y/z communication/packing intervals. CPU masks are audited for size,
allocation containment and overlap. Mathematical checks cover dimensions,
uneven partitions and hybrid variants; all five variants passed six local
oracle cases each, maximum error 7.55e-15.

The experimental baseline shares allocation representation with four
treatments: parallel face packing, genuinely parallel first writes into
uninitialized arrays, a persistent OpenMP team, and their combination.
Only matched-baseline ratios isolate these switches; the original solver is
retained as a separate external reference. Physical NUMA page placement is
not independently measured. No measurement is rejected for being slow.

The primary pure-MPI P144 curve uses the predeclared nine-host layout. The
four-host P144 matrix is a separate controlled layout comparison with its
own pure-MPI denominator. It remains slow on different nodes, so a hardware
fault claim about CN-011/CN-108 is not established. Historical high-wait
samples remain in the archive and historical_summary.csv.

See [the six-page supplement](../output/pdf/DSA5208_B_Completed_Experiments_20261112.pdf),
[raw evidence and all derived tables](../b_mpi/nov12/final_results_20261112/README.md),
[reproduction instructions](../b_mpi/nov12/README.md), and the
[superseded chapter](archive/final_B_mpi_pre_20261112.md).

'''
result_text='\n'.join(sections[2:])
for name in ('strong_scaling.png','weak_scaling.png','optimization_ablation.png'):
    result_text=result_text.replace(']('+name+')','](../b_mpi/nov12/final_results_20261112/'+name+')')
(ROOT/'docs/final_B_mpi.md').write_text(chapter+result_text)
status = f'''# B 完成状态（2026-11-12）

已核验并归档的作业以结果表与 PBS 退出码为准；下表中的 Q/H/R 不计入完成结果。

最新成功采集状态时间：{snapshot}。以下为已保存快照，不能当作实时状态。

''' + table(states,['experiment','job','state','exit_status']) + '''
核心任务：整节点 P1、72 核优化消融、九节点及四节点 144 核矩阵均已通过独立 PBS/数值/绑定/重复次数核验。原异常节点诊断与探针的完成状态见下表；可选 2D 已另行跑通并核验；不将排队作业计为结果。

结果与原始证据：[B 补充结果](../b_mpi/nov12/final_results_20261112/README.md)。继续采集后运行 analyze_feedback.py 与 build_results.py，脚本只接受完整且退出码为 0 的正式作业。

九节点复测的节点/布局已变化，不能据此唯一认定 CN-011/CN-108 硬件故障。所有慢样本保留；不以单调加速或预测时间作为筛选条件。
'''
(ROOT/'docs/B_COMPLETION_STATUS_2026-11-12.md').write_text(status)

# Retain raw commands, all warmups/formal samples, affinity logs, sources and PBS evidence.
files={}
for meta in (ROOT/'results/final_202611/B_nov09').rglob('metadata.json'):
    d=json.loads(meta.read_text())
    if d.get('job') not in audit['accepted_jobs']:continue
    for p in meta.parent.parent.rglob('*'):
        if p.is_file() and 'build' not in p.relative_to(meta.parent.parent).parts:
            files[str(p.relative_to(ROOT))]=p
for job in ('1529169','1529170'):
    for p in (ROOT/'results/final_202611/B_mpi'/f'Vanda_{job}.stdct-mgmt-02').rglob('*'):
        if p.is_file() and 'build' not in p.parts:files[str(p.relative_to(ROOT))]=p
for name in ('job_status.json','submitted_jobs.json','collection_snapshot.json'):
    p=ROOT/'results/final_202611/B_nov09'/name
    if p.exists():files[str(p.relative_to(ROOT))]=p
manifest={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in files.items()}
with zipfile.ZipFile(OUT/'raw_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name,p in sorted(files.items()):z.write(p,name)
    z.writestr('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
(OUT/'evidence_manifest.json').write_text(json.dumps({'accepted_jobs':audit['accepted_jobs'],
    'optional_jobs':['1529169.stdct-mgmt-02','1529170.stdct-mgmt-02'],
    'raw_archive_sha256':hashlib.sha256((OUT/'raw_evidence.zip').read_bytes()).hexdigest(),
    'raw_file_count':len(files)},indent=2))
print(OUT)
