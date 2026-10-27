"""Validate MPI/hybrid solvers against serial and the independent small-grid oracle.
Run on a compute node for cluster validation; Python uses only the standard library.
"""
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
from prepare_team_references import independent_grid, validate

BASE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--serial', required=True, type=Path)
    ap.add_argument('--mpi', required=True, type=Path)
    ap.add_argument('--hybrid', type=Path)
    ap.add_argument('--launcher', default='mpirun')
    ap.add_argument('--processes', default='1,2,3,4')
    ap.add_argument('--threads', default='1,2')
    ap.add_argument('--out-dir', required=True, type=Path)
    args = ap.parse_args()
    processes = [int(x) for x in args.processes.split(',')]
    thread_counts = [int(x) for x in args.threads.split(',')]
    if not processes or not thread_counts or min(processes + thread_counts) < 1:
        ap.error('processes and threads must be positive')
    executables = {'serial': args.serial.resolve(strict=True), 'mpi': args.mpi.resolve(strict=True)}
    if args.hybrid:
        executables['hybrid'] = args.hybrid.resolve(strict=True)
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    config = json.loads((BASE / 'team_contract_v0.1.json').read_text())
    cases = config['validation']['cases'] + [
        {'id': 'one_row_per_rank', 'n': 4, 'max_iters': 2, 'tolerance': 0,
         'expected_exit_code': 0, 'expected_status': 'fixed_iterations'},
        {'id': 'three_rows_per_rank', 'n': 12, 'max_iters': 17, 'tolerance': 0,
         'expected_exit_code': 0, 'expected_status': 'fixed_iterations'},
    ]
    summary = {'generated_at_utc': datetime.now(timezone.utc).isoformat(),
               'scope': 'numerical correctness validation; not scaling evidence',
               'job_id': os.environ.get('PBS_JOBID'), 'host': platform.node(),
               'platform': platform.platform(), 'status': 'RUNNING', 'runs': [],
               'sha256': {str(p.relative_to(BASE)): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in [BASE / 'jacobi.cpp', BASE / 'jacobi_mpi.cpp',
                                    BASE / 'team_contract_v0.1.json']},
               'executable_sha256': {k: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for k, p in executables.items()}}

    def execute(label, mode, p, t, case, exchange='sendrecv', invalid_args=None):
        exe = executables[mode]
        command = ([] if mode == 'serial' else shlex.split(args.launcher) + ['-np', str(p)])
        command += [str(exe)] + (invalid_args if invalid_args is not None else
                    [str(case['n']), str(case['max_iters']), str(case['tolerance'])])
        if mode != 'serial' and invalid_args is None:
            command += ['--exchange', exchange]
        env = dict(os.environ, OMP_NUM_THREADS=str(t), OMP_DYNAMIC='FALSE',
                   OMP_PROC_BIND='FALSE')
        run = subprocess.run(command, env=env, capture_output=True, text=True, timeout=120)
        (out / (label + '.stdout.json')).write_text(run.stdout)
        (out / (label + '.stderr.txt')).write_text(run.stderr)
        record = {'id': label, 'command': command, 'processes': p, 'threads': t,
                  'exit_code': run.returncode, 'OMP_NUM_THREADS': str(t)}
        summary['runs'].append(record)
        if invalid_args is not None:
            assert run.returncode != 0 and not run.stdout.strip(), (label, run.stdout, run.stderr)
        else:
            assert run.returncode == case['expected_exit_code'], (label, run.returncode, run.stderr)
            data = json.loads(run.stdout)
            record['result'] = data
            validate(record, case, config['validation'])
            assert data['mode'] == mode and data['threads'] == t, (label, data)
            assert data['n'] == case['n'] and data['tolerance'] == case['tolerance']
            assert math.isfinite(data['compute_seconds']) and data['compute_seconds'] >= 0
            if mode != 'serial':
                assert data['mpi_processes'] == p and data['exchange'] == exchange
                assert 1 <= data['nodes'] <= p
        record['validation'] = 'PASS'
        return record.get('result')

    try:
        for case in cases:
            serial = execute(case['id'] + '_serial', 'serial', 1, 1, case)
            for mode in ('mpi', 'hybrid'):
                if mode not in executables:
                    continue
                for p in processes:
                    if p > case['n']:
                        continue
                    for t in ([1] if mode == 'mpi' else thread_counts):
                        for exchange in ('sendrecv', 'overlap'):
                            label = f"{case['id']}_{mode}_p{p}_t{t}_{exchange}"
                            result = execute(label, mode, p, t, case, exchange)
                            for field in ('max_update', 'max_error', 'residual_inf', 'boundary_error'):
                                assert math.isclose(result[field], serial[field], rel_tol=1e-10, abs_tol=1e-12), (label, field)
                            if case['n'] <= 8:
                                oracle = independent_grid(case['n'], result['iterations'])
                                difference = max(abs(a-b) for ra, rb in zip(result['grid'], oracle)
                                                 for a, b in zip(ra, rb))
                                assert difference <= config['validation']['fixed_grid_abs_tolerance']
            print('PASS', case['id'], flush=True)
        for mode in ('mpi', 'hybrid'):
            if mode not in executables:
                continue
            for label, p, argv in [('too_many_ranks', 2, ['1', '1', '0']),
                                   ('negative_tolerance', 2, ['8', '2', '-1']),
                                   ('nan_tolerance', 2, ['8', '2', 'nan']),
                                   ('bad_exchange', 2, ['8', '2', '0', '--exchange', 'bad'])]:
                execute(mode + '_' + label, mode, p, 1, None, invalid_args=argv)
        summary['status'] = 'PASS'
    except Exception as error:
        summary['status'] = 'FAIL'
        summary['error'] = str(error)
        raise
    finally:
        (out / 'summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(f"PASS: {len(summary['runs'])} executions; results: {out}")


if __name__ == '__main__':
    main()
