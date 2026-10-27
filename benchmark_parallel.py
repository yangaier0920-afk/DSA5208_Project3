"""Repeated serial/MPI/hybrid fixed-work benchmarks; preserve commands and raw outputs.
No cluster performance claims are made until this script is run on that cluster.
"""
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

BASE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-dir', type=Path, default=Path('build'))
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--cluster', required=True, choices=('local', 'Atlas', 'Vanda'), help='Use local on a laptop; Atlas/Vanda only on that cluster')
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--iterations', type=int, default=1000)
    ap.add_argument('--warmups', type=int, default=1)
    ap.add_argument('--repeats', type=int, default=5)
    ap.add_argument('--configs', default='mpi:1:1,mpi:2:1,mpi:4:1,hybrid:4:3,hybrid:2:6,hybrid:1:12,hybrid:12:1')
    ap.add_argument('--exchanges', default='sendrecv,overlap')
    ap.add_argument('--launcher', default='mpirun')
    ap.add_argument('--mpi-args', default='', help='Optional launcher arguments; {threads} and {processes} are expanded')
    ap.add_argument('--allocated-cpus', type=int, required=True)
    args = ap.parse_args()
    if args.cluster != 'local' and not os.environ.get('PBS_JOBID'):
        ap.error('Atlas/Vanda measurements must run inside a PBS allocation')
    configs = [('serial', 1, 1)]
    try:
        configs += [(mode, int(p), int(t)) for mode, p, t in
                    (s.split(':') for s in args.configs.split(',') if s)]
    except ValueError:
        ap.error('configs must be mode:processes:threads comma-separated')
    exchanges = args.exchanges.split(',')
    if args.warmups < 0 or args.repeats < 1 or not 1 <= args.n <= 2048 or not 1 <= args.iterations <= 10000000:
        ap.error('invalid problem size or repetition count')
    if any(e not in ('sendrecv', 'overlap') for e in exchanges):
        ap.error('unknown exchange')
    for mode, p, t in configs:
        if mode not in ('serial', 'mpi', 'hybrid', 'openmp') or min(p, t) < 1 or p*t > args.allocated_cpus:
            ap.error('invalid/oversubscribed configuration')
        if (mode in ('serial', 'openmp') and p != 1) or (mode in ('serial', 'mpi') and t != 1):
            ap.error('serial/OpenMP require one process; serial/MPI require one thread')
        if p > args.n:
            ap.error('process count exceeds n')
    paths = {'serial': 'jacobi_serial', 'openmp': 'jacobi_omp', 'mpi': 'jacobi_mpi', 'hybrid': 'jacobi_hybrid'}
    executables = {mode: (args.build_dir / paths[mode]).resolve(strict=True) for mode, _, _ in configs}
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'RUNNING', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
               'cluster': args.cluster, 'host': platform.node(), 'platform': platform.platform(),
               'job_id': os.environ.get('PBS_JOBID'), 'allocated_cpus': args.allocated_cpus,
               'n': args.n, 'iterations': args.iterations, 'tolerance': 0,
               'warmups': args.warmups, 'repeats': args.repeats,
               'runs': [], 'groups': [], 'note': 'Fixed iterations; no convergence claim. Efficiency denominator is P*T.',
               'executable_sha256': {m: hashlib.sha256(p.read_bytes()).hexdigest() for m, p in executables.items()},
               'source_sha256': {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest()
                                 for name in ('jacobi.cpp', 'jacobi_mpi.cpp', 'benchmark_parallel.py')}}
    baseline = None
    reference = None
    try:
        for mode, p, t in configs:
            for exchange in (exchanges if mode in ('mpi', 'hybrid') else ['none']):
                times = []
                for repetition in range(-args.warmups, args.repeats):
                    command = []
                    if mode in ('mpi', 'hybrid'):
                        command = shlex.split(args.launcher) + ['-np', str(p)]
                        command += shlex.split(args.mpi_args.format(threads=t, processes=p))
                    command += [str(executables[mode]), str(args.n), str(args.iterations), '0']
                    if exchange != 'none':
                        command += ['--exchange', exchange]
                    env = dict(os.environ, OMP_NUM_THREADS=str(t), OMP_DYNAMIC='FALSE',
                               OMP_PLACES='cores', OMP_PROC_BIND='close')
                    label = f'{mode}_p{p}_t{t}_{exchange}_r{repetition}'
                    run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=1800)
                    (out / (label + '.stdout.json')).write_text(run.stdout)
                    (out / (label + '.stderr.txt')).write_text(run.stderr)
                    record = {'id': label, 'command': command, 'exit_code': run.returncode,
                              'warmup': repetition < 0, 'repeat_index': repetition,
                              'environment': {k: env[k] for k in ('OMP_NUM_THREADS', 'OMP_DYNAMIC', 'OMP_PLACES', 'OMP_PROC_BIND')}}
                    summary['runs'].append(record)
                    if run.returncode != 0:
                        raise RuntimeError(f'{label}: return={run.returncode}: {run.stderr}')
                    result = json.loads(run.stdout)
                    record['result'] = result
                    if (result['mode'] != mode or result['n'] != args.n or result['threads'] != t or
                            result['iterations'] != args.iterations or result['tolerance'] != 0 or
                            result['status'] != 'fixed_iterations'):
                        raise ValueError(f'{label}: wrong workload/team')
                    if mode in ('mpi', 'hybrid') and (result['mpi_processes'] != p or result['exchange'] != exchange):
                        raise ValueError(f'{label}: wrong MPI configuration')
                    for field in ('compute_seconds', 'max_update', 'max_error', 'residual_inf', 'boundary_error'):
                        if not math.isfinite(result[field]) or result[field] < 0:
                            raise ValueError(f'{label}: invalid {field}')
                    if reference is None:
                        reference = result
                    for field in ('max_update', 'max_error', 'residual_inf', 'boundary_error'):
                        if not math.isclose(result[field], reference[field], rel_tol=1e-10, abs_tol=1e-12):
                            raise ValueError(f'{label}: {field} differs from serial')
                    if repetition >= 0:
                        times.append(result['compute_seconds'])
                median = statistics.median(times)
                if median <= 0:
                    raise ValueError('Timer resolution too low; increase workload')
                if mode == 'serial':
                    baseline = median
                summary['groups'].append({'mode': mode, 'processes': p, 'threads': t,
                    'total_cores': p*t, 'exchange': exchange, 'median_seconds': median,
                    'min_seconds': min(times), 'max_seconds': max(times),
                    'speedup': baseline / median, 'efficiency': baseline / median / (p*t)})
                print(f'{mode} {p}x{t} {exchange}: median={median:.6f}s speedup={baseline/median:.3f}', flush=True)
        summary['status'] = 'PASS'
    except Exception as error:
        summary['status'] = 'FAIL'
        summary['error'] = str(error)
        raise
    finally:
        (out / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
        if summary['groups']:
            with (out / 'summary.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(summary['groups'][0]))
                writer.writeheader()
                writer.writerows(summary['groups'])
    print(f'PASS: results saved in {out}')


if __name__ == '__main__':
    main()
