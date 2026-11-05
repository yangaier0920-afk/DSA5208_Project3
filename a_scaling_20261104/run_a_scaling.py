"""A serial scaling. Run on a compute node; --smoke is a small local check."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    p.add_argument('--smoke', action='store_true')
    a = p.parse_args()
    binary = a.binary.resolve()
    if not binary.is_file():
        p.error('Binary missing')
    if not a.smoke and not os.environ.get('PBS_JOBID'):
        p.error('Formal runs require a PBS compute allocation')
    # Pin parent before spawning: all child runs inherit the same allowed CPU.
    allowed = sorted(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else []
    if not a.smoke:
        if not allowed:
            p.error('CPU affinity unavailable')
        os.sched_setaffinity(0, {allowed[0]})
    a.out_dir.mkdir(parents=True, exist_ok=False)
    src = Path(__file__).resolve().parent
    hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
              for f in [binary, src/'jacobi_a_scaling.cpp', Path(__file__).resolve()]}
    write_json(a.out_dir/'environment.json', {
        'host': platform.node(), 'platform': platform.platform(),
        'pbs_job_id': os.environ.get('PBS_JOBID'), 'smoke_only': a.smoke,
        'allowed_cpus_before_pin': allowed,
        'selected_cpu': allowed[0] if not a.smoke else None, 'sha256': hashes,
        'timing_scope': 'K iterations only; initialization and final diagnostics excluded'})

    def run(problem, n, name):
        cmd = [str(binary), '--problem', problem, '--nx', str(n),
               '--mode', 'fixed', '--max-iters', '1000']
        proc = subprocess.run(cmd, capture_output=True, text=True)
        write_json(a.out_dir/(name+'.command.json'), {'argv': cmd, 'exit_code': proc.returncode})
        (a.out_dir/(name+'.stdout.json')).write_text(proc.stdout, encoding='utf-8')
        (a.out_dir/(name+'.stderr.txt')).write_text(proc.stderr, encoding='utf-8')
        if proc.returncode:
            raise RuntimeError(name+' failed; inspect stderr')
        row = json.loads(proc.stdout)
        if (row['problem_id'] != problem or row['nx'] != n or row['ny'] != n
                or row['nz'] != (n if problem == 'poisson3d_mms' else 0)
                or row['iterations'] != 1000 or row['status'] != 'fixed_iterations'):
            raise RuntimeError(name+' unexpected problem/workload')
        for key in ['relative_residual', 'compute_seconds', 'boundary_error_inf',
                    'continuous_error_inf', 'discrete_error_inf']:
            if not math.isfinite(row[key]):
                raise RuntimeError(name+' nonfinite '+key)
        if row['compute_seconds'] <= 0 or row['boundary_error_inf'] > 1e-12:
            raise RuntimeError(name+' invalid time/boundary')
        return row

    checks = []
    for problem in ['poisson2d_mms', 'poisson3d_mms']:
        row = run(problem, 7, 'check_'+problem)
        if row['discrete_error_inf'] > 1e-9:
            raise RuntimeError(problem+' discrete solution mismatch')
        checks.append(row)
    write_json(a.out_dir/'validation.json', checks)
    if a.smoke:
        write_json(a.out_dir/'run_status.json', {'status': 'smoke_passed', 'cases': 2})
        print('SMOKE_PASSED: 2D/3D n=7, K=1000', flush=True)
        return

    configs = [('poisson2d_mms', n) for n in [256,512,1024,2048,4096]]
    configs += [('poisson3d_mms', n) for n in [16,32,64,128,256]]
    rows = []
    reference = {}
    for repeat in range(4):
        # One full warmup round then three rotating formal rounds.
        offset = (repeat*3) % len(configs)
        order = configs[offset:] + configs[:offset]
        for problem, n in order:
            name = f'{problem}_n{n}_r{repeat}'
            row = run(problem, n, name)
            key = (problem, n)
            if key in reference and not math.isclose(row['relative_residual'], reference[key], rel_tol=1e-12, abs_tol=1e-14):
                raise RuntimeError(name+' repeated numerical results disagree')
            reference[key] = row['relative_residual']
            row.update(repeat=repeat, warmup=int(repeat==0), sequence=len(rows)+1)
            rows.append(row)
            with (a.out_dir/'samples.csv').open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
            print(f"{name}: {row['compute_seconds']:.6f}s",flush=True)
    summary = []
    previous = {}
    for problem, n in configs:
        samples=[r['compute_seconds'] for r in rows if r['problem_id']==problem and r['nx']==n and not r['warmup']]
        if len(samples) != 3:
            raise RuntimeError('Incomplete formal samples')
        d=3 if problem=='poisson3d_mms' else 2
        med=statistics.median(samples)
        prior=previous.get(problem)
        q=math.log(med/prior[1])/math.log(n/prior[0]) if prior else ''
        summary.append(dict(problem_id=problem,n=n,N=n**d,K=1000,samples=3,
                            median_seconds=med,min_seconds=min(samples),max_seconds=max(samples),
                            seconds_per_point_update=med/(1000*n**d),local_exponent=q))
        previous[problem]=(n,med)
    with (a.out_dir/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
    write_json(a.out_dir/'run_status.json', {'status':'completed','configurations':10,'warmups':10,'formal_samples':30})
    print('RUN_STATUS=COMPLETED',flush=True)


if __name__=='__main__':
    main()
