# A2 numerical results — Vanda, 2026-11-03

A's planned five numerical cases completed. No added experiments or reruns.
Job 1512708.stdct-mgmt-02, node CN-161, GCC12.2.0, -O2.
PBS: 2 CPU slots, 4GB, 1h limit; actual walltime34s, cput26s, Exit_status0.
The program is serial; requesting two CPU slots does not make it parallel.

| Item | Result |
|---|---|
| 3D n=15/31/63 | All converged to relative L2 residual≤1e−10 |
| Iteration counts | 1080 / 4120 / 15640 |
| Observed spatial orders | 2.0131 / 2.0032 |
| Old 2D n=1024/2048 after1000 iterations | R≈0.005014 / 0.005018; neither meets1e−8 |
| Physical boundary error | 0 in all five cases |
| Sum of timed intervals | 23.453005321s |

Files:
- run.log, compile.log, qstat_full.txt: downloaded execution/resource records.
- data/: original per-case JSON, histories, commands, environment and summary;
  convergence.png and precision.csv were generated locally after download.
- source/: local source copies. Solver and runner SHA256 match the uploaded
  hashes in data/environment.json. Analyzer/PBS/module file copies are retained
  for context; their remote hashes are not recorded in that JSON.

[Full numerical discussion](../../docs/final_A_numerics.md).
Times are single-run numerical observations, not statistical scaling estimates.
