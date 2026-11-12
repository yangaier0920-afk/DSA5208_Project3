# B cluster follow-up / 12 November 2026

See [audited results](final_results_20261112/README.md) and
[completion status](../../docs/B_COMPLETION_STATUS_2026-11-12.md).
The results include raw evidence, observed ranges and independent PBS exit
status. The status table is a dated snapshot; queued/running entries are not
performance results. Do not submit duplicates merely because a local SSH
connection expired.

## Scheduling changes

- The original nine fixed hosts had remained unavailable for two days. P144
  now requests nine scheduler-selected hosts, sixteen ranks each. All six
  hosts from both historical P144 allocations are independently rejected by
  the runner and analyzer, including fully qualified hostname aliases.
- The complete four-host P144 matrix uses scheduler-selected hosts and the
  `node_pool` placement group. CPU model and memory are checked before work.
- The exclusive P1 baseline is independent of the P144 chain. Two 36-core
  NUMA chunks are packed on one exclusive host using `group=host`; P72
  optimization follows it to avoid overlapping whole-host allocations.
- Link probes do not wait for the full original-host diagnostic. The
  reference pair is CN-005/CN-083, both used in the completed new P144 run.
  CN-011/CN-108 remain the requested historical pair. Only descriptive
  comparisons are justified if those hosts remain busy or unavailable.
- The hardware probe uses the same Open MPI hostfile/rsh allocation method
  as the formal runs. The batch environment explicitly loads `/app1/ebenv`.

Original fixed-host requests can be regenerated with
`make_feedback_jobs.py --fixed-reference-hosts`. Current templates in `jobs/`
are prepared requests; actual accepted resources are in each job's saved
`qstat_final.json`. PBS hooks can change memory requests.

## Continue collecting existing jobs

Run from the repository root after reconnecting SSH. The local submission
manifest is under `results/final_202611/B_nov09/`, or can be fetched from the
same path in `~/dsa5208_b_20261109` on Vanda. The collector reads existing job
IDs and never submits jobs.

```sh
python3 b_mpi/nov09/collect_feedback.py
python3 b_mpi/nov09/analyze_feedback.py \
  --input results/final_202611/B_nov09 \
  --out results/final_202611/B_nov12/analysis
python3 b_mpi/nov12/build_results.py
```

`build_results.py` requires matplotlib and the audited historical Nov7 data.
It publishes every accepted measurement, not only improvements. It uses the predeclared nine-host pure-MPI P144 cohort in the main series;
the separate four-host high-wait controls are shown as open diamonds. All
historical samples remain in their own table. The new P1
denominator is adopted only after all five formal repeats pass the audit.

## Optional 2D extension

The prepared `jobs/twod.pbs` uses the original solver in 2D mode for a 512×512
grid at P=1/12/36/72, K=1000, one warmup and three measured repeats, plus a
separate axis diagnostic. It completed as job 1546883 with independent PBS exit zero and passed the audit.
Upload the updated runner first. From the Vanda project root, submit with
`qsub -W depend=afterok:OPTIMIZATION_JOB_ID b_mpi/nov12/twod.pbs`.
This is a different work size from the 3D cases, so absolute timing ratios
cannot be attributed solely to dimension.

## Rebuild after a fresh pull

Install matplotlib and reportlab in your Python environment. Extract the raw
archive from the repository root before analyzing or rebuilding:

```sh
unzip b_mpi/nov12/final_results_20261112/raw_evidence.zip -d .
python3 b_mpi/nov09/analyze_feedback.py \
  --input results/final_202611/B_nov09 \
  --out results/final_202611/B_nov12/analysis
python3 b_mpi/nov12/build_results.py
python3 b_mpi/nov12/build_pdf.py
```

The recovered 432/720 summary is retained as a previously audited input;
its raw source, bindings and PBS evidence are also in the archive. The
historical Nov7 summary is tracked separately in the repository. To continue
live collection on the original account, use the submission manifest in
`final_results_20261112/submission_history.json` or fetch the remote manifest;
job IDs belonging to the original account should not be resubmitted by a
teammate. For new runs, regenerate job templates with your own project name.
