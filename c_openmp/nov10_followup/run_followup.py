"""Run one supplemental suite inside its own PBS work directory."""
import argparse
import csv
import json
import math
import os
import statistics
import subprocess
from pathlib import Path


CPU_CASES = [
    ("a_gcc", 1), ("c_gcc_serial", 1), ("c_gcc_omp", 1),
    ("c_nv_serial", 1), ("c_nv_collapse", 1), ("c_nv_outer", 1),
    ("c_formal", 1), ("c_formal", 12),
]
PHASES = ("enter_s", "resident_s", "copyback_s", "exit_s", "first_sweep_s")


def invoke(binary, args, path, pin):
    command = [str(Path("build", binary).resolve()), *args]
    if pin is not None:
        command = ["taskset", "-c", str(pin), *command]
    result = subprocess.run(command, text=True, capture_output=True)
    path.with_suffix(".stdout").write_text(result.stdout)
    path.with_suffix(".stderr").write_text(result.stderr)
    result.check_returncode()
    return result.stdout, result.stderr


def measure(binary, n, threads, path, pin=None):
    is_a = binary == "a_gcc"
    gpu = binary == "c_gpu_phases"
    args = (
        ["--problem", "poisson3d_mms", "--mode", "fixed", "--max-iters", "1000"]
        if is_a else
        ["--backend", "gpu" if gpu else "cpu", "--iterations", "1000", "--threads", str(threads)]
    )
    stdout, stderr = invoke(binary, ["--nx", str(n), *args], path, pin)
    data = json.loads(stdout)
    if (data["nx"], data["ny"], data["nz"], data["iterations"]) != (n, n, n, 1000):
        raise ValueError(f"{path}: wrong grid or iteration count")
    residual = data["relative_residual"]
    if (not math.isfinite(residual) or data["boundary_error_inf"] != 0 or
            (n == 7 and not (0 <= data["discrete_error_inf"] <= 1e-9))):
        raise ValueError(f"{path}: numerical check failed")
    if gpu:
        if not data["gpu_verified"] or data["target_is_initial_device"]:
            raise ValueError(f"{path}: GPU execution was not verified")
        lines = [line.split()[1:] for line in stderr.splitlines() if line.startswith("C_PHASES ")]
        if len(lines) != 1 or len(lines[0]) != len(PHASES):
            raise ValueError(f"{path}: missing phase timings")
        phases = dict(zip(PHASES, map(float, lines[0])))
        e2e = data["gpu_e2e_seconds"]
        if (any(not math.isfinite(x) or x < 0 for x in phases.values()) or
                not math.isclose(sum(phases[k] for k in PHASES[:4]), e2e, abs_tol=1e-7) or
                not math.isclose(phases["resident_s"], data["gpu_resident_seconds"], abs_tol=1e-7) or
                phases["first_sweep_s"] > phases["resident_s"]):
            raise ValueError(f"{path}: inconsistent phase timings")
        return residual, {"e2e_s": e2e, **phases}
    if not is_a and data["actual_threads"] != threads:
        raise ValueError(f"{path}: requested thread count was not used")
    seconds = data["compute_seconds" if is_a else "cpu_seconds"]
    return residual, {"runtime_s": seconds}


def write_rows(path, rows):
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("cpu", "gpu", "scaling"))
    parser.add_argument("--smoke", action="store_true", help="Small local CPU test only")
    args = parser.parse_args()
    if args.smoke and args.suite != "cpu":
        parser.error("Smoke mode supports only CPU")

    cores = sorted(os.sched_getaffinity(0)) if not args.smoke else []
    pin = cores[0] if cores else None
    Path("affinity.json").write_text(json.dumps({"allowed_cpus": cores, "single_thread_cpu": pin}) + "\n")
    sizes = [7] if args.smoke else ([64, 128, 256] if args.suite == "gpu" else [256])
    if args.suite == "cpu":
        cases = CPU_CASES
    elif args.suite == "gpu":
        cases = [("c_gpu_phases", 1)]
    else:
        cases = [("c_formal", t) for t in (1, 2, 4, 8, 16, 24, 36)]
    if args.suite != "gpu" and not args.smoke and len(cores) < max(t for _, t in cases):
        raise RuntimeError("PBS CPU affinity mask is too small for the requested teams")

    checks = [
        measure(binary, 7, t, Path(f"check_{binary}_t{t}"), pin if t == 1 and args.suite != "gpu" else None)
        for binary, t in cases
    ]
    if any(abs(residual - checks[0][0]) > 1e-12 for residual, _ in checks):
        raise RuntimeError("Small-grid residuals disagree")

    configurations = [(binary, n, t) for n in sizes for binary, t in cases]
    all_rows = []
    reference = {}
    timings = {config: [] for config in configurations}
    for repeat in range(4):
        offset = repeat % len(configurations)
        for binary, n, t in configurations[offset:] + configurations[:offset]:
            path = Path(f"{binary}_{n}_t{t}_r{repeat}")
            residual, measures = measure(binary, n, t, path, pin if t == 1 and args.suite != "gpu" else None)
            if not math.isclose(residual, reference.setdefault(n, residual), rel_tol=1e-9, abs_tol=1e-12):
                raise ValueError(f"{path}: fixed-work residual differs across runs")
            if any(not math.isfinite(x) or x < 0 for x in measures.values()):
                raise ValueError(f"{path}: non-finite or negative time")
            all_rows.append({"variant": binary, "n": n, "threads": t, "repeat": repeat, **measures})
            if repeat:
                timings[binary, n, t].append(measures)
            write_rows(Path("samples.csv"), all_rows)
            print(path, measures, flush=True)

    summary = []
    for (binary, n, t), rows in timings.items():
        for metric in rows[0]:
            values = [row[metric] for row in rows]
            summary.append({"variant": binary, "n": n, "threads": t, "metric": metric,
                            "median_s": statistics.median(values), "min_s": min(values), "max_s": max(values)})
    write_rows(Path("summary.csv"), summary)

    if args.suite == "gpu":
        probes = []
        for repeat in range(3):
            stdout, _ = invoke("target_probe", [], Path(f"probe_{repeat}"), None)
            for line in stdout.splitlines():
                index, elapsed = line.split(",")
                probes.append({"process": repeat, "target_call": int(index), "seconds": float(elapsed)})
        if len(probes) != 33:
            raise RuntimeError("Expected 33 genuine device probe timings")
        write_rows(Path("target_probe.csv"), probes)

    if args.suite == "scaling":
        baseline = summary[0]["median_s"]
        for row in summary:
            row["speedup"] = baseline / row["median_s"]
            row["efficiency"] = row["speedup"] / row["threads"]
        write_rows(Path("scaling.csv"), summary)


if __name__ == "__main__":
    main()
