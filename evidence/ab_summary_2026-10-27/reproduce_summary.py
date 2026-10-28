"""Rebuild cross-job summary from saved raw JSON; no cluster execution."""
import csv, hashlib, json, math, statistics
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path('evidence/ab_summary_2026-10-27')
OUT.mkdir(exist_ok=False)
JOBS = ['1499881','1500222','1500271']
rows=[]; comparisons=[]; datasets={}; baselines={}
for job in JOBS:
    root=Path('results')/f'Vanda_mpi_recheck_{job}.stdct-mgmt-02'
    b=json.loads((root/'benchmark/summary.json').read_text(encoding='utf-8'))
    audit=json.loads((Path('evidence')/f'vanda_{job}_mpi_recheck'/'audit.json').read_text())
    assert audit['status']=='PASS' and audit['rank_affinity_records_rechecked']==390
    datasets[job]=b
    medians={(g['mode'],g['processes'],g['exchange']):g['median_seconds'] for g in b['groups']}
    serial=medians['serial',1,'none']; baselines[job]=serial
    for g in b['groups']:
        runs=[r for r in b['runs'] if not r['warmup'] and (r['result']['mode'],r['result'].get('mpi_processes',1),r['result'].get('exchange','none'))==(g['mode'],g['processes'],g['exchange'])]
        x=[r['result']['compute_seconds'] for r in runs]; median=statistics.median(x)
        assert median==g['median_seconds']
        mpibase=medians.get(('mpi',1,g['exchange']))
        rows.append(dict(job_id=job,n=b['n'],host=b['host'],mode=g['mode'],processes=g['processes'],exchange=g['exchange'],median_seconds=median,min_seconds=min(x),max_seconds=max(x),sample_cv_percent=100*statistics.stdev(x)/statistics.mean(x),serial_baseline_seconds=serial,serial_speedup=serial/median,serial_efficiency=serial/median/g['processes'],mpi_p1_baseline_seconds=mpibase,mpi_speedup=mpibase/median if mpibase else None,mpi_efficiency=mpibase/median/g['processes'] if mpibase else None,samples_seconds=x))
    for p in [1,2,4,12]:
        samples={e:{r['repeat_index']:r['result']['compute_seconds'] for r in b['runs'] if not r['warmup'] and r['result']['mode']=='mpi' and r['result']['mpi_processes']==p and r['result']['exchange']==e} for e in ['sendrecv','overlap']}
        reduction=100*(1-medians['mpi',p,'overlap']/medians['mpi',p,'sendrecv'])
        comparisons.append(dict(job_id=job,n=b['n'],processes=p,overlap_median_time_reduction_percent=reduction,overlap_faster_rounds=sum(samples['overlap'][k]<samples['sendrecv'][k] for k in range(9)),rounds=9))
for name,data in [('performance_comparison.csv',rows),('communication_comparison.csv',comparisons)]:
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=[k for k in data[0] if k!='samples_seconds'])
        writer.writeheader(); writer.writerows({k:v for k,v in r.items() if k!='samples_seconds'} for r in data)
reference=[datasets[j]['runs'][0]['result'] for j in ['1499881','1500271']]
assert all(reference[0][k]==reference[1][k] for k in ['n','iterations','tolerance','max_update','max_error','residual_inf','boundary_error'])
summary=dict(jobs=JOBS,performance=rows,communication=comparisons,identical_1024_global_metrics=True,numerical_validation_executions=264,expected_invalid_rejections=12,performance_executions_including_warmups=270,rank_affinity_records=1170,full_grid_validation_executions=129,note='Counts aggregate repeated suites; they are not counts of distinct mathematical problems.')
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors={'sendrecv':'#206095','overlap':'#d66b24'}
fig,axes=plt.subplots(2,3,figsize=(13.5,7.2),layout='constrained')
for col,job in enumerate(JOBS):
    b=datasets[job]
    for method in ['sendrecv','overlap']:
        data=[r for r in rows if r['job_id']==job and r['exchange']==method]
        for row,field in [(0,'serial_speedup'),(1,'mpi_speedup')]:
            axes[row,col].plot([r['processes'] for r in data],[r[field] for r in data],marker='o',label=method,color=colors[method])
    for ax in axes[:,col]:
        ax.plot([1,12],[1,12],'--',color='#999999',label='Ideal linear')
        ax.set_xticks([1,2,4,12]); ax.set_ylim(0,12.5); ax.grid(alpha=.2)
        ax.set_xlabel('MPI processes')
    axes[0,col].set_title(f"{job} | n={b['n']} | {b['host']}")
axes[0,0].set_ylabel('Speedup vs own-job serial')
axes[1,0].set_ylabel('Speedup vs own-strategy MPI P=1')
axes[0,2].legend(loc='upper left',fontsize=8)
fig.suptitle('Single-node strong scaling | K=1000, tolerance=0 | 9 measurements per configuration')
fig.savefig(OUT/'strong_scaling_comparison.png',dpi=180); plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11.5,4.4),layout='constrained')
labels=['Serial','P1 SR','P1 OV','P2 SR','P2 OV','P4 SR','P4 OV','P12 SR','P12 OV']
for job,color in [('1499881','#206095'),('1500271','#a54c79')]:
    data=[r for r in rows if r['job_id']==job]
    axes[0].errorbar(range(9),[r['median_seconds'] for r in data],yerr=[[r['median_seconds']-r['min_seconds'] for r in data],[r['max_seconds']-r['median_seconds'] for r in data]],marker='o',capsize=3,label=job,color=color)
axes[0].set_xticks(range(9),labels,rotation=45,ha='right'); axes[0].set_ylabel('Iteration time (s)'); axes[0].legend(); axes[0].grid(alpha=.2)
axes[0].set_title('Two independent n=1024 jobs | median and min-max')
for job,color in [('1499881','#206095'),('1500222','#438560'),('1500271','#a54c79')]:
    data=[r for r in comparisons if r['job_id']==job and r['processes']>1]
    axes[1].plot([r['processes'] for r in data],[r['overlap_median_time_reduction_percent'] for r in data],marker='o',label=job,color=color)
axes[1].axhline(0,color='#999999',ls='--'); axes[1].set_xticks([2,4,12]); axes[1].set_xlabel('MPI processes'); axes[1].set_ylabel('Overlap median time reduction (%)'); axes[1].legend(); axes[1].grid(alpha=.2)
axes[1].set_title('Positive = overlap median is lower')
fig.suptitle('Job allocations differ; min-max bars are not confidence intervals')
fig.savefig(OUT/'runtime_and_communication.png',dpi=180); plt.close(fig)
fig,axes=plt.subplots(1,2,figsize=(11.5,4.2),layout='constrained')
for job,color in [('1499881','#206095'),('1500271','#a54c79')]:
    serial=next(r for r in rows if r['job_id']==job and r['mode']=='serial')
    axes[0].plot(range(1,10),serial['samples_seconds'],marker='o',label=f'{job} serial',color=color)
for method in ['sendrecv','overlap']:
    r=next(r for r in rows if r['job_id']=='1500271' and r['processes']==12 and r['exchange']==method)
    axes[1].plot(range(1,10),r['samples_seconds'],marker='o',label=method,color=colors[method])
for ax in axes:
    ax.set_xlabel('Measurement round (1-9)'); ax.set_ylabel('Iteration time (s)'); ax.set_xticks(range(1,10)); ax.grid(alpha=.2); ax.legend()
axes[0].set_title('n=1024 serial samples; each job has its own baseline')
axes[1].set_title('1500271 | P=12 | all samples retained')
fig.savefig(OUT/'measurement_samples.png',dpi=180); plt.close(fig)
print(json.dumps({'output':str(OUT),'rows':len(rows),'communication_rows':len(comparisons),'serial_time_change_1024_percent':100*(baselines['1500271']/baselines['1499881']-1)},indent=2))
