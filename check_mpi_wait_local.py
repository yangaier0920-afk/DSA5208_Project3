"""Local source/oracle checks and explicit SYNTHETIC MPI tooling tests.
No MPI compiler or launcher is used. Timings in the fixture are not measurements.
"""
import contextlib
import copy
import difflib
import io
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import mpi_wait_diagnostic as m

BASE=Path(__file__).resolve().parent
FILES=('jacobi_mpi.cpp','jacobi_mpi_wait_diagnostic.cpp','mpi_wait_diagnostic.py',
       'mpi_wait_reference.json','pin_cpu.py','benchmark_parallel.py',
       'vanda_mpi_wait_diagnostic.pbs','vanda_modules.example.sh')


def main():
    out=BASE/'results/mpi_wait_local_20261028'
    out.mkdir(exist_ok=False)
    source=(BASE/'jacobi_mpi.cpp').read_text(encoding='utf-8')
    candidate=(BASE/'jacobi_mpi_wait_diagnostic.cpp').read_text(encoding='utf-8')
    old='''                // Interior rows do not read receive buffers. Send buffers remain read-only.
                if (rows > 2) local_update = update(2, rows - 1);
                MPI_Waitall(4, requests, MPI_STATUSES_IGNORE);'''
    new='''                // Both nonblocking modes have identical interior/edge work and order.
                // Only the position of the single wait changes. No phase instrumentation.
                if (wait_immediately) MPI_Waitall(4, requests, MPI_STATUSES_IGNORE);
                if (rows > 2) local_update = update(2, rows - 1);
                if (!wait_immediately) MPI_Waitall(4, requests, MPI_STATUSES_IGNORE);'''
    restored=candidate.removeprefix('// Independent pure-MPI wait-placement diagnostic; production source preserved.\n')
    restored=restored.replace('sendrecv|immediate|overlap','sendrecv|overlap')
    restored=restored.replace('(p.exchange != "sendrecv" && p.exchange != "immediate" && p.exchange != "overlap")',
                              '(p.exchange != "sendrecv" && p.exchange != "overlap")')
    restored=restored.replace('        const bool wait_immediately = p.exchange == "immediate";\n','')
    assert restored.count(new)==1
    restored=restored.replace(new,old)
    restored=restored.replace('<< "{\\"diagnostic\\":\\"wait-placement-v1\\",\\"mode\\":\\"" << mode',
                              '<< "{\\"mode\\":\\"" << mode')
    assert restored==source,'Unexpected source changes'
    (out/'diagnostic_source.diff').write_text(''.join(difflib.unified_diff(source.splitlines(True),candidate.splitlines(True),
                                                       fromfile='jacobi_mpi.cpp',tofile='jacobi_mpi_wait_diagnostic.cpp')),encoding='utf-8')
    # Independent oracle is checked against a real serial build on this machine.
    serial=out/'serial_reference.exe'
    cmd=['g++','-std=c++17','-O2','-Wall','-Wextra','-Wpedantic',str(BASE/'jacobi_serial_row_update.cpp'),'-o',str(serial)]
    build=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
    (out/'serial_build.stdout.txt').write_text(build.stdout,encoding='utf-8')
    (out/'serial_build.stderr.txt').write_text(build.stderr,encoding='utf-8')
    assert build.returncode==0
    serial_dir=out/'serial_oracle';serial_dir.mkdir()
    distinct={(c['n'],c['k'],c['tol']):c for c in m.CASES}
    real_serial=[]
    for (n,k,tol),case in distinct.items():
        completed=subprocess.run([str(serial),str(n),str(k),str(tol)],capture_output=True,text=True,timeout=120)
        label=f'n{n}_k{k}_tol{tol}'
        (serial_dir/(label+'.stdout.json')).write_text(completed.stdout,encoding='utf-8')
        (serial_dir/(label+'.stderr.txt')).write_text(completed.stderr,encoding='utf-8')
        assert completed.returncode==0
        d=json.loads(completed.stdout);expected=m.oracle(case)
        assert d['mode']=='serial' and d['threads']==1
        assert d['iterations']==expected['iterations'] and d['status']==expected['status']
        for f in m.FIELDS:
            assert math.isclose(d[f],expected[f],rel_tol=1e-10,abs_tol=1e-12),(label,f)
        if n<=8:
            assert max(abs(a-b) for ra,rb in zip(d['grid'],expected['grid']) for a,b in zip(ra,rb))<=1e-12
        real_serial.append(dict(n=n,k=k,tol=tol,iterations=d['iterations'],status=d['status'],max_error=d['max_error']))
    raw=out/'SYNTHETIC_MPI_WAIT';raw.mkdir()
    (raw/'sources').mkdir();(raw/'bin').mkdir()
    for name in FILES:shutil.copy2(BASE/name,raw/'sources'/name)
    for name in ('jacobi_mpi','jacobi_mpi_wait_diagnostic'):
        (raw/'bin'/name).write_bytes(('SYNTHETIC NONEXECUTABLE '+name).encode())
    cpus=list(range(12));count=[]
    expected_fixed=m.read(BASE/'mpi_wait_reference.json')
    oracles={(c['n'],c['k'],c['tol']):m.oracle(c) for c in m.CASES}

    def fake_run(command,**kwargs):
        index=command.index('--');exe=Path(command[index+1]).name
        n,k,tol=int(command[index+2]),int(command[index+3]),float(command[index+4])
        p=int(command[command.index('-np')+1]);e=command[-1]
        expected=oracles[n,k,tol] if n<=24 else dict(expected_fixed['n_values'][str(n)],iterations=1000,status='fixed_iterations')
        d=copy.deepcopy(expected)
        if n>8:d.pop('grid',None)
        d.update(mode='mpi',n=n,mpi_processes=p,threads=1,nodes=1,exchange=e,tolerance=tol,
                 compute_seconds=1+p/10+len(count)*0.001+m.SCHEMES.index(e)*0.01)
        if exe=='jacobi_mpi_wait_diagnostic':d['diagnostic']=m.TAG
        count.append(command)
        stderr=''.join('AB_AFFINITY '+json.dumps(dict(rank=r,host='fixture.invalid',cpus=[cpus[r]]))+'\n' for r in range(p))
        return SimpleNamespace(returncode=0,stdout=json.dumps(d)+'\n',stderr=stderr)

    transcript=io.StringIO()
    with patch.object(m,'BASE',raw/'sources'), patch.dict(os.environ,{'PBS_JOBID':'synthetic.wait'}), \
         patch.object(os,'sched_getaffinity',lambda pid:set(cpus),create=True), \
         patch.object(platform,'node',lambda:'fixture.invalid'),patch.object(subprocess,'run',fake_run), \
         contextlib.redirect_stdout(transcript):
        m.run_experiment(SimpleNamespace(build_dir=raw/'bin',out_dir=raw/'diagnostic',
                                        pin_cpus=','.join(map(str,cpus)),launcher='mpirun'))
    assert len(count)==99
    qstat='Job Id: synthetic.wait\n job_state = F\n Exit_status = 0\n Resource_List.nodect = 1\n Resource_List.ncpus = 12\n Resource_List.mem = 4gb\n exec_host = fixture.invalid/0*12\n'
    (raw/'qstat_full.txt').write_text(qstat,encoding='utf-8')
    for name,text in [('metadata.txt','SYNTHETIC'),('environment.txt','SYNTHETIC'),('lscpu.txt','SYNTHETIC'),
                      ('qstat_at_start.txt','SYNTHETIC'),('pbs_nodefile.txt','fixture.invalid\n'*12),
                      ('pin_cpus.txt','PIN_CPUS='+','.join(map(str,cpus))+'\n'),
                      ('process_status.txt','Cpus_allowed_list:\t0-11\n')]:
        (raw/name).write_text(text,encoding='utf-8')
    for name,folder in [('source_sha256.txt','sources'),('executable_sha256.txt','bin')]:
        (raw/name).write_text(''.join(m.sha(p)+'  '+p.as_posix()+'\n' for p in sorted((raw/folder).iterdir())),encoding='utf-8')
    builds='\n'.join('+ mpicxx -std=c++17 -O2 -Wall -Wextra -Wpedantic /sources/'+name+' -o /bin/'+exe
                     for name,exe in [('jacobi_mpi.cpp','jacobi_mpi'),('jacobi_mpi_wait_diagnostic.cpp','jacobi_mpi_wait_diagnostic')])
    (raw/'run.log').write_text(builds+'\n'+transcript.getvalue()+'RUN_STATUS=PASSED\nJOB_EXIT_STATUS=0\n',encoding='utf-8')
    with contextlib.redirect_stdout(io.StringIO()):
        m.audit(SimpleNamespace(results=raw,out_dir=out/'valid_analysis',plots=True))
    success=m.read(out/'valid_analysis/audit.json')
    assert success['affinity_records']==673 and success['validation_executions']==45 and success['performance_executions']==54
    rejected=[]

    def rejects(name,path,alter):
        old_bytes=path.read_bytes();alter()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                m.audit(SimpleNamespace(results=raw,out_dir=out/('bad_'+name),plots=False))
        except (ValueError,KeyError,FileNotFoundError) as error:
            rejected.append(dict(name=name,error=str(error)))
        else:
            raise AssertionError('Broken fixture accepted: '+name)
        finally:
            path.write_bytes(old_bytes)

    summary=raw/'diagnostic/summary.json';state=m.read(summary)
    wrong=copy.deepcopy(state);wrong['correctness_completed_before_performance']=False
    rejects('correctness_gate',summary,lambda:m.save(summary,wrong))
    wrong=copy.deepcopy(state);wrong['performance_runs'][9]['sequence']=999
    rejects('execution_order',summary,lambda:m.save(summary,wrong))
    first=state['performance_runs'][0]
    stderr=raw/'diagnostic/performance'/(first['id']+'.stderr.txt')
    rejects('missing_affinity',stderr,lambda:stderr.write_text('',encoding='utf-8'))
    stdout=raw/'diagnostic/performance'/(first['id']+'.stdout.json')
    bad=m.read(stdout);bad['iterations']=999
    rejects('changed_raw_workload',stdout,lambda:m.save(stdout,bad))
    wrong=copy.deepcopy(state);wrong['groups'][0]['median_seconds']*=2
    rejects('changed_statistics',summary,lambda:m.save(summary,wrong))
    rejects('unfinished_pbs',raw/'qstat_full.txt',lambda:(raw/'qstat_full.txt').write_text('Job Id: synthetic.wait\n job_state = R\n',encoding='utf-8'))
    sourcefile=raw/'sources/jacobi_mpi_wait_diagnostic.cpp'
    rejects('changed_source',sourcefile,lambda:sourcefile.write_bytes(sourcefile.read_bytes()+b'\n//tamper\n'))
    # A failed numerical check prevents all performance launches; raw timeout output retained.
    failed=out/'timeout_fixture';calls=[]
    def timeout(command,**kwargs):
        calls.append(command)
        raise subprocess.TimeoutExpired(command,180,output='partial stdout',stderr='partial stderr')
    with patch.object(m,'BASE',raw/'sources'), patch.dict(os.environ,{'PBS_JOBID':'synthetic.wait'}), \
         patch.object(os,'sched_getaffinity',lambda pid:set(cpus),create=True), \
         patch.object(platform,'node',lambda:'fixture.invalid'),patch.object(subprocess,'run',timeout):
        try:
            m.run_experiment(SimpleNamespace(build_dir=raw/'bin',out_dir=failed,pin_cpus=','.join(map(str,cpus)),launcher='mpirun'))
        except ValueError:
            pass
        else:
            raise AssertionError('Timeout accepted')
    failed_state=m.read(failed/'summary.json')
    assert failed_state['status']=='FAIL' and len(calls)==1 and not failed_state['performance_runs']
    assert failed_state['validation_runs'][0]['timeout']
    assert (failed/'validation/one_cell_original_sendrecv.stdout.json').read_text()=='partial stdout'
    # Reaudit checks an existing archive instead of overwriting it.
    with contextlib.redirect_stdout(io.StringIO()):
        m.audit(SimpleNamespace(results=raw,out_dir=out/'valid_reaudit',plots=False))
    checks=dict(status='PASS',scope='real local serial oracle + synthetic tooling; NOT MPI/HPC measurements',
                source_change_roundtrip=True,real_local_serial_workloads=real_serial,
                real_local_serial_workload_count=len(real_serial),mock_solver_launches=99,
                validation_mock_launches=45,performance_mock_launches=54,
                expected_rank_affinity_records=673,rejected_broken_fixtures=rejected,
                timeout_evidence_and_gate_checked=True,archive_roundtrip_checked=True,
                real_mpi_compiled_or_run=False,real_cluster_executions=0,
                serial_build_command=cmd,serial_source_sha256=m.sha(BASE/'jacobi_serial_row_update.cpp'),
                diagnostic_source_sha256=m.sha(BASE/'jacobi_mpi_wait_diagnostic.cpp'))
    m.save(out/'checks.json',checks)
    print(json.dumps(checks,ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
