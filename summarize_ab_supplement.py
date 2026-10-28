"""Review job 1501884 and compare all audited A/B datasets without pooling.
No solver or remote execution. Output must be new; downloaded raw files read only.
"""
import argparse
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import tarfile
import shutil
from analyze_results import checked_rows, require
from prepare_team_references import validate

BASE=Path(__file__).resolve().parent
OLD=('1499881','1500222','1500271')
NEW='1501884'
ROOT=BASE/'results'/f'Vanda_ab_dual_{NEW}.stdct-mgmt-02'
FIELDS=('max_update','max_error','residual_inf','boundary_error')
CST=timezone(timedelta(hours=8))


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p,d):
    p.write_text(json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def csv_save(path,rows):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out-dir',type=Path,default=BASE/'evidence/ab_summary_2026-10-28')
    args=ap.parse_args()
    out=args.out_dir.resolve()
    require(not out.exists(),'Output already exists')
    primary=read(BASE/'evidence/vanda_1501884_ab_supplement/audit.json')
    require(primary['status']=='PASS','Primary audit incomplete')
    b=read(ROOT/'benchmark/summary.json')
    # Independently compare every printed performance line to the journal, in order.
    log=(ROOT/'run.log').read_text(encoding='utf-8')
    lines=re.findall(r'^seq=(\d+) n=(\d+) (\S+): ([0-9.]+)s$',log,re.M)
    require(len(lines)==180,'Printed sequence count')
    for i,(seq,n,label,seconds) in enumerate(lines):
        r=b['runs'][i]
        require((int(seq),int(n),label)==(i,r['n'],r['id']),'Printed sequence differs')
        require(seconds==f"{r['result']['compute_seconds']:.6f}",'Printed timer differs')
        require(datetime.fromisoformat(r['started_at_utc'])<=datetime.fromisoformat(r['finished_at_utc']),'Invalid launch interval')
        if i:
            require(datetime.fromisoformat(b['runs'][i-1]['finished_at_utc'])<=datetime.fromisoformat(r['started_at_utc']),'Overlapping sequential launches')
    # Each of the two performance and two independent correctness binaries built once.
    build_lines=[line for line in log.splitlines() if line.startswith(('+ g++ ','+ mpicxx '))]
    require(len(build_lines)==4,'Unexpected build count')
    built={}
    for line in build_lines:
        require('-std=c++17 -O2 -Wall -Wextra -Wpedantic' in line,'Build flags differ')
        compiler,rest=line[2:].split(' ',1)
        source=re.search(r'/sources/(\S+\.cpp) -o (\S+)$',rest)
        require(source is not None,'Build invocation not preserved')
        filename=source.group(2).rsplit('/',1)[-1]
        require(filename not in built,'Duplicate binary build')
        built[filename]=dict(compiler=compiler,source=source.group(1))
    require(built=={
        'jacobi_serial':dict(compiler='g++',source='jacobi_serial_row_update.cpp'),
        'jacobi_mpi':dict(compiler='mpicxx',source='jacobi_mpi.cpp'),
        'jacobi_serial_asymmetric':dict(compiler='g++',source='jacobi_serial_asymmetric.cpp'),
        'jacobi_mpi_asymmetric':dict(compiler='mpicxx',source='jacobi_mpi_asymmetric.cpp')},'Build/source mapping')
    hardware=(ROOT/'lscpu.txt').read_text(encoding='utf-8')
    numa_match=re.search(r'^NUMA node1 CPU\(s\):\s*(.+)$',hardware,re.M)
    require(numa_match is not None,'NUMA topology missing')
    def expand(s):
        output=[]
        for part in s.split(','):
            limits=list(map(int,part.split('-')))
            output.extend(range(limits[0],limits[-1]+1))
        return output
    require(set(b['pin_cpus'])<=set(expand(numa_match.group(1))),'CPUs outside recorded NUMA node1')
    require('Xeon(R) Gold 6438N' in hardware,'Unexpected recorded hardware')
    qstat=(ROOT/'qstat_full.txt').read_text()
    require('exec_host = '+b['host']+'/' in qstat,'PBS/benchmark host mismatch')
    # Verify submitted snapshots against the already preserved upload bundle.
    bundle=BASE/'results/ab_supplement_upload_20261028_v1.tar.gz'
    with tarfile.open(bundle,'r:gz') as tar:
        submitted={p.name:hashlib.sha256(tar.extractfile(p.name).read()).hexdigest()==sha(p)
                   for p in (ROOT/'sources').iterdir() if p.is_file()}
    require(all(submitted.values()) and len(submitted)==17,'Submission snapshot mismatch')
    matches=[]
    datasets=[]
    for job in OLD:
        root=BASE/'results'/f'Vanda_mpi_recheck_{job}.stdct-mgmt-02'
        old=read(root/'benchmark/summary.json')
        prior=read(BASE/'evidence'/f'vanda_{job}_mpi_recheck/audit.json')
        require(prior['status']=='PASS','Historical audit incomplete')
        for p in (root/'sources').iterdir():
            other=ROOT/'sources'/p.name
            if other.is_file():
                matches.append(dict(historical_job=job,kind='source',name=p.name,
                                    sha256=sha(other),identical=sha(p)==sha(other)))
        for name in ('jacobi_serial','jacobi_mpi'):
            matches.append(dict(historical_job=job,kind='executable',name=name,
                                sha256=sha(ROOT/'bin'/name),identical=sha(ROOT/'bin'/name)==sha(root/'bin'/name)))
        datasets.append((job,root,old))
    require(len(matches)==36 and all(x['identical'] for x in matches),'Historical source/binary mismatch')
    for n in (1024,2048):
        datasets.append((NEW,ROOT,read(ROOT/f'benchmark/n{n}/summary.json')))
    rows=[]; samples=[]; comm=[]
    for job,root,d in datasets:
        groups=checked_rows(d)
        medians={(g['mode'],g['processes'],g['exchange']):g['median_seconds'] for g in groups}
        serial=medians['serial',1,'none']
        reference=next(r['result'] for r in d['runs'] if r['result']['mode']=='serial')
        new_reference=next(r['result'] for r in b['runs'] if r['n']==d['n'] and r['result']['mode']=='serial')
        require(all(reference[f]==new_reference[f] for f in FIELDS),'Same-size metrics differ between jobs')
        for r in d['runs']:
            rawdir=root/'benchmark' if job!=NEW else root/f"benchmark/n{d['n']}"
            require(read(rawdir/(r['id']+'.stdout.json'))==r['result'],'Changed comparison stdout')
            x=r['result']
            samples.append(dict(job_id=job,n=d['n'],host=d['host'],mode=x['mode'],
                                processes=x.get('mpi_processes',1),exchange=x.get('exchange','none'),
                                warmup=r['warmup'],repeat_index=r['repeat_index'],
                                sequence=r.get('sequence',''),compute_seconds=x['compute_seconds']))
        for g in groups:
            key=(g['mode'],g['processes'],g['exchange'])
            runs=[r for r in d['runs'] if not r['warmup'] and
                  (r['result']['mode'],r['result'].get('mpi_processes',1),r['result'].get('exchange','none'))==key]
            times=[r['result']['compute_seconds'] for r in runs]
            mpi_base=medians.get(('mpi',1,g['exchange']))
            rows.append(dict(job_id=job,n=d['n'],host=d['host'],mode=g['mode'],processes=g['processes'],
                             exchange=g['exchange'],median_seconds=g['median_seconds'],
                             min_seconds=min(times),max_seconds=max(times),
                             sample_cv_percent=100*statistics.stdev(times)/statistics.mean(times),
                             serial_baseline_seconds=serial,serial_speedup=serial/g['median_seconds'],
                             serial_efficiency=serial/g['median_seconds']/g['processes'],
                             mpi_p1_baseline_seconds=mpi_base,
                             mpi_speedup=mpi_base/g['median_seconds'] if mpi_base else None,
                             mpi_efficiency=mpi_base/g['median_seconds']/g['processes'] if mpi_base else None,
                             samples_seconds=times))
        for p in (1,2,4,12):
            paired={e:{r['repeat_index']:r['result']['compute_seconds'] for r in d['runs'] if not r['warmup'] and
                       (r['result']['mode'],r['result'].get('mpi_processes',1),r['result'].get('exchange','none'))==('mpi',p,e)}
                    for e in ('sendrecv','overlap')}
            sr,ov=paired['sendrecv'],paired['overlap']
            reductions=[100*(1-ov[k]/sr[k]) for k in range(9)]
            comm.append(dict(job_id=job,n=d['n'],host=d['host'],processes=p,
                             ratio_of_medians_reduction_percent=100*(1-medians['mpi',p,'overlap']/medians['mpi',p,'sendrecv']),
                             median_of_round_reductions_percent=statistics.median(reductions),
                             overlap_faster_rounds=sum(ov[k]<sr[k] for k in range(9)),rounds=9))
    asym=read(ROOT/'asymmetric_validation/summary.json')
    cases={c['id']:c for c in asym['cases']}
    asymrows=[dict(case_id=r['case_id'],n=r['result']['n'],mode=r['result']['mode'],
                   processes=r['processes'],exchange=r['exchange'],iterations=r['result']['iterations'],
                   tolerance=r['result']['tolerance'],status=r['result']['status'],
                   max_error=r['result']['max_error'],residual_inf=r['result']['residual_inf'],
                   independent_grid_max_difference=r['independent_grid_max_difference'],
                   covers=cases[r['case_id']]['covers']) for r in asym['runs']]
    # verify_small.py makes six extra serial prechecks. Only three numerical stdout
    # records are retained in run.log; do not claim six individually archived runs.
    precheck=[json.loads(line) for line in log.splitlines() if line.startswith('{"mode": "serial"')]
    require([d['n'] for d in precheck]==[8,16,32],'Unexpected retained precheck JSON')
    settings=read(ROOT/'sources/team_contract_v0.1.json')['validation']
    for d in precheck:
        c=dict(id='serial_precheck',n=d['n'],max_iters=100000,tolerance=1e-12,
               expected_exit_code=0,expected_status='update_tolerance_reached')
        validate(dict(result=d),c,settings)
    require('PASS: hand values, boundaries, exact solution, residual, iteration limit:' in log,'Serial precheck did not finish')
    review=dict(status='PASS',job_id=b['job_id'],host=b['host'],pin_cpus=b['pin_cpus'],
                numa_nodes=[1],primary_audit=primary,
                printed_sequence_and_timers_checked=180,builds_checked=built,
                uploaded_snapshot_files_identical=submitted,historical_identity_comparisons=matches,
                serial_precheck_executions_from_script=6,serial_precheck_numeric_log_records_rechecked=3,
                structured_solver_records=303,total_solver_executions_including_serial_precheck=309,
                asymmetric_max_full_grid_difference=max(x['independent_grid_max_difference'] for x in asymrows),
                validation_converged_runs=27,asymmetric_converged_runs=7,
                benchmark_interval_start_utc=b['runs'][0]['started_at_utc'],
                benchmark_interval_end_utc=b['runs'][-1]['finished_at_utc'],
                interpretation='Large chronological performance changes observed; system mechanism unmeasured.',
                experiment2='Deferred for this reporting round; summarize experiment1/3 first.',
                performance_samples_removed=0,new_cluster_executions_during_review=0)
    out.mkdir(parents=True)
    save(out/'new_job_review.json',review)
    csv_save(out/'source_binary_identity.csv',matches)
    csv_save(out/'performance_comparison.csv',[{k:v for k,v in r.items() if k!='samples_seconds'} for r in rows])
    csv_save(out/'measurement_samples.csv',samples)
    csv_save(out/'communication_comparison.csv',comm)
    csv_save(out/'asymmetric_validation.csv',asymrows)
    seqrows=[dict(sequence=r['sequence'],n=r['n'],repeat_index=r['repeat_index'],warmup=r['warmup'],
                  scale_block=r['scale_block'],within_scale_position=r['within_scale_position'],
                  mode=r['config'][0],processes=r['config'][1],exchange=r['config'][3],
                  started_at_cst=datetime.fromisoformat(r['started_at_utc']).astimezone(CST).isoformat(),
                  finished_at_cst=datetime.fromisoformat(r['finished_at_utc']).astimezone(CST).isoformat(),
                  compute_seconds=r['result']['compute_seconds']) for r in b['runs']]
    csv_save(out/'execution_sequence_1501884.csv',seqrows)
    scale_ratios=[]
    for row in [r for r in rows if r['job_id']==NEW and r['n']==1024]:
        other=next(r for r in rows if r['job_id']==NEW and r['n']==2048 and
                   (r['mode'],r['processes'],r['exchange'])==(row['mode'],row['processes'],row['exchange']))
        scale_ratios.append(dict(mode=row['mode'],processes=row['processes'],exchange=row['exchange'],
                                 n2048_median_over_n1024_median=other['median_seconds']/row['median_seconds']))
    csv_save(out/'same_allocation_scale_ratios.csv',scale_ratios)
    summary=dict(status='PASS',jobs=list(OLD)+( [NEW]),datasets=5,performance=rows,communication=comm,
                 structured_validation_numerical=383,structured_validation_rejections=16,
                 structured_independent_full_grid_executions=203,
                 performance_executions_including_warmups=450,performance_formal_executions=405,
                 rank_affinity_records=1950,
                 count_note='Four original suites (352 numerical + 16 rejections), plus 31 asymmetric cases. Extra verify_small prechecks excluded from these structured totals.',
                 new_job_review='new_job_review.json',source_identity_rows=len(matches))
    save(out/'summary.json',summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    colors={'sendrecv':'#206095','overlap':'#c96a20'}
    fig,axes=plt.subplots(2,3,figsize=(14,7.8),layout='constrained')
    for ri,n in enumerate((1024,2048)):
        for col,p in enumerate((1,4,12)):
            ax=axes[ri,col]
            if p==1:
                row=next(r for r in rows if r['job_id']==NEW and r['n']==n and r['mode']=='serial')
                ax.plot(range(9),row['samples_seconds'],'o-',color='#333333',label='Serial')
            for e in ('sendrecv','overlap'):
                row=next(r for r in rows if r['job_id']==NEW and r['n']==n and r['processes']==p and r['exchange']==e)
                ax.plot(range(9),row['samples_seconds'],'o-',color=colors[e],label=e)
            ax.set_title(f'n={n} | P={p}'+(' + serial' if p==1 else ''))
            ax.set_xlabel('Formal round (0-8)');ax.set_ylabel('Iteration time (s)')
            ax.set_xticks(range(9));ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('1501884 | all 9 formal samples | changing runtimes within one allocation')
    fig.savefig(out/'round_times.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
    for col,n in enumerate((1024,2048)):
        for e in ('sendrecv','overlap'):
            selected=[r for r in rows if r['job_id']==NEW and r['n']==n and r['exchange']==e]
            for ri,field in enumerate(('serial_speedup','mpi_speedup')):
                axes[ri,col].plot([r['processes'] for r in selected],[r[field] for r in selected],'o-',label=e,color=colors[e])
        for ax in axes[:,col]:
            ax.plot([1,12],[1,12],'--',color='#999999',label='Ideal linear')
            ax.set_xticks([1,2,4,12]);ax.set_ylim(0,12.5);ax.set_xlabel('MPI processes');ax.grid(alpha=.2)
        axes[0,col].set_title(f'n={n}')
    axes[0,0].set_ylabel('Speedup vs this-scale serial')
    axes[1,0].set_ylabel('Speedup vs this-strategy MPI P=1')
    axes[0,1].legend(fontsize=8)
    fig.suptitle('1501884 | full-sample medians | substantial round variation; no samples removed')
    fig.savefig(out/'dual_scale_scaling.png',dpi=180);plt.close(fig)
    palette={'1499881':'#206095','1500222':'#438560','1500271':'#9c5984',NEW:'#d06924'}
    fig,axes=plt.subplots(2,2,figsize=(13,9),layout='constrained')
    labels=['Serial','P1 SR','P1 OV','P2 SR','P2 OV','P4 SR','P4 OV','P12 SR','P12 OV']
    for col,n in enumerate((1024,2048)):
        jobs=[job for job,_,d in datasets if d['n']==n]
        for job in jobs:
            selected=[r for r in rows if r['job_id']==job and r['n']==n]
            ax=axes[0,col]
            ax.errorbar(range(9),[r['median_seconds'] for r in selected],
                        yerr=[[r['median_seconds']-r['min_seconds'] for r in selected],
                              [r['max_seconds']-r['median_seconds'] for r in selected]],
                        marker='o',capsize=3,color=palette[job],label=job)
            current=[c for c in comm if c['job_id']==job and c['n']==n and c['processes']>1]
            axes[1,col].plot([c['processes'] for c in current],
                             [c['ratio_of_medians_reduction_percent'] for c in current],
                             'o-',color=palette[job],label=job)
        axes[0,col].set_yscale('log');axes[0,col].set_xticks(range(9),labels,rotation=40,ha='right')
        axes[0,col].set_ylabel('Iteration time (s, log scale)');axes[0,col].set_title(f'n={n} | median and min-max')
        axes[1,col].axhline(0,ls='--',color='#999999');axes[1,col].set_xticks([2,4,12])
        axes[1,col].set_xlabel('MPI processes');axes[1,col].set_ylabel('Overlap reduction: ratio of medians (%)')
        for ax in axes[:,col]:
            ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Historical context | allocations kept separate | min-max bars are not confidence intervals')
    fig.savefig(out/'historical_context.png',dpi=180);plt.close(fig)
    # Preserve selected raw evidence alongside the reviewed analysis, without touching raw.
    evidence=BASE/'evidence/vanda_1501884_ab_supplement'
    for name in ('qstat_full.txt','qstat_at_start.txt','run.log','metadata.txt','lscpu.txt','pin_cpus.txt',
                 'process_status.txt','source_sha256.txt','executable_sha256.txt','pbs_nodefile.txt'):
        if (evidence/name).exists():
            require(sha(ROOT/name)==sha(evidence/name),'Selected evidence differs')
        else:
            shutil.copy2(ROOT/name,evidence/name)
    for n in (1024,2048):
        target=evidence/f'benchmark_n{n}_summary.json'
        source=ROOT/f'benchmark/n{n}/summary.json'
        if target.exists():
            require(sha(target)==sha(source),'Selected scale summary differs')
        else:
            shutil.copy2(source,target)
    for folder,name in [('validation','validation_summary.json'),('asymmetric_validation','asymmetric_validation_summary.json')]:
        source=ROOT/folder/'summary.json';target=evidence/name
        if target.exists():
            require(sha(target)==sha(source),'Selected validation summary differs')
        else:
            shutil.copy2(source,target)
    if (evidence/'supplemental_review.json').exists():
        require(read(evidence/'supplemental_review.json')==review,'Existing review differs')
    else:
        save(evidence/'supplemental_review.json',review)
    print(json.dumps(dict(status='PASS',out=str(out),groups=len(rows),performance_executions=len(samples),
                          communication_rows=len(comm),identity_comparisons=len(matches),
                          original_numerical=352,asymmetric_numerical=31),ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
