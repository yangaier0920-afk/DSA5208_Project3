"""Local tooling checks; synthetic fixture timings are NOT measurements."""
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import benchmark_dual_scale as dual
import audit_ab_supplement as audit
import verify_asymmetric as asym

BASE=Path(__file__).resolve().parent


def save(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def main():
    temp=Path(tempfile.mkdtemp(prefix='supplement_tooling_',dir=BASE/'results'))
    raw=temp/'SYNTHETIC_NOT_HPC'
    raw.mkdir()
    (raw/'sources').mkdir()
    (raw/'bin').mkdir()
    source_files=[p for p in BASE.iterdir() if p.is_file() and p.suffix in ('.py','.cpp','.pbs','.sh','.json')]
    for p in source_files:
        shutil.copy2(p,raw/'sources'/p.name)
    # Fixture executable bytes exist only to exercise hash and inventory checking.
    for name in ('jacobi_serial','jacobi_mpi','jacobi_serial_asymmetric','jacobi_mpi_asymmetric'):
        (raw/'bin'/name).write_bytes(('SYNTHETIC NONEXECUTABLE '+name).encode())
    cpus=list(range(12))
    historical={n:json.loads((BASE/f'results/Vanda_mpi_recheck_{j}.stdct-mgmt-02/benchmark/summary.json').read_text(encoding='utf-8'))
                for n,j in ((1024,'1500271'),(2048,'1500222'))}
    metrics={n:next(r['result'] for r in b['runs'] if r['result']['mode']=='serial') for n,b in historical.items()}
    launched=[]

    def fake_run(command,**kwargs):
        index=command.index('--')
        mode=Path(command[index+1]).name.removeprefix('jacobi_')
        n=int(command[index+2])
        p=int(command[command.index('-np')+1]) if mode=='mpi' else 1
        data=copy.deepcopy(metrics[n])
        data.update(mode=mode,compute_seconds=1.0+n/1024/p+len(launched)*1e-5)
        if mode=='mpi':
            data.update(mpi_processes=p,nodes=1,exchange=command[-1])
        stderr=''.join('AB_AFFINITY '+json.dumps(dict(rank=r,host='fixture.invalid',cpus=[cpus[r]]))+'\n' for r in range(p))
        launched.append(command)
        return SimpleNamespace(returncode=0,stdout=json.dumps(data)+'\n',stderr=stderr)

    argv=['benchmark_dual_scale.py','--build-dir',str(raw/'bin'),'--out-dir',str(raw/'benchmark'),'--pin-cpus',','.join(map(str,cpus))]
    with patch.object(sys,'argv',argv), patch.dict(os.environ,{'PBS_JOBID':'synthetic.test'}), \
         patch.object(os,'sched_getaffinity',lambda pid:set(cpus),create=True), \
         patch.object(platform,'node',lambda:'fixture.invalid'), patch.object(dual,'BASE',raw/'sources'), \
         patch.object(subprocess,'run',fake_run):
        dual.main()
    assert len(launched)==180
    plan=dual.execution_plan()
    assert sum(x['warmup'] for x in plan)==18
    assert sum(not x['warmup'] for x in plan)==162
    assert sum(x['config'][1] for x in plan)==780
    for n in (1024,2048):
        for config in dual.TRIALS:
            selected=[x for x in plan if x['n']==n and tuple(x['config'])==config]
            assert len(selected)==10 and sum(x['warmup'] for x in selected)==1
            assert sorted(x['within_scale_position'] for x in selected if not x['warmup'])==list(range(9))
    # Use prior verified numerical records as fixture payloads; no solver is launched.
    old=BASE/'results/Vanda_mpi_recheck_1500271.stdct-mgmt-02/validation'
    shutil.copytree(old,raw/'validation')
    v=audit.read(raw/'validation/summary.json')
    v.update(job_id='synthetic.test',host='fixture.invalid')
    v['sha256']={name:audit.sha(raw/'sources'/name) for name in v['sha256']}
    v['executable_sha256']={m:audit.sha(raw/'bin'/('jacobi_'+m)) for m in ('serial','mpi')}
    save(raw/'validation/summary.json',v)
    folder=raw/'asymmetric_validation';folder.mkdir()
    a=dict(status='PASS',problem='x+2y+xy',job_id='synthetic.test',host='fixture.invalid',
           cases=asym.CASES,runs=[],source_sha256={n:audit.sha(raw/'sources'/n) for n in
               ('jacobi_serial_asymmetric.cpp','jacobi_mpi_asymmetric.cpp','verify_asymmetric.py')},
           executable_sha256={m:audit.sha(raw/'bin'/('jacobi_'+m+'_asymmetric')) for m in ('serial','mpi')})
    for case in asym.CASES:
        expected=asym.oracle(case)
        for mode in ('serial','mpi'):
            configs=[(1,'none')] if mode=='serial' else [(p,e) for p in case['processes'] for e in ('sendrecv','overlap')]
            for p,e in configs:
                label=f"{case['id']}_{mode}_p{p}_{e}"
                d=dict(expected,problem='x+2y+xy',n=case['n'],tolerance=case['tol'],mode=mode,threads=1,compute_seconds=1)
                cmd=[str(raw/'bin'/('jacobi_'+mode+'_asymmetric')),str(case['n']),str(case['k']),str(case['tol'])]
                if mode=='mpi':
                    d.update(mpi_processes=p,exchange=e,nodes=1)
                    cmd=['mpirun','-np',str(p)]+cmd+['--exchange',e]
                r=dict(id=label,case_id=case['id'],processes=p,exchange=e,command=cmd,
                       exit_code=0,result=d,validation='PASS',independent_grid_max_difference=0)
                a['runs'].append(r)
                save(folder/(label+'.stdout.json'),d)
                (folder/(label+'.stderr.txt')).write_text('',encoding='utf-8')
    save(folder/'summary.json',a)
    (raw/'qstat_full.txt').write_text('Job Id: synthetic.test\n job_state = F\n Exit_status = 0\n Resource_List.nodect = 1\n Resource_List.ncpus = 12\n Resource_List.mem = 4gb\n',encoding='utf-8')
    log='\n'.join('g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic '+s for s in
        ('jacobi_serial_row_update.cpp','jacobi_mpi.cpp','jacobi_serial_asymmetric.cpp','jacobi_mpi_asymmetric.cpp'))
    (raw/'run.log').write_text(log+'\nRUN_STATUS=PASSED\nJOB_EXIT_STATUS=0\n',encoding='utf-8')
    for name,text in [('environment.txt','SYNTHETIC'),('metadata.txt','SYNTHETIC'),('pbs_nodefile.txt','fixture.invalid\n'*12),
                      ('process_status.txt','Cpus_allowed_list:\t0-11\n'),('pin_cpus.txt','PIN_CPUS='+','.join(map(str,cpus))+'\n')]:
        (raw/name).write_text(text,encoding='utf-8')
    for manifest,dir_name in [('source_sha256.txt','sources'),('executable_sha256.txt','bin')]:
        (raw/manifest).write_text(''.join(audit.sha(p)+'  '+p.as_posix()+'\n' for p in sorted((raw/dir_name).iterdir())),encoding='utf-8')
    result=audit.audit(raw,temp/'valid_analysis',plots=True)
    assert result['status']=='PASS' and result['asymmetric_full_grid_executions']==31
    rejected=[]

    def rejects(name,mutate,restore):
        mutate()
        try:
            audit.audit(raw,temp/('bad_'+name))
        except (ValueError,KeyError,FileNotFoundError,StopIteration) as error:
            rejected.append(dict(name=name,error=str(error)))
        else:
            raise AssertionError('Accepted broken fixture: '+name)
        finally:
            restore()

    summary_path=raw/'benchmark/summary.json'
    original=summary_path.read_bytes()
    b=audit.read(summary_path)
    bad=copy.deepcopy(b);bad['runs'][18]['sequence']=999
    rejects('global_order',lambda:save(summary_path,bad),lambda:summary_path.write_bytes(original))
    record=b['runs'][19]
    stderr=raw/'benchmark'/f"n{record['n']}"/(record['id']+'.stderr.txt')
    saved=stderr.read_bytes()
    rejects('missing_affinity',lambda:stderr.write_text('',encoding='utf-8'),lambda:stderr.write_bytes(saved))
    p=raw/'benchmark/n1024/summary.json';saved_scale=p.read_bytes()
    wrong=audit.read(p);wrong['groups'][0]['median_seconds']*=2
    rejects('changed_statistics',lambda:save(p,wrong),lambda:p.write_bytes(saved_scale))
    p=raw/'asymmetric_validation/summary.json';saved_asym=p.read_bytes()
    wrong=audit.read(p);wrong['runs']=wrong['runs'][:-1]
    rejects('missing_asymmetric_case',lambda:save(p,wrong),lambda:p.write_bytes(saved_asym))
    p=raw/'qstat_full.txt';saved_q=p.read_bytes()
    rejects('unfinished_pbs',lambda:p.write_text('Job Id: synthetic.test\n job_state = R\n',encoding='utf-8'),lambda:p.write_bytes(saved_q))
    p=raw/'sources/jacobi_mpi.cpp';saved_source=p.read_bytes()
    rejects('changed_source',lambda:p.write_bytes(saved_source+b'\n//tamper\n'),lambda:p.write_bytes(saved_source))
    # Same raw fixture can be re-audited; existing archive must match rather than be overwritten.
    audit.audit(raw,temp/'valid_reaudit')
    c=asym.CASES[2];d=dict(asym.oracle(c),problem='x+2y+xy',n=c['n'],tolerance=c['tol'],compute_seconds=1)
    d['grid']=[list(row) for row in zip(*d['grid'])]
    try:
        asym.validate_result(d,c)
    except ValueError:
        rejected.append(dict(name='swapped_xy_grid',error='independent grid rejected transposed coordinates'))
    else:
        raise AssertionError('Transposed grid was accepted')
    checks=dict(status='PASS',scope='local tooling and synthetic fixtures; NOT MPI/HPC measurements',
                fixture=str(raw),mock_solver_launches=180,plan_rank_records=780,
                asymmetric_fixture_records=31,rejected_invalid_fixtures=rejected,
                real_cluster_executions=0,real_mpi_executions=0,
                archive_round_trip_checked=True,plots_generated=True)
    save(temp/'checks.json',checks)
    print(json.dumps(checks,indent=2))
    print('CHECK_OUTPUT='+str(temp))


if __name__=='__main__':
    main()
