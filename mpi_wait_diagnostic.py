"""Bounded wait-placement diagnostic: 45 correctness + 54 performance launches.
No instrumentation, serial benchmark, extra matrix or automatic reruns.
Run requires PBS; audit reads saved raw files without launching any program.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import statistics
import subprocess
import sys
import tarfile

from benchmark_parallel import check_affinity

BASE=Path(__file__).resolve().parent
SCHEMES=('sendrecv','immediate','overlap')
COMBINATIONS=((2048,2),(2048,12),(1024,12))
CASES=[
    dict(id='one_cell',n=1,p=1,k=1,tol=0,covers='one row, PROC_NULL, odd swap'),
    dict(id='one_per_rank',n=2,p=2,k=2,tol=0,covers='one local row, even swap'),
    dict(id='two_per_rank',n=4,p=2,k=3,tol=0,covers='two local rows, no interior'),
    dict(id='uneven_interiors',n=7,p=2,k=31,tol=0,covers='4+3 rows, interior before edges'),
    dict(id='uneven_single',n=7,p=4,k=31,tol=0,covers='2+2+2+1 rows, single-row neighbor'),
    dict(id='four_double',n=8,p=4,k=30,tol=0,covers='four ranks with two rows'),
    dict(id='converged',n=7,p=2,k=10000,tol=1e-12,covers='global stopping, refreshed residual'),
    dict(id='twelve_single',n=12,p=12,k=3,tol=0,covers='12 ranks each one row; independent metrics'),
    dict(id='twelve_double',n=24,p=12,k=4,tol=0,covers='12 ranks each two rows; independent metrics'),
]
FIELDS=('max_update','max_error','residual_inf','boundary_error')
TAG='wait-placement-v1'


def require(ok,message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def validation_plan():
    return [dict(id=f"{c['id']}_{kind}_{e}",case_id=c['id'],n=c['n'],p=c['p'],k=c['k'],tol=c['tol'],
                 kind=kind,exchange=e) for c in CASES
            for kind,schemes in (('original',('sendrecv','overlap')),('diagnostic',SCHEMES))
            for e in schemes]


def performance_plan():
    # Five unique permutations out of six. Position counts are 1 or 2, not exact balance.
    permutations=list(itertools.permutations(SCHEMES))
    plan=[]
    for repeat in range(-1,5):
        offset=max(repeat,0)%3
        combos=list(range(3))
        if repeat>=0:
            combos=combos[offset:]+combos[:offset]
        for case_position,ci in enumerate(combos):
            n,p=COMBINATIONS[ci]
            order=SCHEMES if repeat<0 else permutations[(repeat+ci)%6]
            for position,e in enumerate(order):
                plan.append(dict(id=f'n{n}_p{p}_{e}_r{repeat}',sequence=len(plan),n=n,p=p,k=1000,tol=0,
                                 kind='diagnostic',exchange=e,repeat_index=repeat,warmup=repeat<0,
                                 combo_index=ci,case_position=case_position,scheme_position=position))
    return plan


def oracle(case):
    n=case['n']
    grid=[[(i+j)/(n+1) if i in (0,n+1) or j in (0,n+1) else 0.0
           for j in range(n+2)] for i in range(n+2)]
    for k in range(1,case['k']+1):
        new=[row[:] for row in grid]
        delta=0.0
        for i in range(1,n+1):
            for j in range(1,n+1):
                value=(grid[i-1][j]+grid[i+1][j]+grid[i][j-1]+grid[i][j+1])/4
                new[i][j]=value
                delta=max(delta,abs(value-grid[i][j]))
        grid=new
        if case['tol']>0 and delta<=case['tol']:
            break
    error=max(abs(grid[i][j]-(i+j)/(n+1)) for i in range(1,n+1) for j in range(1,n+1))
    residual=max(abs(4*grid[i][j]-grid[i-1][j]-grid[i+1][j]-grid[i][j-1]-grid[i][j+1])*(n+1)**2
                 for i in range(1,n+1) for j in range(1,n+1))
    return dict(grid=grid,iterations=k,max_update=delta,max_error=error,residual_inf=residual,
                boundary_error=0.0,status='fixed_iterations' if case['tol']==0 else
                ('update_tolerance_reached' if delta<=case['tol'] else 'iteration_limit'))


def validate(data,item,expected):
    require((data['mode'],data['n'],data['mpi_processes'],data['threads'],data['nodes'],data['exchange'],data['tolerance'])==
            ('mpi',item['n'],item['p'],1,1,item['exchange'],item['tol']),'Wrong MPI workload')
    require(data.get('diagnostic')==(TAG if item['kind']=='diagnostic' else None),'Wrong program identity')
    require(all(math.isfinite(data[f]) and data[f]>=0 for f in FIELDS+('compute_seconds',)),'Nonfinite/negative value')
    require(data['boundary_error']<=1e-14,'Boundary mismatch')
    require(all(math.isclose(data[f],expected[f],rel_tol=1e-10,abs_tol=1e-12) for f in FIELDS),'Independent/global metric mismatch')
    require(data['iterations']==expected['iterations'] and data['status']==expected['status'],'Wrong iterations/status')
    if item['n']<=8:
        grid=data['grid'];width=item['n']+2
        require(len(grid)==width and all(len(row)==width for row in grid),'Full-grid shape')
        differences=[abs(grid[i][j]-expected['grid'][i][j]) for i in range(width) for j in range(width)]
        require(all(math.isfinite(v) for v in differences) and max(differences)<=1e-12,'Full-grid mismatch')
    if item['tol']>0:
        require(data['status']=='update_tolerance_reached' and data['max_update']<=item['tol'] and
                data['max_error']<=1e-8 and data['residual_inf']<=1e-7,'Small convergence criteria')


def command(exe,item,cpus,launcher):
    return (shlex.split(launcher)+['--bind-to','none','--map-by','slot','-np',str(item['p']),
            sys.executable,str(BASE/'pin_cpu.py'),'--cpus',','.join(map(str,cpus)),'--',str(exe),
            str(item['n']),str(item['k']),str(item['tol']),'--exchange',item['exchange']])


def execute(exe,item,folder,cpus,launcher,host):
    record=dict(item,command=command(exe,item,cpus,launcher),exit_code=None,
                started_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        run=subprocess.run(record['command'],capture_output=True,text=True,timeout=180,
                           env=dict(os.environ,OMP_NUM_THREADS='1',OMP_DYNAMIC='FALSE'))
        stdout,stderr=run.stdout,run.stderr
        record['exit_code']=run.returncode
    except subprocess.TimeoutExpired as error:
        stdout=error.stdout or '';stderr=error.stderr or ''
        if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
        if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
        record['timeout']=True
    (folder/(item['id']+'.stdout.json')).write_text(stdout,encoding='utf-8')
    (folder/(item['id']+'.stderr.txt')).write_text(stderr,encoding='utf-8')
    record['finished_at_utc']=datetime.now(timezone.utc).isoformat()
    if record['exit_code']==0:
        record['result']=json.loads(stdout)
        record['affinity_before_exec']=check_affinity(stderr,cpus,item['p'],host)
    return record


def statistics_for(runs):
    groups=[];comparisons=[]
    for n,p in COMBINATIONS:
        lookup={}
        for e in SCHEMES:
            selected=[r for r in runs if not r['warmup'] and (r['n'],r['p'],r['exchange'])==(n,p,e)]
            values=[r['result']['compute_seconds'] for r in selected]
            require(len(values)==5 and min(values)>0,'Wrong sample count/timing')
            lookup[e]={r['repeat_index']:r['result']['compute_seconds'] for r in selected}
            groups.append(dict(n=n,p=p,exchange=e,median_seconds=statistics.median(values),
                               min_seconds=min(values),max_seconds=max(values),
                               sample_cv_percent=100*statistics.stdev(values)/statistics.mean(values),
                               max_over_min=max(values)/min(values),samples_seconds=values))
        for baseline,candidate in (('sendrecv','immediate'),('immediate','overlap'),('sendrecv','overlap')):
            first,last=lookup[baseline],lookup[candidate]
            reductions=[100*(1-last[k]/first[k]) for k in range(5)]
            comparisons.append(dict(n=n,p=p,baseline=baseline,candidate=candidate,
                                    ratio_of_medians_reduction_percent=100*(1-statistics.median(last.values())/statistics.median(first.values())),
                                    median_of_round_reductions_percent=statistics.median(reductions),
                                    candidate_faster_rounds=sum(last[k]<first[k] for k in range(5)),rounds=5,
                                    round_reductions_percent=reductions))
    return groups,comparisons


def run_experiment(args):
    require(os.environ.get('PBS_JOBID'),'Diagnostic performance runs require PBS allocation')
    cpus=[int(x) for x in args.pin_cpus.split(',')]
    require(len(cpus)==len(set(cpus))==12 and hasattr(os,'sched_getaffinity'),'Need twelve allocated Linux CPUs')
    require(set(cpus)==set(os.sched_getaffinity(0)),'CPU list differs from inherited mask')
    binaries={kind:(args.build_dir/name).resolve(strict=True) for kind,name in
              [('original','jacobi_mpi'),('diagnostic','jacobi_mpi_wait_diagnostic')]}
    expected_fixed=read(BASE/'mpi_wait_reference.json')
    require(expected_fixed['production_source_sha256']==sha(BASE/'jacobi_mpi.cpp'),'Numeric reference source differs')
    out=args.out_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    for folder in ('validation','performance'):(out/folder).mkdir()
    state=dict(schema=TAG,status='RUNNING',job_id=os.environ['PBS_JOBID'],host=platform.node(),
               pin_cpus=cpus,validation_cases=CASES,combinations=list(map(list,COMBINATIONS)),
               performance_plan=performance_plan(),validation_runs=[],performance_runs=[],
               source_sha256={p.name:sha(p) for p in BASE.iterdir() if p.is_file()},
               executable_sha256={k:sha(p) for k,p in binaries.items()},groups=[],comparisons=[],
               note='Uninstrumented diagnostic totals. No serial speedup; no cross-job timing baseline.')
    save(out/'execution_plan.json',state['performance_plan'])
    save(out/'summary.json',state)
    try:
        oracles={c['id']:oracle(c) for c in CASES}
        originals={}
        for item in validation_plan():
            record=execute(binaries[item['kind']],item,out/'validation',cpus,args.launcher,state['host'])
            state['validation_runs'].append(record);save(out/'summary.json',state)
            require(record['exit_code']==0,'Correctness execution failed: '+item['id'])
            validate(record['result'],item,oracles[item['case_id']])
            if item['kind']=='original':
                originals[item['case_id'],item['exchange']]=record['result']
            else:
                original=originals[item['case_id'],'sendrecv']
                require(all(math.isclose(record['result'][f],original[f],rel_tol=1e-10,abs_tol=1e-12) for f in FIELDS),'Diagnostic differs from original')
            record['validation']='PASS'
            print('PASS correctness '+item['id'],flush=True)
            save(out/'summary.json',state)
        require(len(state['validation_runs'])==45,'Unexpected validation count')
        state['correctness_completed_before_performance']=True
        for item in state['performance_plan']:
            record=execute(binaries['diagnostic'],item,out/'performance',cpus,args.launcher,state['host'])
            state['performance_runs'].append(record);save(out/'summary.json',state)
            require(record['exit_code']==0,'Performance execution failed: '+item['id'])
            expected=dict(expected_fixed['n_values'][str(item['n'])],iterations=1000,status='fixed_iterations')
            validate(record['result'],item,expected)
            record['validation']='PASS'
            print(f"seq={item['sequence']} {item['id']}: {record['result']['compute_seconds']:.6f}s",flush=True)
            save(out/'summary.json',state)
        state['groups'],state['comparisons']=statistics_for(state['performance_runs'])
        state['status']='PASS'
    except Exception as error:
        state.update(status='FAIL',error=str(error))
        raise
    finally:
        save(out/'summary.json',state)
    print('PASS: 45 correctness + 54 performance (9 warmups + 45 formal); no phase instrumentation')



def archive_checked(root,archive):
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        with archive.open('xb') as stream:
            with tarfile.open(fileobj=stream,mode='w:gz') as tar:
                tar.add(root,arcname=root.name)
    files={root.name+'/'+p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
    with tarfile.open(archive,'r:gz') as tar:
        regular=[m for m in tar.getmembers() if m.isfile()]
        require(len(regular)==len({m.name for m in regular}),'Duplicate archive member')
        members={m.name:m for m in regular}
        require(members.keys()==files.keys(),'Archive inventory mismatch')
        for name,path in files.items():
            require(hashlib.sha256(tar.extractfile(members[name]).read()).hexdigest()==sha(path),'Archive member mismatch')
    return dict(path=str(archive),sha256=sha(archive),files=len(files),member_by_member_checked=True)



def verify_saved_statistics(groups,comparisons,state):
    # Python 3.10/3.11 stdev/mean may differ in the final rounded bit.
    # Only derived CV gets a tight tolerance; samples and other statistics stay exact.
    require(len(groups)==len(state['groups']),'Saved group count differs')
    for current,saved in zip(groups,state['groups']):
        require(set(current)==set(saved),'Saved statistic fields differ')
        require({k:v for k,v in current.items() if k!='sample_cv_percent'}==
                {k:v for k,v in saved.items() if k!='sample_cv_percent'},'Saved exact statistics differ')
        require(math.isfinite(saved['sample_cv_percent']) and
                math.isclose(current['sample_cv_percent'],saved['sample_cv_percent'],rel_tol=1e-12,abs_tol=1e-14),
                'Saved CV differs beyond cross-Python rounding tolerance')
    require(comparisons==state['comparisons'],'Saved comparisons differ')


def audit(args):
    root=args.results.resolve();out=args.out_dir.resolve()
    require(not out.exists() and not out.is_relative_to(root),'Audit output must be new and outside raw')
    required={'sources','bin','diagnostic','run.log','metadata.txt','environment.txt','lscpu.txt',
              'qstat_at_start.txt','qstat_full.txt','process_status.txt','pbs_nodefile.txt','pin_cpus.txt',
              'source_sha256.txt','executable_sha256.txt'}
    require({p.name for p in root.iterdir()}==required,'Raw root inventory')
    require({p.name for p in (root/'diagnostic').iterdir()}=={'summary.json','execution_plan.json','validation','performance'},'Diagnostic root inventory')
    state=read(root/'diagnostic/summary.json')
    require((state['schema'],state['status'])==(TAG,'PASS'),'Incomplete diagnostic')
    require(state['validation_cases']==CASES and state['combinations']==list(map(list,COMBINATIONS)),'Changed case matrix')
    qstat=(root/'qstat_full.txt').read_text(encoding='utf-8')
    require(re.search(r'^Job Id:\s*'+re.escape(state['job_id'])+r'\s*$',qstat,re.M),'Wrong final job')
    for expr in (r'job_state\s*=\s*F\b',r'Exit_status\s*=\s*0\b',r'Resource_List.nodect\s*=\s*1\b',
                 r'Resource_List.ncpus\s*=\s*12\b',r'Resource_List.mem\s*=\s*4gb\b'):
        require(re.search(expr,qstat,re.I),'PBS completion/resources')
    require('exec_host = '+state['host']+'/' in qstat,'PBS/solver host mismatch')
    log=(root/'run.log').read_text(encoding='utf-8')
    require(log.rstrip().endswith('RUN_STATUS=PASSED\nJOB_EXIT_STATUS=0'),'Failed run log')
    require(log.count('+ mpicxx -std=c++17 -O2 -Wall -Wextra -Wpedantic ')==2,'Unexpected MPI builds')
    require(re.findall(r'^PASS correctness (\S+)$',log,re.M)==[x['id'] for x in validation_plan()],'Correctness log matrix')
    require('PASS: 45 correctness + 54 performance (9 warmups + 45 formal); no phase instrumentation' in log,'Missing execution completion marker')
    sources={};binaries={}
    for name,folder,mapping in [('source_sha256.txt','sources',sources),('executable_sha256.txt','bin',binaries)]:
        for line in (root/name).read_text().splitlines():
            digest,path=line.split(maxsplit=1);filename=path.strip().rsplit('/',1)[-1]
            require(filename not in mapping and sha(root/folder/filename)==digest,'Hash mismatch')
            mapping[filename]=digest
        require(set(mapping)=={p.name for p in (root/folder).iterdir() if p.is_file()},'Manifest inventory')
    require(state['source_sha256']==sources,'Source map differs')
    require(state['executable_sha256']==dict(original=binaries['jacobi_mpi'],diagnostic=binaries['jacobi_mpi_wait_diagnostic']),'Binary map differs')
    cpus=state['pin_cpus']
    require(len(cpus)==len(set(cpus))==12,'CPU list')
    allowed=re.search(r'Cpus_allowed_list:\s*([^\r\n]+)',(root/'process_status.txt').read_text())
    def expand(s):
        result=[]
        for part in s.split(','):
            limits=list(map(int,part.strip().split('-')));result.extend(range(limits[0],limits[-1]+1))
        return result
    require(allowed is not None and set(expand(allowed.group(1)))==set(cpus),'Inherited mask')
    require((root/'pin_cpus.txt').read_text().strip()=='PIN_CPUS='+','.join(map(str,cpus)),'CPU record differs')
    require(len((root/'pbs_nodefile.txt').read_text().splitlines())==12,'PBS slots')
    expected_fixed=read(root/'sources/mpi_wait_reference.json')
    require(expected_fixed['production_source_sha256']==sources['jacobi_mpi.cpp'],'Numerical reference source identity')
    validation_expected=validation_plan();performance_expected=performance_plan()
    require(state['performance_plan']==performance_expected==read(root/'diagnostic/execution_plan.json'),'Execution plan differs')
    require(state['correctness_completed_before_performance'] is True,'Correctness gate missing')
    require(len(state['validation_runs'])==45 and len(state['performance_runs'])==54,'Execution count')
    oracles={c['id']:oracle(c) for c in CASES}
    affinity=0; originals={}
    for section,runs,expected_plan in [('validation',state['validation_runs'],validation_expected),
                                       ('performance',state['performance_runs'],performance_expected)]:
        folder=root/'diagnostic'/section
        expected_files={r['id']+suffix for r in runs for suffix in ('.stdout.json','.stderr.txt')}
        require({p.name for p in folder.iterdir()}==expected_files and len(runs)==len({r['id'] for r in runs}),'Raw inventory')
        for r,item in zip(runs,expected_plan):
            require(all(r.get(k)==v for k,v in item.items()),'Actual order differs')
            require(r['exit_code']==0 and r['validation']=='PASS','Failed raw execution')
            data=read(folder/(r['id']+'.stdout.json'))
            require(data==r['result'],'Changed raw JSON')
            expected=oracles[item['case_id']] if section=='validation' else dict(expected_fixed['n_values'][str(item['n'])],iterations=1000,status='fixed_iterations')
            validate(data,item,expected)
            stderr=(folder/(r['id']+'.stderr.txt')).read_text(encoding='utf-8')
            actual=check_affinity(stderr,cpus,item['p'],state['host'])
            require(actual==r['affinity_before_exec'],'Affinity differs');affinity+=len(actual)
            cmd=r['command'];index=cmd.index('--')
            require(Path(cmd[index+1]).name==('jacobi_mpi' if item['kind']=='original' else 'jacobi_mpi_wait_diagnostic'),'Wrong executable command')
            require(cmd[-5:]==[str(item['n']),str(item['k']),str(item['tol']),'--exchange',item['exchange']],'Wrong command workload')
            require(cmd[cmd.index('-np')+1]==str(item['p']) and cmd[cmd.index('--bind-to')+1]=='none' and
                    cmd[cmd.index('--map-by')+1]=='slot' and cmd[cmd.index('--cpus')+1]==','.join(map(str,cpus)),'Wrong launcher/mapping')
            require(datetime.fromisoformat(r['started_at_utc'])<=datetime.fromisoformat(r['finished_at_utc']),'Bad execution timestamps')
            if section=='validation':
                if item['kind']=='original':originals[item['case_id'],item['exchange']]=data
                else:require(all(math.isclose(data[f],originals[item['case_id'],'sendrecv'][f],rel_tol=1e-10,abs_tol=1e-12) for f in FIELDS),'Original/diagnostic disagreement')
    all_runs=state['validation_runs']+state['performance_runs']
    require(all(datetime.fromisoformat(a['finished_at_utc'])<=datetime.fromisoformat(b['started_at_utc']) for a,b in zip(all_runs,all_runs[1:])),'Correctness/performance timeline differs')
    require(affinity==673,'Wrong total affinity records')
    groups,comparisons=statistics_for(state['performance_runs'])
    verify_saved_statistics(groups,comparisons,state)
    for n,p in COMBINATIONS:
        runs=[r for r in state['performance_runs'] if (r['n'],r['p'])==(n,p)]
        require(sum(r['warmup'] for r in runs)==3,'Warmup count')
        for e in SCHEMES:
            require(sum(r['warmup'] and r['exchange']==e for r in runs)==1,'Per-scheme warmup count')
            positions=Counter(r['scheme_position'] for r in runs if not r['warmup'] and r['exchange']==e)
            require(sorted(positions.values())==[1,2,2],'Five-round order balance')
    printed=re.findall(r'^seq=(\d+) (\S+): ([0-9.]+)s$',log,re.M)
    require(len(printed)==54,'Printed sequence count')
    require(all((int(seq),label,seconds)==(r['sequence'],r['id'],f"{r['result']['compute_seconds']:.6f}")
                for (seq,label,seconds),r in zip(printed,state['performance_runs'])),'Printed sequence changed')
    archived=archive_checked(root,root.parent/'raw_archives'/(root.name+'.tar.gz'))
    out.mkdir(parents=True)
    def csv_save(name,rows):
        with (out/name).open('w',newline='',encoding='utf-8') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    csv_save('performance.csv',[{k:v for k,v in g.items() if k!='samples_seconds'} for g in groups])
    csv_save('comparisons.csv',[{k:v for k,v in c.items() if k!='round_reductions_percent'} for c in comparisons])
    csv_save('all_samples.csv',[dict(sequence=r['sequence'],n=r['n'],p=r['p'],exchange=r['exchange'],
                                   repeat_index=r['repeat_index'],warmup=r['warmup'],scheme_position=r['scheme_position'],
                                   started_at_utc=r['started_at_utc'],finished_at_utc=r['finished_at_utc'],
                                   compute_seconds=r['result']['compute_seconds']) for r in state['performance_runs']])
    warnings=['libpbs.so.0 warning retained'] if any('libpbs.so.0' in p.read_text(encoding='utf-8') for p in (root/'diagnostic').rglob('*.stderr.txt')) else []
    result=dict(status='PASS',job_id=state['job_id'],host=state['host'],validation_executions=45,
                performance_executions=54,performance_warmups=9,performance_formal=45,
                affinity_records=affinity,groups=groups,comparisons=comparisons,raw_archive=archived,warnings=warnings,
                meaning='Immediate vs overlap changes wait scheduling; no claim of proved underlying overlap.')
    save(out/'audit.json',result)
    table='\n'.join(f"| {g['n']} | {g['p']} | {g['exchange']} | {g['median_seconds']:.6f} | {g['min_seconds']:.6f}–{g['max_seconds']:.6f} | {g['sample_cv_percent']:.2f}% |" for g in groups)
    paired='\n'.join(f"| {c['n']} | {c['p']} | {c['baseline']}→{c['candidate']} | {c['ratio_of_medians_reduction_percent']:.2f}% | {c['median_of_round_reductions_percent']:.2f}% | {c['candidate_faster_rounds']}/5 |" for c in comparisons)
    text=f"""# 等待位置诊断：{state['job_id']}

仅诊断总迭代时间；固定K=1000/tol=0，不宣称收敛，不计算相对历史串行的加速比。
45次正确性与673条验证/性能执行前绑定、54次性能（9预热+45正式）、工作量、数值、哈希、实际顺序和统计通过重核。
源码/程序以本作业快照为准，与历史正式矩阵分开。五轮三方案位置计数1或2次，非完全平衡。

| n | P | 方案 | 中位秒 | min–max秒 | 样本CV |
|---:|---:|---|---:|---|---:|
{table}

| n | P | 对照 | 中位数之比降低 | 同轮降低的中位数 | 候选更快 |
|---:|---:|---|---:|---:|---:|
{paired}

三方案在每个组合内紧邻执行，仍是先后运行而非同时运行。检查完整逐轮图，不删除慢样本或自动追加重复。
SR与立即等待的差异同时包含接口、更新划分/顺序及可能代码生成差异，不能称为纯API成本。
立即等待与overlap共享数值计算及内部/边界顺序，仅等待位置改变；差异先描述为等待/计算调度收益。
总耗时及MPI非阻塞API不足以证明底层有效通信重叠；没有内部阶段插桩。
如果再次发生明显时间变化，结论降为不确定，保留结果结束本轮，不不断重提交直到变好。

原始包：{archived['path']}；SHA-256：{archived['sha256']}；{archived['files']}文件逐成员核对。
环境警告：{'; '.join(warnings) or 'stderr未检出libpbs.so.0警告'}。单节点不证明多节点PBS集成。
AI协助工具和分析；用户完成Vanda操作与最终报告人工确认。未提交Git或发送邮件。
"""
    if args.plots:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(1,3,figsize=(13,4.4),layout='constrained')
        colors={'sendrecv':'#206095','immediate':'#7c6289','overlap':'#d06924'}
        for ax,(n,p) in zip(axes,COMBINATIONS):
            for e in SCHEMES:
                values=next(g['samples_seconds'] for g in groups if (g['n'],g['p'],g['exchange'])==(n,p,e))
                ax.plot(range(5),values,'o-',label=e,color=colors[e])
            ax.set_title(f'n={n}, P={p}');ax.set_xlabel('Formal round (0-4)')
            ax.set_ylabel('Iteration time (s)');ax.set_xticks(range(5));ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.suptitle('Uninstrumented wait-placement diagnostic | all formal samples retained')
        fig.savefig(out/'round_times.png',dpi=180);plt.close(fig)
        text+='\n![全部正式样本](round_times.png)\n'
    (out/'analysis.md').write_text(text,encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    subs=ap.add_subparsers(dest='action',required=True)
    run=subs.add_parser('run')
    run.add_argument('--build-dir',type=Path,required=True);run.add_argument('--out-dir',type=Path,required=True)
    run.add_argument('--pin-cpus',required=True);run.add_argument('--launcher',default='mpirun')
    check=subs.add_parser('audit')
    check.add_argument('--results',type=Path,required=True);check.add_argument('--out-dir',type=Path,required=True)
    check.add_argument('--plots',action='store_true')
    args=ap.parse_args()
    run_experiment(args) if args.action=='run' else audit(args)


if __name__=='__main__':
    main()
