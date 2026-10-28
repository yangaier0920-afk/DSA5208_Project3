"""Audit dual-scale raw output, original validation, asymmetric grids and archive.
Existing raw data are read-only; output directories must be new. Standard library,
with optional matplotlib figures. This does not launch any solver.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import tarfile
from analyze_results import checked_rows, make_plots, require
from benchmark_parallel import check_affinity
from prepare_team_references import validate
from verify_asymmetric import CASES, oracle, validate_result

FIELDS=('max_update','max_error','residual_inf','boundary_error')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_record(directory, r):
    raw=(directory/(r['id']+'.stdout.json')).read_text(encoding='utf-8')
    stderr=(directory/(r['id']+'.stderr.txt')).read_text(encoding='utf-8')
    if 'result' in r:
        require(read(directory/(r['id']+'.stdout.json'))==r['result'], 'Changed stdout '+r['id'])
    else:
        require(r['exit_code']!=0 and not raw.strip(), 'Invalid input not rejected')
    return stderr


def inventory(directory, runs, extras=('summary.json',)):
    names=set(extras)
    for r in runs:
        names.update((r['id']+'.stdout.json',r['id']+'.stderr.txt'))
    require({p.name for p in directory.iterdir()}==names, 'Raw inventory mismatch: '+str(directory))
    require(len(runs)==len({r['id'] for r in runs}), 'Duplicate raw record ID')


def hash_manifest(root, name, directory):
    seen={}
    for line in (root/name).read_text(encoding='utf-8').splitlines():
        digest,path=line.split(maxsplit=1)
        filename=path.strip().lstrip('*').replace('\\','/').rsplit('/',1)[-1]
        require(filename not in seen, 'Duplicate manifest file')
        require(sha(root/directory/filename)==digest, 'Hash mismatch: '+filename)
        seen[filename]=digest
    require(set(seen)=={p.name for p in (root/directory).iterdir() if p.is_file()}, 'Incomplete hash manifest')
    return seen


def check_hash_map(mapping, actual):
    require(all(actual.get(k)==v for k,v in mapping.items()), 'Summary hash mismatch')


def check_validation(root, b, sources, binaries):
    v=read(root/'validation/summary.json')
    require((v['status'],v['job_id'],v['host'])==('PASS',b['job_id'],b['host']), 'Validation identity')
    check_hash_map(v['sha256'],sources)
    require(v['executable_sha256']=={m:binaries['jacobi_'+m] for m in ('serial','mpi')}, 'Validation binary hashes')
    config=read(root/'sources/team_contract_v0.1.json')
    cases=config['validation']['cases']+[
        dict(id='one_row_per_rank',n=4,max_iters=2,tolerance=0,expected_exit_code=0,expected_status='fixed_iterations'),
        dict(id='three_rows_per_rank',n=12,max_iters=17,tolerance=0,expected_exit_code=0,expected_status='fixed_iterations')]
    expected={c['id']+'_serial':(c,1,'none') for c in cases}
    expected.update({f"{c['id']}_mpi_p{p}_t1_{e}":(c,p,e)
                     for c in cases for p in (1,2,4,12) if p<=c['n'] for e in ('sendrecv','overlap')})
    rejected={'mpi_too_many_ranks':['1','1','0'],
              'mpi_negative_tolerance':['8','2','-1'],
              'mpi_nan_tolerance':['8','2','nan'],
              'mpi_bad_exchange':['8','2','0','--exchange','bad']}
    require(Counter(r['id'] for r in v['runs'])==Counter(list(expected)+list(rejected)), 'Validation case matrix')
    inventory(root/'validation',v['runs'])
    serials={r['id']:r['result'] for r in v['runs'] if r['id'].endswith('_serial')}
    for r in v['runs']:
        raw_record(root/'validation',r)
        require(r['validation']=='PASS', 'Recorded numerical failure')
        if r['id'] in rejected:
            require('result' not in r and r['command'][-len(rejected[r['id']]):]==rejected[r['id']], 'Wrong rejection command')
            continue
        case,p,e=expected[r['id']]
        d=r['result']
        require(r['exit_code']==case['expected_exit_code'], 'Unexpected validation exit')
        require(d['n']==case['n'] and d['tolerance']==case['tolerance'] and d['threads']==r['threads']==1, 'Validation workload')
        require(all(math.isfinite(d[f]) and d[f]>=0 for f in FIELDS+('compute_seconds',)), 'Invalid numerical metrics')
        validate(dict(r),case,config['validation'])
        require(r['processes']==p, 'Wrong validation process count')
        suffix=[str(case['n']),str(case['max_iters']),str(case['tolerance'])]
        if e!='none':
            require(d['mode']=='mpi' and (d['mpi_processes'],d['exchange'],d['nodes'])==(p,e,1), 'Wrong validation MPI')
            suffix+=['--exchange',e]
        else:
            require(d['mode']=='serial', 'Wrong validation serial mode')
        # Numeric tolerance formatting can be 0 or 0.0; verify values, not spelling.
        tail=r['command'][-len(suffix):]
        require(tail[:2]==suffix[:2] and float(tail[2])==case['tolerance'] and tail[3:]==suffix[3:], 'Validation command')
        for f in FIELDS:
            require(math.isclose(d[f],serials[case['id']+'_serial'][f],rel_tol=1e-10,abs_tol=1e-12), 'Validation serial mismatch')
    return dict(total=len(v['runs']),numerical=len(expected),rejections=len(rejected),
                full_grid=sum('grid' in r.get('result',{}) for r in v['runs']))


def check_asymmetric(root,b,sources,binaries):
    folder=root/'asymmetric_validation'
    a=read(folder/'summary.json')
    require((a['status'],a['job_id'],a['host'],a['problem'])==('PASS',b['job_id'],b['host'],'x+2y+xy'), 'Asymmetric identity')
    require(a['cases']==CASES, 'Changed asymmetric case definitions')
    check_hash_map(a['source_sha256'],sources)
    require(a['executable_sha256']=={m:binaries['jacobi_'+m+'_asymmetric'] for m in ('serial','mpi')}, 'Asymmetric binary hashes')
    expected={f"{c['id']}_serial_p1_none":(c,'serial',1,'none') for c in CASES}
    expected.update({f"{c['id']}_mpi_p{p}_{e}":(c,'mpi',p,e)
                     for c in CASES for p in c['processes'] for e in ('sendrecv','overlap')})
    require(Counter(r['id'] for r in a['runs'])==Counter(expected.keys()), 'Asymmetric matrix incomplete')
    inventory(folder,a['runs'])
    oracles={c['id']:oracle(c) for c in CASES}
    for r in a['runs']:
        raw_record(folder,r)
        c,m,p,e=expected[r['id']]
        require(r['exit_code']==0 and r['validation']=='PASS', 'Asymmetric execution failed')
        d=r['result']
        require(d['mode']==m and d['threads']==1 and r['processes']==p and r['exchange']==e and r['case_id']==c['id'], 'Asymmetric mode')
        suffix=[str(c['n']),str(c['k']),str(c['tol'])]
        if m=='mpi':
            require((d['mpi_processes'],d['exchange'],d['nodes'])==(p,e,1), 'Asymmetric MPI')
            suffix+=['--exchange',e]
            require(r['command'][r['command'].index('-np')+1]==str(p), 'Asymmetric launcher P')
        require(r['command'][-len(suffix):]==suffix, 'Asymmetric command workload')
        difference=validate_result(d,c,oracles[c['id']])
        require(difference==r['independent_grid_max_difference'], 'Asymmetric saved grid difference')
    return len(a['runs'])


def expand_mask(text):
    values=[]
    for part in text.split(','):
        limits=list(map(int,part.strip().split('-')))
        values.extend(range(limits[0],limits[-1]+1))
    return values


def archive_checked(root,archive):
    archive.parent.mkdir(parents=True,exist_ok=True)
    if not archive.exists():
        with archive.open('xb') as stream:
            with tarfile.open(fileobj=stream,mode='w:gz') as tar:
                tar.add(root,arcname=root.name)
    files={root.name+'/'+p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
    with tarfile.open(archive,'r:gz') as tar:
        regular=[m for m in tar.getmembers() if m.isfile()]
        require(len(regular)==len({m.name for m in regular}), 'Duplicate archive member')
        members={m.name:m for m in regular}
        require(members.keys()==files.keys(), 'Archive inventory mismatch')
        for name,p in files.items():
            require(hashlib.sha256(tar.extractfile(members[name]).read()).hexdigest()==sha(p), 'Archive member changed: '+name)
    return dict(path=str(archive),sha256=sha(archive),files=len(files),member_by_member_checked=True)


def audit(root,out,plots=False,archive=None):
    require(not out.exists(), 'Output directory must not exist')
    require(not out.is_relative_to(root), 'Analysis must be outside raw results')
    b=read(root/'benchmark/summary.json')
    require((b['status'],b['schema'],b['cluster'])==('PASS','dual-scale-v1','Vanda'), 'Incomplete dual run')
    require((b['iterations'],b['tolerance'],b['warmups'],b['repeats'],b['allocated_cpus'])==(1000,0,1,9,12), 'Design mismatch')
    qstat=(root/'qstat_full.txt').read_text(encoding='utf-8')
    job=re.search(r'^Job Id:\s*(\S+)',qstat)
    require(job is not None and job.group(1)==b['job_id'], 'Wrong PBS job')
    for expression in (r'\bjob_state\s*=\s*F\b',r'\bExit_status\s*=\s*0\b',
                       r'Resource_List.nodect\s*=\s*1\b',r'Resource_List.ncpus\s*=\s*12\b',
                       r'Resource_List.mem\s*=\s*4gb\b'):
        require(re.search(expression,qstat,re.I), 'PBS resource/completion mismatch: '+expression)
    log=(root/'run.log').read_text(encoding='utf-8')
    require(log.rstrip().endswith('RUN_STATUS=PASSED\nJOB_EXIT_STATUS=0'), 'Incomplete run log')
    for source in ('jacobi_serial_row_update.cpp','jacobi_mpi.cpp','jacobi_serial_asymmetric.cpp','jacobi_mpi_asymmetric.cpp'):
        require(source in log and '-std=c++17 -O2 -Wall -Wextra -Wpedantic' in log, 'Missing build command')
    sources=hash_manifest(root,'source_sha256.txt','sources')
    binaries=hash_manifest(root,'executable_sha256.txt','bin')
    check_hash_map(b['source_sha256'],sources)
    require(set(b['source_sha256'])=={name for name in sources if Path(name).suffix in ('.py','.cpp','.json','.pbs','.sh')}, 'Incomplete benchmark source map')
    require(b['serial_source']=='jacobi_serial_row_update.cpp', 'Wrong baseline source')
    require(b['executable_sha256']=={m:binaries['jacobi_'+m] for m in ('serial','mpi')}, 'Benchmark executable hash')
    require((root/'environment.txt').is_file() and (root/'metadata.txt').is_file(), 'Missing environment')
    require(len((root/'pbs_nodefile.txt').read_text().splitlines())==12, 'Wrong PBS slots')
    cpus=b['pin_cpus']
    require(len(set(cpus))==len(cpus)==12, 'CPU list')
    match=re.search(r'Cpus_allowed_list:\s*([^\r\n]+)',(root/'process_status.txt').read_text())
    require(match is not None and set(expand_mask(match.group(1)))==set(cpus), 'Inherited CPU mask')
    require((root/'pin_cpus.txt').read_text().strip()=='PIN_CPUS='+','.join(map(str,cpus)), 'CPU record differs')
    validation=check_validation(root,b,sources,binaries)
    asymmetric=check_asymmetric(root,b,sources,binaries)
    trials=[('serial',1,1,'none')]+[('mpi',p,1,e) for p in (1,2,4,12) for e in ('sendrecv','overlap')]
    plan=read(root/'benchmark/execution_plan.json')
    require(plan==b['plan'] and len(plan)==len(b['runs'])==180, 'Global plan/run count')
    require({p.name for p in (root/'benchmark').iterdir()}=={'summary.json','execution_plan.json','n1024','n2048'}, 'Benchmark directory inventory')
    references={}
    affinity=0
    rows=[]
    for sequence,r in enumerate(b['runs']):
        repeat=sequence//18-1
        block=(sequence%18)//9
        pos=sequence%9
        sizes=(1024,2048) if repeat<0 or repeat%2==0 else (2048,1024)
        n=sizes[block]
        config=trials[(pos+max(0,repeat))%9]
        item=dict(sequence=sequence,n=n,repeat_index=repeat,warmup=repeat<0,
                  scale_block=block,within_scale_position=pos,config=list(config))
        require(plan[sequence]==item and all(r.get(k)==v for k,v in item.items()), 'Global execution order')
        mode,p,t,e=config
        expected_id=f'{mode}_p{p}_t{t}_{e}_r{repeat}'
        require(r['id']==expected_id and r['exit_code']==0, 'Wrong execution ID/exit')
        stderr=raw_record(root/'benchmark'/f'n{n}',r)
        d=r['result']
        require((d['mode'],d['n'],d['iterations'],d['tolerance'],d['status'],d['threads'])==
                (mode,n,1000,0,'fixed_iterations',1), 'Performance workload')
        if mode=='mpi':
            require((d['mpi_processes'],d['exchange'],d['nodes'])==(p,e,1), 'Performance MPI')
        require(all(math.isfinite(d[f]) and d[f]>=0 for f in FIELDS+('compute_seconds',)), 'Invalid performance metrics')
        require(d['compute_seconds']>0 and d['boundary_error']<=1e-14, 'Invalid timing/boundary')
        references.setdefault(n,d)
        require(all(math.isclose(d[f],references[n][f],rel_tol=1e-10,abs_tol=1e-12) for f in FIELDS), 'Performance numerical mismatch')
        actual=check_affinity(stderr,cpus,p,b['host'])
        require(actual==r['affinity_before_exec'], 'Raw affinity differs')
        affinity+=len(actual)
        cmd=r['command']
        require(cmd[cmd.index('--cpus')+1]==','.join(map(str,cpus)), 'Pin command differs')
        suffix=[str(n),'1000','0']
        if mode=='mpi':
            suffix+=['--exchange',e]
            require(cmd[cmd.index('-np')+1]==str(p) and cmd[cmd.index('--bind-to')+1]=='none' and
                    cmd[cmd.index('--map-by')+1]=='slot', 'MPI launcher command')
        require(cmd[-len(suffix):]==suffix, 'Performance command workload')
        solver_index=cmd.index('--')+1
        require(Path(cmd[solver_index]).name=='jacobi_'+mode, 'Wrong executable command')
    require(affinity==780, 'Wrong affinity count')
    for n in (1024,2048):
        scale=read(root/'benchmark'/f'n{n}'/'summary.json')
        runs=[r for r in b['runs'] if r['n']==n]
        require(scale['status']=='PASS' and scale['n']==n and scale['runs']==runs, 'Scale projection differs')
        for k in ('job_id','host','pin_cpus','serial_source','executable_sha256','source_sha256','iterations','tolerance','warmups','repeats'):
            require(scale[k]==b[k], 'Scale metadata differs: '+k)
        require(scale['groups']==b['scales'][str(n)]['groups'], 'Scale statistics projection')
        inventory(root/'benchmark'/f'n{n}',runs)
        require([(g['mode'],g['processes'],g['threads'],g['exchange']) for g in scale['groups']]==trials, 'Scale configurations')
        for row in checked_rows(scale):
            times=[r['result']['compute_seconds'] for r in runs if not r['warmup'] and
                   (r['result']['mode'],r['result'].get('mpi_processes',1),r['result']['threads'],r['result'].get('exchange','none'))==
                   (row['mode'],row['processes'],row['threads'],row['exchange'])]
            row.update(n=n,sample_cv_percent=100*statistics.stdev(times)/statistics.mean(times))
            rows.append(row)
        for config in trials:
            positions=[r['within_scale_position'] for r in runs if not r['warmup'] and tuple(r['config'])==config]
            require(Counter(positions)==Counter(range(9)), 'Within-scale order not balanced')
    archived=archive_checked(root,archive or root.parent/'raw_archives'/(root.name+'.tar.gz'))
    out.mkdir(parents=True)
    with (out/'performance_audited.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    warnings=['libpbs.so.0 warning retained'] if any('libpbs.so.0' in p.read_text(encoding='utf-8') for p in root.rglob('*.stderr.txt')) else []
    result=dict(status='PASS',job_id=b['job_id'],host=b['host'],validation=validation,
                asymmetric_full_grid_executions=asymmetric,performance_executions=180,
                performance_warmups=18,performance_formal=162,rank_affinity_records=affinity,
                global_order_checked=True,within_scale_nine_positions_checked=True,
                eighteen_positions_balanced=False,raw_archive=archived,warnings=warnings)
    (out/'audit.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    table='\n'.join(f"| {r['n']} | {r['mode']} | {r['processes']} | {r['exchange']} | {r['median_seconds']:.6f} | {r['min_seconds']:.6f}–{r['max_seconds']:.6f} | {r['sample_cv_percent']:.2f}% | {r['speedup']:.3f} |" for r in rows)
    communication=[]
    for n in (1024,2048):
        rs=[r for r in rows if r['n']==n]
        for p in (1,2,4,12):
            sr=next(r for r in rs if r['mode']=='mpi' and r['processes']==p and r['exchange']=='sendrecv')
            ov=next(r for r in rs if r['mode']=='mpi' and r['processes']==p and r['exchange']=='overlap')
            def times(e):
                return {r['repeat_index']:r['result']['compute_seconds'] for r in b['runs']
                        if r['n']==n and not r['warmup'] and tuple(r['config'])==('mpi',p,1,e)}
            s,o=times('sendrecv'),times('overlap')
            communication.append(dict(n=n,processes=p,overlap_median_reduction_percent=100*(sr['median_seconds']-ov['median_seconds'])/sr['median_seconds'],
                                      overlap_faster_rounds=sum(o[k]<s[k] for k in s),rounds=9))
    with (out/'communication_audited.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(communication[0]));writer.writeheader();writer.writerows(communication)
    comm='\n'.join(f"| {r['n']} | {r['processes']} | {r['overlap_median_reduction_percent']:.2f}% | {r['overlap_faster_rounds']}/9 |" for r in communication)
    text=f"""# 同次分配双规模与非对称验证复核

作业 {b['job_id']}，主机 {b['host']}。以下为当前原始数据派生结果，不预设改善方向。
源码、程序哈希、原始 JSON、工作量、780 条执行前绑定、完整执行顺序及统计重新核对。
原验证 {validation['total']} 次；非对称完整小网格验证 {asymmetric} 次；性能 180 次（18 预热、162 正式）。

| n | 模式 | P | 通信 | 中位秒 | min–max 秒 | 样本 CV | 相对本规模串行 |
|---:|---|---:|---|---:|---|---:|---:|
{table}

相对 MPI P=1 的加速比及效率另见 CSV，各规模、各策略各用本次基准。
min/max 不是置信区间，全部样本保留，未按性能好坏排除。

| n | P | overlap 中位耗时降低（正数更快） | 同轮更快次数 |
|---:|---:|---:|---:|
{comm}

正式轮交替规模块，每规模的每配置覆盖内部九个位置；九轮不覆盖十八个跨规模位置。
同一次分配控制 CPU 列表、程序及 rank 映射，但不能排除共享节点干扰或时间变化。
这些大网格只核对全局指标，没有逐点验证，也不宣称 K=1000 收敛。
非对称验证采用 x=列坐标、y=行坐标及 u=x+2y+xy；小网格全点和全局指标均与独立 Python 参考比较。
小规模收敛阈值不推广到大网格。非阻塞 API 或总耗时差异均不足以证明底层有效通信重叠。
本作业与历史作业不能混算基准。系统根因仍需独立证据；不因当前数据再自动追加实验。

原始包：{archived['path']}；SHA-256：{archived['sha256']}；{archived['files']} 个文件逐成员核验。
环境警告：{'; '.join(warnings) or '原始 stderr 未检出 libpbs.so.0 警告'}。
AI 协助准备和审计；Vanda 登录、提交、下载及人工理解确认由用户完成。未发送邮件或提交 Git。
"""
    if plots:
        for n in (1024,2048):
            target=out/f'n{n}';target.mkdir()
            make_plots(read(root/'benchmark'/f'n{n}'/'summary.json'),[r for r in rows if r['n']==n],target)
            text+=f"\n![n={n}](n{n}/mpi_scaling.png)\n"
    (out/'analysis.md').write_text(text,encoding='utf-8')
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--plots',action='store_true')
    args=ap.parse_args()
    result=audit(args.results.resolve(),args.out_dir.resolve(),args.plots)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
