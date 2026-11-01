# A local numerical evidence — 1 November 2026

Windows/GCC 12.2.0, -std=c++17 -O2 -Wall -Wextra -Wpedantic.
This folder contains local basic checks, not Atlas/Vanda formal timing results.

- summary.csv: three smoke cases, including the deliberate iteration limit.
- *_history.csv: true relative L2 residual histories.
- *.stdout.json / *.stderr.txt / *.command.json: original run outputs and commands.
- environment.json: platform, source/binary hashes and case-suite identity.
- compile.log: local compiler information and executed build command.
- basic_checks.json: tiny rectangular-grid one/two-step checks and input rejection.
- convergence.png / precision.csv: generated using analyze_a_numerics.py.
  A single converged grid cannot establish spatial order; the order field is blank.
- run_status.json: batch completion.

Commands and complete interpretation: [A README](../../docs/A_NUMERICS_README.md).
The first failed runner attempt remains in the local results directory; see
[A progress](../../docs/A_PROGRESS_2026-11-01.md) for its cause and correction.

