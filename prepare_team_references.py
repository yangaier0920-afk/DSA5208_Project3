"""Generate checked serial reference cases and optional sequential local pilot data.

Example:
python prepare_team_references.py --executable build/jacobi_serial.exe \
    --out-dir results/team_reference_v0.1 --pilot

Run with the serial build. Pilot timings describe this machine and are not
Atlas measurements. Existing evidence directories are never overwritten.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess


BASE = Path(__file__).resolve().parent


def independent_grid(n, iterations):
    """Small list-of-lists oracle, independent of the C++ flat-array indexing."""
    grid = [[0.0 for _ in range(n + 2)] for _ in range(n + 2)]
    for row in range(n + 2):
        for col in range(n + 2):
            if row in (0, n + 1) or col in (0, n + 1):
                grid[row][col] = (row + col) / (n + 1)
    for _ in range(iterations):
        updated = [row[:] for row in grid]
        for row in range(1, n + 1):
            for col in range(1, n + 1):
                updated[row][col] = sum((
                    grid[row - 1][col], grid[row + 1][col],
                    grid[row][col - 1], grid[row][col + 1],
                )) / 4.0
        grid = updated
    return grid


def run(executable, case, output_dir):
    command = [str(executable), str(case['n']), str(case['max_iters']), str(case['tolerance'])]
    env = dict(os.environ, OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE')
    completed = subprocess.run(command, env=env, text=True, capture_output=True, timeout=180)
    (output_dir / (case['id'] + '.stdout.json')).write_text(completed.stdout, encoding='utf-8')
    (output_dir / (case['id'] + '.stderr.txt')).write_text(completed.stderr, encoding='utf-8')
    if completed.returncode != case.get('expected_exit_code', 0):
        raise ValueError(f"{case['id']}: unexpected exit {completed.returncode}: {completed.stderr}")
    result = json.loads(completed.stdout)
    if result['mode'] != 'serial' or result['threads'] != 1:
        raise ValueError('Use the serial build for reference generation')
    if result['n'] != case['n'] or result['tolerance'] != case['tolerance']:
        raise ValueError(f"{case['id']}: echoed parameters differ")
    for field in ('max_update', 'max_error', 'residual_inf', 'boundary_error', 'compute_seconds'):
        if not math.isfinite(result[field]) or result[field] < 0:
            raise ValueError(f"{case['id']}: invalid {field}")
    return {'case_id': case['id'], 'command': command, 'exit_code': completed.returncode, 'result': result}


def validate(record, case, settings):
    result = record['result']
    if result['status'] != case['expected_status']:
        raise ValueError(f"{case['id']}: unexpected status")
    if result['boundary_error'] > settings['boundary_abs_tolerance']:
        raise ValueError(f"{case['id']}: boundary mismatch")
    if case['tolerance'] == 0 or case['expected_exit_code'] == 2:
        if result['iterations'] != case['max_iters']:
            raise ValueError(f"{case['id']}: wrong fixed/limited iteration count")
    if case['n'] <= 8:
        expected = independent_grid(case['n'], result['iterations'])
        actual = result['grid']
        width = case['n'] + 2
        if len(actual) != width or any(len(row) != width for row in actual):
            raise ValueError(f"{case['id']}: wrong global grid shape")
        differences = [abs(actual[i][j] - expected[i][j]) for i in range(width) for j in range(width)]
        if not all(math.isfinite(value) for value in differences):
            raise ValueError(f"{case['id']}: non-finite grid")
        record['independent_grid_max_difference'] = max(differences)
        if max(differences) > settings['fixed_grid_abs_tolerance']:
            raise ValueError(f"{case['id']}: independent reference mismatch")
    if case['expected_status'] == 'update_tolerance_reached':
        if not (1 <= result['iterations'] <= case['max_iters']):
            raise ValueError(f"{case['id']}: invalid convergence iterations")
        if result['max_update'] > case['tolerance']:
            raise ValueError(f"{case['id']}: stopping tolerance not reached")
        if result['max_error'] > settings['small_converged_max_error']:
            raise ValueError(f"{case['id']}: exact solution error too large")
        if result['residual_inf'] > settings['small_converged_residual_inf']:
            raise ValueError(f"{case['id']}: residual too large")
    record['validation'] = 'PASS'


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--executable', required=True, type=Path)
    parser.add_argument('--out-dir', required=True, type=Path)
    parser.add_argument('--pilot', action='store_true')
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    config_path = BASE / 'team_contract_v0.1.json'
    config = json.loads(config_path.read_text(encoding='utf-8'))
    output_dir = args.out_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    provenance = {
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'contract_version': config['contract_version'],
        'source_sha256': hashlib.sha256((BASE / 'jacobi.cpp').read_bytes()).hexdigest(),
        'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
        'contract_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
        'source_hash_note': 'current source file; build command/log must establish the executable was compiled from it',
        'scope': 'local serial correctness and optional local pilot; not an Atlas benchmark',
    }
    save(output_dir / 'contract_snapshot.json', config)
    records = []
    for case in config['validation']['cases']:
        record = run(executable, case, output_dir)
        validate(record, case, config['validation'])
        records.append(record)
        print(f"PASS {case['id']}: iterations={record['result']['iterations']}", flush=True)
    save(output_dir / 'reference_results.json', dict(provenance, status='PASS', cases=records))
    if args.pilot:
        pilots = []
        for n in (256, 512, 1024, 2048):
            case = {'id': f'pilot_n{n}_k1000', 'n': n, 'max_iters': 1000, 'tolerance': 0.0,
                    'expected_status': 'fixed_iterations', 'expected_exit_code': 0}
            record = run(executable, case, output_dir)
            validate(record, case, config['validation'])
            record['two_grid_memory_mib'] = 2 * (n + 2)**2 * 8 / 2**20
            pilots.append(record)
            print(f"PILOT n={n}: {record['result']['compute_seconds']:.6f} s", flush=True)
        save(output_dir / 'local_pilot.json', dict(provenance, repeats_per_profile=1,
             convergence_claim=False, cases=pilots))


if __name__ == '__main__':
    main()
