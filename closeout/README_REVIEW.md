# Technical closeout / 2026-11-07

The integrated review edition omits author identification and personal declarations at the user's request. It is not a Canvas submission receipt or member sign-off.

Completed:
- A serial inputs and C formal samples independently re-audited; C English chapter written.
- Primary B scaling standardized to the CPU/topology and nominal 512-GB host capacity class. Main 72/144/288 points use 3/4/9 hosts.
- 144-core independent review on four hosts (partially different host set), with explicit remote OpenMP settings and OS CPU masks. Original 144-core scaling observations remain in the main curve.
- Separate paired hybrid cohorts: original single-node 72 cores and controlled four-node 144-core review. A paired MPI control is never replaced by a different scaling allocation's time.
- 63 supplementary calls have per-rank mask-size, allowed-set and no-overlap checks; 20 scaling and eight paired-layout configurations give 84 formal observations, plus three separate diagnostics.
- The original cohort, old hybrid data and failed startup attempts are preserved internally; no slow valid observation is deleted for appearance.
- English PDF/Markdown, consistent report figures, source/CSV whitelist and code-review guide prepared.

Optional 432/720-core jobs remain queued for insufficient available CPU resources; no time or success is fabricated for them. Author identity, individual contributions, personal understanding and final Canvas action remain human responsibilities, intentionally outside this review edition.

Rebuild derived material:
1. With internal raw evidence available: `python3 closeout/prepare_cohorts.py`.
2. `python3 closeout/plot_report.py` (only concise numeric CSVs required).
3. `python3 closeout/build_report.py` (ReportLab/Pillow; DejaVu fonts from matplotlib or REPORT_FONT_DIR).
4. `python3 closeout/package_review.py`.

The public review ZIP excludes raw logs, qstat, executables, terminal transcriptions, SSH sockets and authentication data. It includes the exact numerical CSVs needed by the plotting script, plus the real implementations and build/reproduction instructions.
