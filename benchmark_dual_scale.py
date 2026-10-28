"""Two scales in one allocation: 18 warmups + 162 measurements = 180 launches."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
from types import SimpleNamespace
from benchmark_parallel import solver_command, check_affinity

BASE = Path(__file__).resolve().parent
TRIALS = [('serial', 1, 1, 'none')] + [
    ('mpi', p, 1, e) for p in (1, 2, 4, 12) for e in ('sendrecv', 'overlap')]
FIELDS = ('max_update', 'max_error', 'residual_inf', 'boundary_error')


def execution_plan():
    plan = []
    for repeat in range(-1, 9):
        sizes = (1024, 2048) if repeat < 0 or repeat % 2 == 0 else (2048, 1024)
        offset = max(0, repeat)
        configs = TRIALS[offset:] + TRIALS[:offset]
        for block, n in enumerate(sizes):
            for position, config in enumerate(configs):
                plan.append(dict(sequence=len(plan), n=n, repeat_index=repeat,
                                 warmup=repeat < 0, scale_block=block,
                                 within_scale_position=position, config=list(config)))
    return plan


def groups(runs):
    baseline = statistics.median(r['result']['compute_seconds'] for r in runs
                                if not r['warmup'] and r['result']['mode'] == 'serial')
    output = []
    for mode, p, t, exchange in TRIALS:
        times = [r['result']['compute_seconds'] for r in runs if not r['warmup'] and
                 (r['result']['mode'], r['result'].get('mpi_processes', 1),
                  r['result']['threads'], r['result'].get('exchange', 'none')) == (mode, p, t, exchange)]
        if len(times) != 9 or min(times) <= 0:
            raise ValueError('Missing samples or nonpositive timing')
        median = statistics.median(times)
        output.append(dict(mode=mode, processes=p, threads=t, exchange=exchange,
                           total_cores=p*t, median_seconds=median,
                           min_seconds=min(times), max_seconds=max(times),
                           speedup=baseline/median, efficiency=baseline/median/(p*t)))
    return output


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build-dir', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--pin-cpus', required=True)
    ap.add_argument('--launcher', default='mpirun')
    args = ap.parse_args()
    if not os.environ.get('PBS_JOBID'):
        ap.error('Performance measurements require a PBS allocation')
    cpus = [int(c) for c in args.pin_cpus.split(',')]
    if len(cpus) != 12 or len(set(cpus)) != 12 or min(cpus) < 0 or not hasattr(os, 'sched_getaffinity'):
        ap.error('Require twelve distinct allocated Linux CPUs')
    if set(cpus) != set(os.sched_getaffinity(0)):
        ap.error('CPU list must equal inherited allocation mask')
    binaries = {m: (args.build_dir/('jacobi_'+m)).resolve(strict=True) for m in ('serial', 'mpi')}
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for n in (1024, 2048):
        (out/f'n{n}').mkdir()
    summary = dict(status='RUNNING', schema='dual-scale-v1', cluster='Vanda', host=platform.node(),
                   job_id=os.environ['PBS_JOBID'], generated_at_utc=datetime.now(timezone.utc).isoformat(),
                   iterations=1000, tolerance=0, warmups=1, repeats=9, allocated_cpus=12,
                   serial_source='jacobi_serial_row_update.cpp', pin_cpus=cpus,
                   source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in BASE.iterdir() if p.is_file() and p.suffix in ('.py', '.cpp', '.json', '.pbs', '.sh')},
                   executable_sha256={m: hashlib.sha256(p.read_bytes()).hexdigest() for m, p in binaries.items()},
                   plan=execution_plan(), runs=[], scales={})
    save(out/'execution_plan.json', summary['plan'])
    references = {}
    try:
        for item in summary['plan']:
            n = item['n']
            mode, p, t, exchange = item['config']
            command_args = SimpleNamespace(n=n, iterations=1000, launcher=args.launcher,
                                           mpi_args='--bind-to none --map-by slot')
            command = solver_command(mode, p, t, exchange, binaries[mode], command_args, cpus)
            label = f'{mode}_p{p}_t{t}_{exchange}_r{item["repeat_index"]}'
            record = dict(item, id=label, command=command, exit_code=None)
            summary['runs'].append(record)
            record['started_at_utc'] = datetime.now(timezone.utc).isoformat()
            save(out/'summary.json', summary)
            run = subprocess.run(command, capture_output=True, text=True, timeout=1800,
                                 env=dict(os.environ, OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE'))
            target = out/f'n{n}'
            (target/(label+'.stdout.json')).write_text(run.stdout, encoding='utf-8')
            (target/(label+'.stderr.txt')).write_text(run.stderr, encoding='utf-8')
            record.update(exit_code=run.returncode, finished_at_utc=datetime.now(timezone.utc).isoformat())
            if run.returncode:
                raise RuntimeError(f'n{n}/{label}: exit {run.returncode}')
            data = json.loads(run.stdout)
            record['result'] = data
            if (data['mode'], data['n'], data['iterations'], data['tolerance'], data['threads'], data['status']) != (
                    mode, n, 1000, 0, 1, 'fixed_iterations'):
                raise ValueError('Wrong fixed workload')
            if mode == 'mpi' and (data['mpi_processes'], data['exchange'], data['nodes']) != (p, exchange, 1):
                raise ValueError('Wrong MPI configuration')
            if any(not math.isfinite(data[f]) or data[f] < 0 for f in FIELDS+('compute_seconds',)):
                raise ValueError('Invalid numeric field')
            if data['boundary_error'] > 1e-14:
                raise ValueError('Boundary changed')
            references.setdefault(n, data)
            if any(not math.isclose(data[f], references[n][f], rel_tol=1e-10, abs_tol=1e-12) for f in FIELDS):
                raise ValueError('Global metrics differ from this scale serial reference')
            record['affinity_before_exec'] = check_affinity(run.stderr, cpus, p, summary['host'])
            print(f"seq={item['sequence']} n={n} {label}: {data['compute_seconds']:.6f}s", flush=True)
        for n in (1024, 2048):
            runs = [r for r in summary['runs'] if r['n'] == n]
            scale = {k: v for k, v in summary.items() if k not in ('scales', 'plan', 'runs')}
            scale.update(n=n, runs=runs, groups=groups(runs), order='dual-scale-interleaved', status='PASS')
            summary['scales'][str(n)] = dict(n=n, groups=scale['groups'])
            save(out/f'n{n}'/'summary.json', scale)
        summary['status'] = 'PASS'
    except Exception as error:
        summary.update(status='FAIL', error=str(error))
        raise
    finally:
        save(out/'summary.json', summary)
    print('PASS: 180 executions; 18 warmups, 162 formal; scales analyzed separately')


if __name__ == '__main__':
    main()
