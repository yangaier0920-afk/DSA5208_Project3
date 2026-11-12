#!/usr/bin/env python3
"""Publish audited observations, retaining historical points and all samples."""
import csv
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
opt = read(IN / 'optional_analysis/summary.csv')
states_file = ROOT / 'results/final_202611/B_nov09/job_status.json'
states = json.loads(states_file.read_text()) if states_file.exists() else []
snapshot = datetime.fromtimestamp(states_file.stat().st_mtime, timezone(timedelta(hours=8))).isoformat() if states_file.exists() else 'unknown'
submission=ROOT/'results/final_202611/B_nov09/submitted_jobs.json'
if submission.exists():
    manifest=json.loads(submission.read_text())
    names={r['job']:r['name'] for r in manifest['submitted']}
    states=[dict(experiment=names.get(r['job'],'unknown'),**r) for r in states]
    shutil.copyfile(submission,OUT/'submission_history.json')

audit = json.loads((IN / 'analysis/audit.json').read_text())
for p in (IN / 'analysis').glob('*.csv'):
    shutil.copyfile(p, OUT / p.name)
shutil.copyfile(IN / 'analysis/audit.json', OUT / 'audit.json')
write('optional_summary.csv', opt)
write('PBS_status.csv', [dict(experiment=r.get('experiment','unknown'),job=r['job'], state=r.get('state','unknown'),
                            exit_status=r.get('exit_status'), comment=r.get('comment','').rstrip()) for r in states])

strong = []
for r in old + opt:
    if r['suite'] != 'strong':
        continue
    n, p = int(r['nx']), int(r['P'])
    candidates = [v for v in new if v['case'] == 'strong'+str(n) and v['mode'] == 'paired144'] if p == 144 else []
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
        candidates = [v for v in new if v['mode']=='paired144' and v['case']=='weak64']
        if candidates:
            v=candidates[0]
            for k in ('median','minimum','maximum'):r[k]=float(v[k])
            r['provenance']=v['job']
    for p in (1,8,72):
        b=next(v for v in old if v['suite']=='weak' and int(v['P'])==p)
        r['E'+str(p)]=float(b['median'])/r['median']
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
    if v['mode']=='clean144' and v['case'].startswith('strong'):
        m=float(v['median'])
        axes[0].errorbar([144],[m],yerr=[[m-float(v['minimum'])],[float(v['maximum'])-m]],
                         marker='D',markerfacecolor='none',color='black',capsize=3,linestyle='none',zorder=5)
for ax in axes:
    ax.set_xscale('log');ax.set_xticks([1,12,36,72,144,288,720],[str(p) for p in [1,12,36,72,144,288,720]])
    ax.set_xlabel('MPI ranks / physical cores');ax.grid(alpha=.2);ax.legend(fontsize=7)
axes[0].set_yscale('log');axes[0].set_ylabel('Iteration time (s), K=1000')
axes[0].set_title('Open diamonds: separate nine-host P144 run')
axes[1].set_ylabel('Strong efficiency (%)');fig.tight_layout();fig.savefig(OUT/'strong_scaling.png',dpi=180);plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(10,3.5))
rs=sorted(weak,key=lambda r:r['P']);xs=[r['P'] for r in rs]
axes[0].errorbar(xs,[r['median'] for r in rs],
    yerr=[[r['median']-r['minimum'] for r in rs],[r['maximum']-r['median'] for r in rs]],marker='o',capsize=3)
axes[0].set_ylabel('Milliseconds per sweep (K=1000)')
axes[0].set_yscale('log')
for v in new:
    if v['mode']=='clean144' and v['case']=='weak64':
        m=float(v['median'])
        axes[0].errorbar([144],[m],yerr=[[m-float(v['minimum'])],[float(v['maximum'])-m]],
                        marker='D',markerfacecolor='none',color='black',capsize=3,linestyle='none',
                        label='Separate nine-host P144')
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
    '## Scheduler status (snapshot, not live)\n', f'Last collected: {snapshot}. SSH disconnected afterward; uncompleted jobs may have progressed.\n', table(states,['experiment','job','state','exit_status']),
    '## Audited new measurements\n', table(new,['job','mode','case','P','T','median','minimum','maximum','max_deviation_pct']),
    '## Optional 432/720-core results recovered from 8 November\n',table(opt,['id','nodes','median','minimum','maximum']),
    '## Interpretation and limits\n',
    '- The nine-host P144 rerun is separate from the four-host hybrid control. Its host count/ranks per host changed; recovery cannot uniquely identify faulty hardware. No monotonicity acceptance filter is used.\n',
    '- The old P144 observations remain in the historical archive. Main tables replace them only after a completed four-host paired run. Open diamonds show the separate nine-host results.\n',
    '- New exclusive P1 samples replace the old shared-node P1 denominator only when the full five-repeat job is audited. The old weak-P1 (64 cubed) denominator is retained and labelled by the reference efficiencies E1/E8/E72.\n',
    '- Cross-core scaling combines allocations and dates on the same CPU model; occupancy, NUMA placement, CPU frequency and node topology can differ. A serial controls use the actual same core as MPI P1.\n',
    '- Optimization gains must use the matched experimental baseline. The original binary is an external reference because the experimental source changes the allocation representation. First touch is implemented but actual NUMA page placement is not independently measured.\n',
    '- Axis communication/wait totals aggregate both neighbors. Rank/host/neighbor tables identify participants, not a uniquely faulty one-way link. Link RTTs are descriptive windows, not fitted network alpha/beta constants.\n',
    '- Optional 2D and 3D problems have different work sizes and decompositions; compare trends rather than claiming a dimension-only runtime advantage.\n',
    '## Figures\n\n![Strong scaling](strong_scaling.png)\n\n![Weak scaling](weak_scaling.png)\n']
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
    write('two_dimensional_scaling.csv',rows)
    sections += ['\n### Optional 2D 512 x 512, K=1000\n',table(rows,['P','median','speedup','efficiency'])]
(OUT/'README.md').write_text('\n'.join(sections))
status = f'''# B 完成状态（2026-11-12）

已核验并归档：9 节点 144 核三规模强扩展、弱扩展、分轴诊断；参考节点 RTT；432/720 核历史作业（PBS 退出码均为 0）。

最新成功采集状态时间：{snapshot}。该时间之后 SSH 意外断开，以下是历史快照，不能当作实时状态。

''' + table(states,['experiment','job','state','exit_status']) + '''
整节点 P1、72 核优化消融、4 节点 144 核配对矩阵仍需采集完成证据；原异常节点诊断与探针仍排队。2D 扩展脚本已准备，尚未提交。任务尚未全部完成，不能将排队作业当成结果。

结果与原始证据：[B 补充结果](../b_mpi/nov12/final_results_20261112/README.md)。恢复 SSH 后继续采集，运行 analyze_feedback.py 与 build_results.py，脚本只接受完整且退出码为 0 的正式作业。

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
manifest={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in files.items()}
with zipfile.ZipFile(OUT/'raw_evidence.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name,p in sorted(files.items()):z.write(p,name)
    z.writestr('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
(OUT/'evidence_manifest.json').write_text(json.dumps({'accepted_jobs':audit['accepted_jobs'],
    'optional_jobs':['1529169.stdct-mgmt-02','1529170.stdct-mgmt-02'],
    'raw_archive_sha256':hashlib.sha256((OUT/'raw_evidence.zip').read_bytes()).hexdigest(),
    'raw_file_count':len(files)},indent=2))
print(OUT)
