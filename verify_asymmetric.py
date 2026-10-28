"""Independent asymmetric Laplace oracle; small correctness cases, never a benchmark."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import subprocess

BASE = Path(__file__).resolve().parent
# x = column/(n+1), y = row/(n+1). All cases emit the complete grid.
CASES = [
    dict(id='single_cell', n=1, k=1, tol=0, processes=[1], covers='one cell, physical corners, odd swap'),
    dict(id='two_rows', n=2, k=2, tol=0, processes=[1,2], covers='one/two local rows, even swap'),
    dict(id='uneven', n=7, k=31, tol=0, processes=[1,2,4], covers='4+3 and 2+2+2+1 partition, halo, internal rows'),
    dict(id='two_per_rank', n=8, k=2, tol=0, processes=[4], covers='exactly two rows, no internal row'),
    dict(id='twelve_single', n=12, k=3, tol=0, processes=[12], covers='all 12 ranks own one row'),
    dict(id='twelve_double', n=24, k=4, tol=0, processes=[12], covers='all 12 ranks own two rows'),
    dict(id='converged', n=7, k=10000, tol=1e-12, processes=[1,2,4], covers='global stopping, analytic error, refreshed residual halo'),
]
FIELDS = ('max_update', 'max_error', 'residual_inf', 'boundary_error')


def exact(row, col, n):
    x, y = col/(n+1), row/(n+1)
    return x + 2*y + x*y


def oracle(case):
    n = case['n']
    grid = [[exact(i,j,n) if i in (0,n+1) or j in (0,n+1) else 0.0
             for j in range(n+2)] for i in range(n+2)]
    for k in range(1, case['k']+1):
        new = [row[:] for row in grid]
        delta = 0.0
        for i in range(1,n+1):
            for j in range(1,n+1):
                new[i][j] = (grid[i-1][j]+grid[i+1][j]+grid[i][j-1]+grid[i][j+1])/4
                delta = max(delta, abs(new[i][j]-grid[i][j]))
        grid = new
        if case['tol'] > 0 and delta <= case['tol']:
            break
    error = max(abs(grid[i][j]-exact(i,j,n)) for i in range(1,n+1) for j in range(1,n+1))
    residual = max(abs(4*grid[i][j]-grid[i-1][j]-grid[i+1][j]-grid[i][j-1]-grid[i][j+1])*(n+1)**2
                   for i in range(1,n+1) for j in range(1,n+1))
    return dict(grid=grid, iterations=k, max_update=delta, max_error=error,
                residual_inf=residual, boundary_error=0.0,
                status='fixed_iterations' if case['tol']==0 else
                ('update_tolerance_reached' if delta<=case['tol'] else 'iteration_limit'))


def validate_result(data, case, expected=None):
    expected = expected or oracle(case)
    if data.get('problem') != 'x+2y+xy' or data['n'] != case['n'] or data['tolerance'] != case['tol']:
        raise ValueError('Wrong asymmetric problem or workload')
    if data['iterations'] != expected['iterations'] or data['status'] != expected['status']:
        raise ValueError('Independent iteration/stopping mismatch')
    if any(not math.isfinite(data[f]) or data[f] < 0 for f in FIELDS+('compute_seconds',)):
        raise ValueError('Non-finite or negative metric')
    grid = data['grid']
    width = case['n']+2
    if len(grid)!=width or any(len(row)!=width for row in grid):
        raise ValueError('Wrong full-grid shape')
    differences = [abs(grid[i][j]-expected['grid'][i][j]) for i in range(width) for j in range(width)]
    if any(not math.isfinite(d) for d in differences) or max(differences)>1e-12:
        raise ValueError('Independent full-grid mismatch')
    for f in FIELDS:
        if not math.isclose(data[f],expected[f],rel_tol=1e-10,abs_tol=1e-12):
            raise ValueError('Independent metric mismatch: '+f)
    boundary = max(abs(grid[i][j]-exact(i,j,case['n'])) for i in range(width)
                   for j in range(width) if i in (0,width-1) or j in (0,width-1))
    if boundary>1e-14 or data['boundary_error']>1e-14:
        raise ValueError('Asymmetric boundary mismatch')
    if case['tol']>0 and (data['status']!='update_tolerance_reached' or
                          data['max_update']>case['tol'] or data['max_error']>1e-8 or data['residual_inf']>1e-7):
        raise ValueError('Small-grid convergence criteria failed')
    return max(differences)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial',type=Path,required=True)
    ap.add_argument('--mpi',type=Path)
    ap.add_argument('--launcher',default='mpirun')
    ap.add_argument('--out-dir',type=Path,required=True)
    args=ap.parse_args()
    binaries={'serial':args.serial.resolve(strict=True)}
    if args.mpi:
        binaries['mpi']=args.mpi.resolve(strict=True)
    out=args.out_dir.resolve()
    out.mkdir(parents=True,exist_ok=False)
    summary=dict(status='RUNNING',problem='x+2y+xy',coordinates='x=column/(n+1), y=row/(n+1)',
                 scope='small full-grid correctness only; not performance or large-grid proof',
                 job_id=os.environ.get('PBS_JOBID'),host=platform.node(),
                 generated_at_utc=datetime.now(timezone.utc).isoformat(),cases=CASES,runs=[],
                 executable_sha256={m:hashlib.sha256(p.read_bytes()).hexdigest() for m,p in binaries.items()},
                 source_sha256={n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in
                                ('jacobi_serial_asymmetric.cpp','jacobi_mpi_asymmetric.cpp','verify_asymmetric.py')})
    try:
        for case in CASES:
            expected=oracle(case)
            for mode in binaries:
                configs=[(1,'none')] if mode=='serial' else [(p,e) for p in case['processes'] for e in ('sendrecv','overlap')]
                for p,exchange in configs:
                    label=f"{case['id']}_{mode}_p{p}_{exchange}"
                    cmd=([str(binaries[mode])] if mode=='serial' else
                         shlex.split(args.launcher)+['-np',str(p),str(binaries[mode])])
                    cmd += [str(case['n']),str(case['k']),str(case['tol'])]
                    if mode=='mpi':
                        cmd += ['--exchange',exchange]
                    record=dict(id=label,case_id=case['id'],processes=p,exchange=exchange,command=cmd)
                    summary['runs'].append(record)
                    run=subprocess.run(cmd,capture_output=True,text=True,timeout=120,
                                       env=dict(os.environ,OMP_NUM_THREADS='1',OMP_DYNAMIC='FALSE'))
                    (out/(label+'.stdout.json')).write_text(run.stdout,encoding='utf-8')
                    (out/(label+'.stderr.txt')).write_text(run.stderr,encoding='utf-8')
                    record['exit_code']=run.returncode
                    if run.returncode!=0:
                        raise ValueError(label+': unexpected exit '+str(run.returncode))
                    data=json.loads(run.stdout)
                    record['result']=data
                    if data['mode']!=mode or data['threads']!=1:
                        raise ValueError('Wrong mode/team')
                    if mode=='mpi' and (data['mpi_processes']!=p or data['exchange']!=exchange or data['nodes']!=1):
                        raise ValueError('Wrong MPI layout')
                    record['independent_grid_max_difference']=validate_result(data,case,expected)
                    record['validation']='PASS'
                    print('PASS',label,flush=True)
        summary['status']='PASS'
    except Exception as error:
        summary.update(status='FAIL',error=str(error))
        raise
    finally:
        (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(f"PASS: {len(summary['runs'])} asymmetric full-grid executions")


if __name__=='__main__':
    main()
