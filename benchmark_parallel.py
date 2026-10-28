'''Repeated fixed-work benchmarks with recorded execution order and optional CPU pinning.'''
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shlex
import statistics
import subprocess
import sys

BASE = Path(__file__).resolve().parent


def execution_plan(configurations, warmups, repeats, order):
    if order == 'grouped':
        return [(index, config) for config in configurations for index in range(-warmups, repeats)]
    plan = [(index, config) for index in range(-warmups, 0) for config in configurations]
    for index in range(repeats):
        offset = index % len(configurations)
        rotated = configurations[offset:] + configurations[:offset]
        if (index // len(configurations)) % 2:
            rotated = rotated[::-1]
        plan.extend((index, config) for config in rotated)
    return plan


def solver_command(mode, p, t, exchange, executable, args, cpus):
    command = [str(executable), str(args.n), str(args.iterations), '0']
    if exchange != 'none':
        command += ['--exchange', exchange]
    if cpus:
        command = [sys.executable, str(BASE/'pin_cpu.py'), '--cpus', ','.join(map(str, cpus)), '--'] + command
    if mode in ('mpi', 'hybrid'):
        command = (shlex.split(args.launcher) + ['-np', str(p)] +
                   shlex.split(args.mpi_args.format(threads=t, processes=p))) + command
    return command


def check_affinity(stderr, cpus, processes, host):
    actual = [json.loads(line[12:]) for line in stderr.splitlines() if line.startswith('AB_AFFINITY ')]
    if len(actual) != processes or {a['rank'] for a in actual} != set(range(processes)):
        raise ValueError('Missing or duplicate rank affinity records')
    for entry in actual:
        if entry['cpus'] != [cpus[entry['rank']]] or entry['host'] != host:
            raise ValueError('Unexpected CPU mask or host')
    return sorted(actual, key=lambda item: item['rank'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-dir', type=Path, default=Path('build'))
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--cluster', required=True, choices=('local', 'Atlas', 'Vanda'))
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--iterations', type=int, default=1000)
    ap.add_argument('--warmups', type=int, default=1)
    ap.add_argument('--repeats', type=int, default=5)
    ap.add_argument('--configs', default='mpi:1:1,mpi:2:1,mpi:4:1,hybrid:4:3,hybrid:2:6,hybrid:1:12,hybrid:12:1')
    ap.add_argument('--exchanges', default='sendrecv,overlap')
    ap.add_argument('--launcher', default='mpirun')
    ap.add_argument('--mpi-args', default='', help='{threads} and {processes} are expanded')
    ap.add_argument('--allocated-cpus', type=int, required=True)
    ap.add_argument('--order', choices=('grouped', 'interleaved'), default='grouped')
    ap.add_argument('--serial-source', default='jacobi.cpp', help='Archived source actually used for the serial build')
    ap.add_argument('--pin-cpus', default='', help='Single-node pure MPI/serial only: rank r uses CPU list[r]')
    args = ap.parse_args()
    if args.cluster != 'local' and not os.environ.get('PBS_JOBID'):
        ap.error('Atlas/Vanda measurements must run inside a PBS allocation')
    try:
        configs = [('serial', 1, 1)] + [(m, int(p), int(t)) for m, p, t in
                    (s.split(':') for s in args.configs.split(',') if s)]
        cpus = [int(cpu) for cpu in args.pin_cpus.split(',') if cpu]
    except ValueError:
        ap.error('Invalid configuration or CPU list')
    exchanges = args.exchanges.split(',')
    if args.warmups < 0 or args.repeats < 1 or not 1 <= args.n <= 2048 or not 1 <= args.iterations <= 10000000:
        ap.error('Invalid problem size or repetition count')
    if not exchanges or len(set(exchanges)) != len(exchanges) or any(e not in ('sendrecv', 'overlap') for e in exchanges):
        ap.error('Invalid communication strategies')
    for mode, p, t in configs:
        if mode not in ('serial', 'mpi', 'hybrid', 'openmp') or min(p, t) < 1 or p*t > args.allocated_cpus:
            ap.error('Invalid/oversubscribed configuration')
        if (mode in ('serial', 'openmp') and p != 1) or (mode in ('serial', 'mpi') and t != 1) or p > args.n:
            ap.error('Wrong process/thread count')
    if len(set(configs)) != len(configs):
        ap.error('Duplicate configuration')
    if cpus:
        if any(m not in ('serial', 'mpi') for m, _, _ in configs):
            ap.error('CPU-list pinning is only for serial and pure MPI')
        if len(set(cpus)) != len(cpus) or len(cpus) > args.allocated_cpus or min(cpus) < 0:
            ap.error('Invalid CPU list')
        if len(cpus) < max(p for _, p, _ in configs) or not hasattr(os, 'sched_getaffinity'):
            ap.error('Insufficient CPUs or unsupported affinity platform')
        if not set(cpus).issubset(os.sched_getaffinity(0)):
            ap.error('CPU list is outside inherited affinity')
        if '--bind-to none' not in args.mpi_args:
            ap.error('Use --mpi-args="--bind-to none --map-by slot" with explicit CPU pinning')
    paths = {'serial': 'jacobi_serial', 'openmp': 'jacobi_omp', 'mpi': 'jacobi_mpi', 'hybrid': 'jacobi_hybrid'}
    executables = {m: (args.build_dir/paths[m]).resolve(strict=True) for m, _, _ in configs}
    trials = [(m, p, t, e) for m, p, t in configs for e in (exchanges if m in ('mpi', 'hybrid') else ['none'])]
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source_names = list(dict.fromkeys(['jacobi.cpp', 'jacobi_mpi.cpp', 'benchmark_parallel.py', args.serial_source] +
                                      (['pin_cpu.py'] if cpus else [])))
    summary = dict(status='RUNNING', generated_at_utc=datetime.now(timezone.utc).isoformat(),
                   cluster=args.cluster, host=platform.node(), platform=platform.platform(),
                   job_id=os.environ.get('PBS_JOBID'), allocated_cpus=args.allocated_cpus,
                   n=args.n, iterations=args.iterations, tolerance=0, warmups=args.warmups, repeats=args.repeats,
                   order=args.order, serial_source=args.serial_source, pin_cpus=cpus, runs=[], groups=[],
                   note='Fixed iterations; no convergence claim. Efficiency denominator is P*T.',
                   executable_sha256={m:hashlib.sha256(p.read_bytes()).hexdigest() for m,p in executables.items()},
                   source_sha256={n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in source_names})
    reference = None
    try:
        for repetition, (mode, p, t, exchange) in execution_plan(trials, args.warmups, args.repeats, args.order):
            command = solver_command(mode, p, t, exchange, executables[mode], args, cpus)
            env = dict(os.environ, OMP_NUM_THREADS=str(t), OMP_DYNAMIC='FALSE', OMP_PLACES='cores', OMP_PROC_BIND='close')
            label = f'{mode}_p{p}_t{t}_{exchange}_r{repetition}'
            record = dict(id=label, command=command, warmup=repetition<0, repeat_index=repetition,
                          environment={k:env[k] for k in ('OMP_NUM_THREADS','OMP_DYNAMIC','OMP_PLACES','OMP_PROC_BIND')})
            summary['runs'].append(record)
            run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=1800)
            (out/(label+'.stdout.json')).write_text(run.stdout, encoding='utf-8')
            (out/(label+'.stderr.txt')).write_text(run.stderr, encoding='utf-8')
            record['exit_code'] = run.returncode
            if run.returncode != 0:
                raise RuntimeError(f'{label}: return={run.returncode}: {run.stderr}')
            data = json.loads(run.stdout)
            record['result'] = data
            if (data['mode'] != mode or data['n'] != args.n or data['threads'] != t or
                data['iterations'] != args.iterations or data['tolerance'] != 0 or data['status'] != 'fixed_iterations'):
                raise ValueError(f'{label}: wrong workload/team')
            if mode in ('mpi','hybrid') and (data['mpi_processes'] != p or data['exchange'] != exchange):
                raise ValueError(f'{label}: wrong MPI configuration')
            for field in ('compute_seconds','max_update','max_error','residual_inf','boundary_error'):
                if not math.isfinite(data[field]) or data[field]<0:
                    raise ValueError(f'{label}: invalid {field}')
            if reference is None:
                reference = data
            for field in ('max_update','max_error','residual_inf','boundary_error'):
                if not math.isclose(data[field],reference[field],rel_tol=1e-10,abs_tol=1e-12):
                    raise ValueError(f'{label}: {field} differs from serial')
            if cpus:
                record['affinity_before_exec'] = check_affinity(run.stderr,cpus,p,summary['host'])
                if mode=='mpi' and data['nodes'] != 1:
                    raise ValueError('Explicit CPU mapping is for a single node')
            print(f"{label}: {data['compute_seconds']:.6f}s",flush=True)
        baseline = statistics.median([r['result']['compute_seconds'] for r in summary['runs']
                                      if not r['warmup'] and r['result']['mode']=='serial'])
        for mode,p,t,exchange in trials:
            times=[r['result']['compute_seconds'] for r in summary['runs'] if not r['warmup'] and
                   (r['result']['mode'],r['result'].get('mpi_processes',1),r['result']['threads'],
                    r['result'].get('exchange','none'))==(mode,p,t,exchange)]
            if len(times)!=args.repeats or min(times)<=0:
                raise ValueError('Missing measurements or insufficient timer resolution')
            median=statistics.median(times)
            summary['groups'].append(dict(mode=mode,processes=p,threads=t,total_cores=p*t,exchange=exchange,
                                          median_seconds=median,min_seconds=min(times),max_seconds=max(times),
                                          speedup=baseline/median,efficiency=baseline/median/(p*t)))
        summary['status']='PASS'
    except Exception as error:
        summary.update(status='FAIL',error=str(error))
        raise
    finally:
        (out/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        if summary['groups']:
            with (out/'summary.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(summary['groups'][0]));writer.writeheader();writer.writerows(summary['groups'])
    print('PASS: results saved in '+str(out))


if __name__=='__main__':
    main()
