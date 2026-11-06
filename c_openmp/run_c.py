#!/usr/bin/env python3
"""C's checks and GPU-node matrix. Python standard library only."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def command_info(cmd):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return {"command":cmd, "returncode":p.returncode, "stdout":p.stdout, "stderr":p.stderr}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"command":cmd, "unavailable":str(e)}


def one_step_reference(nx, ny, nz, dim, iterations):
    # Independent coordinate/dictionary implementation; includes boundaries.
    h = [1/(nx+1),1/(ny+1),1/(nz+1)]
    sizes = [nx,ny,nz]
    keys = [(i,j,k) for i in range(nx+2) for j in range(ny+2)
            for k in (range(nz+2) if dim==3 else [0])]
    def edge(q):
        return any(q[d] in (0,sizes[d]+1) for d in range(dim))
    def linear(q):
        return sum((d+1)*q[d]*h[d] for d in range(dim))
    u = {q:linear(q) if edge(q) else 0.0 for q in keys}
    weights = [1/h[d]**2 for d in range(dim)]
    diag = 2*sum(weights)
    for _ in range(iterations):
        v = u.copy()
        for q in keys:
            if edge(q):
                continue
            rhs = (14 if dim==3 else 5)*math.pi**2
            for d in range(dim):
                rhs *= math.sin((d+1)*math.pi*q[d]*h[d])
            neighbors = 0.0
            for d in range(dim):
                minus,plus = list(q),list(q)
                minus[d]-=1
                plus[d]+=1
                neighbors += weights[d]*(u[tuple(minus)]+u[tuple(plus)])
            v[q] = (neighbors+rhs)/diag
        u = v
    return u


def solution_difference(cpu_grid, gpu_grid):
    if not cpu_grid or cpu_grid.keys()!=gpu_grid.keys():
        raise RuntimeError('CPU/GPU grid point sets differ or are empty')
    if any(not math.isfinite(v) for grid in (cpu_grid,gpu_grid) for v in grid.values()):
        raise RuntimeError('Nonfinite CPU/GPU solution')
    return max(abs(cpu_grid[q]-gpu_grid[q]) for q in cpu_grid)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--binary', required=True)
    ap.add_argument('--suite', choices=['check','pilot','formal'], default='check')
    ap.add_argument('--threads', type=int, required=True, help='Tc=min(12, allocated physical cores); local checks may use 2/4')
    ap.add_argument('--cpu-only', action='store_true', help='Local CPU checks only; never GPU evidence')
    ap.add_argument('--small-memory', action='store_true', help='Entire formal matrix becomes 32/64/128; document reason')
    ap.add_argument('--out', required=True, help='New output directory, must not exist')
    args = ap.parse_args()
    if not 1<=args.threads<=12:
        ap.error('--threads must be 1..12')
    if not args.cpu_only and args.threads<2:
        ap.error('GPU comparison requires Tc>=2; obtain at least 2 physical CPU cores')
    if args.cpu_only and args.suite!='check':
        ap.error('--cpu-only is restricted to local check suite')
    if hasattr(os,'sched_getaffinity') and args.threads>len(os.sched_getaffinity(0)):
        ap.error('Requested thread count exceeds process CPU affinity')
    binary = Path(args.binary).resolve()
    if not binary.is_file():
        ap.error('Binary does not exist; build first')
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = out/'source'
    source.mkdir()
    for p in Path(__file__).resolve().parent.iterdir():
        if p.is_file() and p.suffix in ('.cpp','.c','.h','.py','.sh','.md','.example'):
            shutil.copy2(p, source/p.name)
    env = dict(os.environ)
    env.update(OMP_DYNAMIC='FALSE', OMP_PROC_BIND='close', OMP_PLACES='cores')
    if not args.cpu_only:
        env['OMP_TARGET_OFFLOAD']='MANDATORY'
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir() if p.is_file()}
    save(out/'environment.json', {
        'platform':platform.platform(), 'host':platform.node(), 'python':sys.version,
        'binary':str(binary), 'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
        'source_sha256':hashes, 'arguments':vars(args),
        'affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
        'environment':{k:v for k,v in env.items() if k.startswith(('OMP_','PBS_','CUDA_VISIBLE_DEVICES','LOADEDMODULES'))},
        'lscpu':command_info(['lscpu']),
        'gpu':command_info(['nvidia-smi','--query-gpu=index,uuid,pci.bus_id,name,memory.total,driver_version','--format=csv']),
        'gpu_listing':command_info(['nvidia-smi','-L']),
        'nvhpc':command_info(['nvc++','--version']),
        'gcc':command_info(['gcc','--version']),
    })
    results=[]
    seq=0
    grids={}
    def run(dim,nx,ny,nz,K,backend,T,tag,grid=False):
        nonlocal seq
        seq+=1
        name=f'{seq:03d}_{tag}'
        cmd=[str(binary),'--backend',backend,'--dim',str(dim),'--nx',str(nx),'--ny',str(ny),
             '--nz',str(nz),'--iterations',str(K),'--threads',str(T)]
        if grid:
            cmd+=['--grid',str(out/(name+'.grid.csv'))]
        save(out/(name+'.command.json'),cmd)
        started=time.time()
        p=subprocess.run(cmd,env=env,capture_output=True,text=True)
        (out/(name+'.stdout.json')).write_text(p.stdout)
        (out/(name+'.stderr.txt')).write_text(p.stderr)
        if p.returncode:
            raise RuntimeError(f'{tag}: exit {p.returncode}; see {name}.stderr.txt')
        r=json.loads(p.stdout)
        for k,v in r.items():
            if isinstance(v,float) and not math.isfinite(v):
                raise RuntimeError(f'{tag}: nonfinite {k}')
        if (r['dimension'],r['nx'],r['ny'],r['nz'],r['iterations'])!=(dim,nx,ny,nz if dim==3 else 0,K):
            raise RuntimeError(f'{tag}: wrong grid or iteration count')
        if r['backend']!=backend or r['status']!='completed_fixed_work' or r['boundary_error_inf']>1e-12:
            raise RuntimeError(f'{tag}: backend/status/boundary failed')
        metrics=['cpu_seconds'] if backend=='cpu' else ['gpu_resident_seconds','gpu_e2e_seconds']
        if any(r[k]<=0 for k in metrics):
            raise RuntimeError(f'{tag}: invalid timing')
        if backend=='cpu' and r['actual_threads']!=T:
            raise RuntimeError(f'{tag}: wrong actual thread count')
        if backend=='gpu' and (not r['gpu_verified'] or r.get('target_is_initial_device',True) or r['num_devices']<1 or r['gpu_e2e_seconds']<r['gpu_resident_seconds']):
            raise RuntimeError(f'{tag}: GPU verification/timing failed')
        r['tag']=tag
        r['wall_seconds']=time.time()-started
        if grid:
            expected=one_step_reference(nx,ny,nz,dim,K) if K<=2 else None
            with (out/(name+'.grid.csv')).open() as f:
                actual={(int(x['i']),int(x['j']),int(x['k'])):float(x['u']) for x in csv.DictReader(f)}
            grids[tag]=actual
            if any(not math.isfinite(x) for x in actual.values()):
                raise RuntimeError(f'{tag}: nonfinite grid')
            if expected is not None and actual.keys()!=expected.keys():
                raise RuntimeError(f'{tag}: missing/extra grid points')
            difference=max(abs(actual[q]-expected[q]) for q in expected) if expected is not None else None
            if difference is not None and difference>1e-12:
                raise RuntimeError(f'{tag}: independent step reference mismatch {difference}')
            if difference is not None:
                r['independent_step_error']=difference
        print(f'PASS {tag}: R={r["relative_residual"]:.6g}',flush=True)
        return r
    try:
        checks=[]
        modes=[('cpu',1),('cpu',args.threads)]
        if not args.cpu_only:
            modes.append(('gpu',1))
        for dim in (2,3):
            for backend,T in modes:
                r=run(dim,7,7,7 if dim==3 else 1,1000,backend,T,f'check_d{dim}_{backend}_t{T}',grid=True)
                if r['discrete_error_inf']>1e-9:
                    raise RuntimeError(f'{r["tag"]}: discrete error exceeds 1e-9')
                checks.append(r)
        # One and two steps test odd/even buffer roles and directional coefficients.
        for K in (1,2):
            for dim in (2,3):
                for backend,T in modes:
                    checks.append(run(dim,9,7,5 if dim==3 else 1,K,backend,T,
                                      f'step{K}_d{dim}_{backend}_t{T}',grid=True))
        differences=[]
        if not args.cpu_only:
            for gpu in [r for r in checks if r['backend']=='gpu']:
                reference=next(r for r in checks if r['backend']=='cpu' and r['requested_threads']==1
                    and all(r[k]==gpu[k] for k in ('dimension','nx','ny','nz','iterations')))
                cpu_grid,gpu_grid=grids[reference['tag']],grids[gpu['tag']]
                difference=solution_difference(cpu_grid,gpu_grid)
                gpu['cpu_gpu_diff_inf']=difference
                row={k:gpu[k] for k in ('dimension','nx','ny','nz','iterations','cpu_gpu_diff_inf')}
                row.update(cpu_tag=reference['tag'],gpu_tag=gpu['tag'],tolerance=1e-9,passed=difference<=1e-9)
                differences.append(row)
            save(out/'cpu_gpu_comparison.json',differences)
            if not all(r['passed'] for r in differences):
                raise RuntimeError('CPU/GPU solution difference exceeds 1e-9')
        save(out/'validation.json',checks)
        if args.suite!='check':
            sizes=[64] if args.suite=='pilot' else ([32,64,128] if args.small_memory else [64,128,256])
            # Rotate sizes AND modes within every size: each measured round starts
            # each size with a different mode. One warmup + three balanced rounds.
            order=[]
            for repeat in range(4):
                offset=repeat%len(sizes)
                size_order=sizes[offset:]+sizes[:offset]
                offset=repeat%len(modes)
                mode_order=modes[offset:]+modes[:offset]
                configs=[(n,b,t) for n in size_order for b,t in mode_order]
                for n,backend,T in configs:
                    order.append(dict(repeat=repeat,n=n,backend=backend,threads=T))
                    save(out/'execution_order.json',order)
                    r=run(3,n,n,n,1000,backend,T,f'n{n}_{backend}_t{T}_r{repeat}')
                    r.update(repeat=repeat,warmup=int(repeat==0))
                    results.append(r)
                    with (out/'samples.csv').open('w',newline='') as f:
                        writer=csv.DictWriter(f,fieldnames=list(results[0]))
                        writer.writeheader(); writer.writerows(results)
            # Same grid, K, initial condition: residual norms should match across paths.
            for n in sizes:
                rr=[r['relative_residual'] for r in results if r['nx']==n]
                if max(rr)-min(rr)>1e-9*max(max(rr),1e-12):
                    raise RuntimeError(f'n={n}: final residual differs across configurations')
        save(out/'run_status.json',{'status':'COMPLETED','cpu_only':args.cpu_only,
            'suite':args.suite,'performance_samples':len(results),'validation_cases':len(checks)})
        print(f'COMPLETED: {out}',flush=True)
    except Exception as e:
        save(out/'run_status.json',{'status':'FAILED','error':str(e),'performance_samples':len(results)})
        raise

if __name__=='__main__':
    main()
