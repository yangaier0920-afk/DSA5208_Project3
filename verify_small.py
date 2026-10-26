"""Numerical checks using hand-computed values and an exact harmonic solution.
Usage: python verify_small.py SERIAL_EXECUTABLE [OPENMP_EXECUTABLE]
Python is a checking helper; the algorithm itself is implemented in C++.
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys


def run(executable, n, iterations, tolerance, threads=1, expected_return=0):
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), OMP_DYNAMIC="FALSE")
    result = subprocess.run(
        [str(Path(executable).resolve()), str(n), str(iterations), str(tolerance)],
        check=False, capture_output=True, text=True, env=env, timeout=60,
    )
    if result.returncode != expected_return:
        raise AssertionError(f"return={result.returncode}: {result.stderr}")
    data = json.loads(result.stdout)
    for name in ("max_update", "max_error", "residual_inf", "boundary_error"):
        assert math.isfinite(data[name]), (name, data)
    assert data["boundary_error"] == 0.0, data
    return data


def check(executable):
    one = run(executable, 1, 1, 0)
    assert abs(one["grid"][1][1] - 1.0) < 1e-14, one
    two = run(executable, 2, 1, 0)
    expected = [[1/6, 1/2], [1/2, 5/6]]
    for i in range(2):
        for j in range(2):
            assert abs(two["grid"][i+1][j+1] - expected[i][j]) < 1e-14, two
    for n in (8, 16, 32):
        data = run(executable, n, 100000, 1e-12)
        assert data["status"] == "update_tolerance_reached", data
        assert data["max_error"] < 1e-8, data
        assert data["residual_inf"] < 1e-7, data
        print(json.dumps(data, ensure_ascii=False))
    short = run(executable, 16, 1, 1e-12, expected_return=2)
    assert short["status"] == "iteration_limit", short
    print(f"PASS: hand values, boundaries, exact solution, residual, iteration limit: {executable}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    check(sys.argv[1])
    if len(sys.argv) == 3:
        check(sys.argv[2])
        serial = run(sys.argv[1], 8, 30, 0)
        for threads in (1, 2, 4):
            parallel = run(sys.argv[2], 8, 30, 0, threads=threads)
            assert parallel["mode"] == "openmp", parallel
            assert parallel["threads"] == threads, parallel
            for a_row, b_row in zip(serial["grid"], parallel["grid"]):
                assert max(abs(a-b) for a, b in zip(a_row, b_row)) < 1e-14
            print(f"PASS: serial/OpenMP full grid after 30 iterations, threads={threads}")
