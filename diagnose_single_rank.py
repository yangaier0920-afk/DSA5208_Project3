'''Controlled serial vs MPI P=1 diagnostics. Run inside a single-node PBS CPU job.
All solvers use the same Linux logical CPU; OpenMP is not enabled.
'''
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
from prepare_team_references import independent_grid

BASE = Path(__file__).resolve().parent
VARIANTS = ('serial_gpp', 'serial_mpicxx', 'mpi_sendrecv', 'mpi_overlap')
FLAGS = ['-std=c++17', '-O2', '-Wall', '-Wextra', '-Wpedantic']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def order_for_round(index, variants=VARIANTS):
    '''Each variant occupies each position once per four measured rounds.'''
    offset = index % len(variants)
    order = list(variants[offset:] + variants[:offset])
    return order if (index // len(variants)) % 2 == 0 else order[::-1]


def solver_command(variant, binary, wrapper, cpu, n, iterations, tolerance):
    command = [sys.executable, str(wrapper), '--pin-exec', str(cpu), str(binary),
               str(n), str(iterations), str(tolerance)]
    if variant.startswith('mpi_'):
        command += ['--exchange', variant.removeprefix('mpi_')]
        command = ['mpirun', '-np', '1', '--bind-to', 'none'] + command
    return command


def check_result(data, variant, n, iterations, tolerance, reference=None):
    mpi = variant.startswith('mpi_')
    require(data['mode'] == ('mpi' if mpi else 'serial'), 'Unexpected solver mode')
    require(data['n'] == n and data['tolerance'] == tolerance and data['threads'] == 1,
            'Wrong problem or thread count')
    if mpi:
        require(data['mpi_processes'] == data['nodes'] == 1, 'Expected MPI P=1 on one node')
        require(data['exchange'] == variant.removeprefix('mpi_'), 'Wrong communication strategy')
    for field in ('compute_seconds', 'max_update', 'max_error', 'residual_inf', 'boundary_error'):
        require(math.isfinite(data[field]) and data[field] >= 0, f'Invalid {field}')
    require(data['compute_seconds'] > 0 and data['boundary_error'] <= 1e-14,
            'Invalid timer or physical boundary')
    if tolerance == 0:
        require(data['status'] == 'fixed_iterations' and data['iterations'] == iterations,
                'Wrong fixed workload')
    else:
        require(data['status'] == 'update_tolerance_reached' and
                1 <= data['iterations'] <= iterations and data['max_update'] <= tolerance and
                data['max_error'] <= 1e-8 and data['residual_inf'] <= 1e-7,
                'Small-grid convergence check failed')
    if n <= 8:
        grid = data['grid']
        require(len(grid) == n+2 and all(len(row) == n+2 for row in grid), 'Wrong grid shape')
        expected = independent_grid(n, data['iterations'])
        differences = [abs(grid[i][j]-expected[i][j]) for i in range(n+2) for j in range(n+2)]
        require(all(math.isfinite(d) and d <= 1e-12 for d in differences), 'Independent grid mismatch')
    if reference is not None:
        for field in ('max_update', 'max_error', 'residual_inf', 'boundary_error'):
            require(math.isclose(data[field], reference[field], rel_tol=1e-10, abs_tol=1e-12),
                    f'{field} differs from serial')


def pin_exec():
    cpu = int(sys.argv[2])
    require(cpu in os.sched_getaffinity(0), 'Requested CPU is outside inherited affinity')
    os.sched_setaffinity(0, {cpu})
    mask = sorted(os.sched_getaffinity(0))
    require(mask == [cpu], 'Pinning failed')
    print('AB_AFFINITY ' + json.dumps({'host': platform.node(), 'cpus': mask}),
          file=sys.stderr, flush=True)
    os.execv(sys.argv[3], sys.argv[3:])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--iterations', type=int, default=1000)
    ap.add_argument('--repeats', type=int, default=8)
    ap.add_argument('--warmups', type=int, default=1)
    ap.add_argument('--allocated-cpus', type=int, default=2)
    ap.add_argument('--experiment', choices=('baseline', 'local-reduction'), default='baseline')
    args = ap.parse_args()
    require(os.environ.get('PBS_JOBID') and hasattr(os, 'sched_setaffinity'),
            'Run this diagnostic inside a Linux PBS CPU allocation')
    require(1 <= args.n <= 2048 and 1 <= args.iterations <= 10000000 and
            args.repeats >= 4 and args.warmups >= 1 and args.allocated_cpus >= 1,
            'Invalid diagnostic settings')
    variants = (('serial_gpp', 'serial_local_update', 'serial_row_update', 'mpi_sendrecv')
                if args.experiment == 'local-reduction' else VARIANTS)
    require(args.repeats % len(variants) == 0,
            'Use a multiple of the configuration count for balanced positions')
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    sources, binaries, runs = out/'sources', out/'bin', out/'runs'
    for directory in (sources, binaries, runs):
        directory.mkdir()
    summary = dict(status='RUNNING', scope='Serial vs MPI single-process diagnostic; no scaling claim',
                   generated_at_utc=datetime.now(timezone.utc).isoformat(), job_id=os.environ['PBS_JOBID'],
                   host=platform.node(), n=args.n, iterations=args.iterations, tolerance=0,
                   warmups=args.warmups, repeats=args.repeats, allocated_cpus=args.allocated_cpus,
                   flags=FLAGS, experiment=args.experiment, variants=list(variants),
                   builds=[], runs=[], groups=[])
    try:
        for name in ('jacobi.cpp', 'jacobi_mpi.cpp', 'diagnose_single_rank.py',
                     'prepare_team_references.py', 'vanda_single_rank.pbs', 'vanda_modules.example.sh'):
            shutil.copyfile(BASE/name, sources/name)
        if args.experiment == 'local-reduction':
            for name in ('jacobi_serial_local_update.cpp', 'jacobi_serial_row_update.cpp'):
                shutil.copyfile(BASE/name, sources/name)
        if (BASE/'vanda_modules.sh').is_file():
            shutil.copyfile(BASE/'vanda_modules.sh', sources/'vanda_modules.sh')
        summary['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in sources.iterdir()}
        mask = sorted(os.sched_getaffinity(0))
        summary['inherited_affinity'] = mask
        summary['environment'] = {k: os.environ.get(k) for k in
                                  ('PBS_QUEUE', 'PBS_NODEFILE', 'PBS_NCPUS', 'NCPUS', 'LOADEDMODULES')}
        for name, command in [('lscpu', ['lscpu']), ('compiler', ['g++', '--version']),
                              ('mpi_wrapper', ['mpicxx', '--showme']), ('mpi', ['mpirun', '--version']),
                              ('qstat_at_start', ['qstat', '-f', os.environ['PBS_JOBID']])]:
            try:
                run = subprocess.run(command, capture_output=True, text=True, timeout=30)
                (out/(name+'.txt')).write_text(run.stdout+run.stderr, encoding='utf-8')
            except (OSError, subprocess.TimeoutExpired) as error:
                (out/(name+'.txt')).write_text(str(error), encoding='utf-8')
        if Path('/proc/self/status').is_file():
            shutil.copyfile('/proc/self/status', out/'process_status.txt')
        if os.environ.get('PBS_NODEFILE'):
            shutil.copyfile(os.environ['PBS_NODEFILE'], out/'pbs_nodefile.txt')
        require(mask and len(mask) <= args.allocated_cpus,
                'Inherited CPU mask is wider than requested allocation. Metadata saved; '
                'check PBS/cpuset configuration before selecting a CPU.')
        cpu = mask[0]
        summary['selected_logical_cpu'] = cpu
        build_specs = [('serial_gpp', 'g++', 'jacobi.cpp'),
                       ('serial_mpicxx', 'mpicxx', 'jacobi.cpp'),
                       ('mpi', 'mpicxx', 'jacobi_mpi.cpp')]
        if args.experiment == 'local-reduction':
            build_specs = [('serial_gpp', 'g++', 'jacobi.cpp'),
                           ('serial_local_update', 'g++', 'jacobi_serial_local_update.cpp'),
                           ('serial_row_update', 'g++', 'jacobi_serial_row_update.cpp'),
                           ('mpi', 'mpicxx', 'jacobi_mpi.cpp')]
        for label, compiler, source in build_specs:
            binary = binaries/label
            command = [compiler, *FLAGS, '-fopt-info-vec-all='+str(out/(label+'_vectorization.txt')),
                       str(sources/source), '-o', str(binary)]
            run = subprocess.run(command, capture_output=True, text=True, timeout=180)
            (out/(label+'_build.log')).write_text(run.stdout+run.stderr, encoding='utf-8')
            summary['builds'].append(dict(label=label, command=command, exit_code=run.returncode))
            require(run.returncode == 0, 'Build failed: '+label)
        summary['executable_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in binaries.iterdir()}
        env = dict(os.environ, OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE')

        def execute(variant, phase, index, n, iterations, tolerance, reference):
            label = f'{phase}_{index}_{variant}_n{n}'
            binary = binaries/('mpi' if variant.startswith('mpi_') else variant)
            command = solver_command(variant, binary, sources/'diagnose_single_rank.py', cpu,
                                     n, iterations, tolerance)
            record = dict(id=label, variant=variant, phase=phase, round=index, command=command)
            summary['runs'].append(record)
            run = subprocess.run(command, capture_output=True, text=True, env=env, timeout=300)
            (runs/(label+'.stdout.json')).write_text(run.stdout, encoding='utf-8')
            (runs/(label+'.stderr.txt')).write_text(run.stderr, encoding='utf-8')
            record['exit_code'] = run.returncode
            require(run.returncode == 0, 'Solver failed: '+label)
            affinity = [json.loads(line.removeprefix('AB_AFFINITY ')) for line in run.stderr.splitlines()
                        if line.startswith('AB_AFFINITY ')]
            require(len(affinity) == 1 and affinity[0]['cpus'] == [cpu] and
                    affinity[0]['host'] == summary['host'], 'Wrong CPU affinity or host: '+label)
            record['affinity_before_exec'] = affinity[0]
            data = json.loads(run.stdout)
            record['result'] = data
            check_result(data, variant, n, iterations, tolerance, reference)
            record['validation'] = 'PASS'
            print(f"{label}: {data['compute_seconds']:.6f}s", flush=True)
            return data

        for n, iterations, tolerance in [(7, 31, 0), (32, 100000, 1e-12)]:
            reference = None
            for variant in variants:
                data = execute(variant, 'correctness', 0, n, iterations, tolerance, reference)
                if reference is None:
                    reference = data
        reference = None
        for index in range(-args.warmups, args.repeats):
            phase = 'warmup' if index < 0 else 'measured'
            for variant in (list(variants) if index < 0 else order_for_round(index, variants)):
                data = execute(variant, phase, index, args.n, args.iterations, 0, reference)
                if reference is None:
                    reference = data
        for variant in variants:
            times = [r['result']['compute_seconds'] for r in summary['runs']
                     if r['phase'] == 'measured' and r['variant'] == variant]
            require(len(times) == args.repeats, 'Missing measured executions')
            summary['groups'].append(dict(variant=variant, median_seconds=statistics.median(times),
                                          min_seconds=min(times), max_seconds=max(times)))
        baseline = summary['groups'][0]['median_seconds']
        for group in summary['groups']:
            group['ratio_vs_serial_gpp'] = baseline/group['median_seconds']
        summary['status'] = 'PASS'
        save(out/'summary.json', summary)
        print('DIAGNOSTIC_STATUS=PASSED', flush=True)
    except Exception as error:
        summary.update(status='FAIL', error=str(error))
        raise
    finally:
        save(out/'summary.json', summary)


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == '--pin-exec':
        pin_exec()
    else:
        main()
