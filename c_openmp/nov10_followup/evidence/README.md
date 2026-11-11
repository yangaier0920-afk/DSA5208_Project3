# C formal PBS history evidence

Reviewed on 10 November 2026 from the two user-supplied screenshots of PBS job history. The overlapping images establish the job identity, completed state and exit code. The table transcribes the relevant scheduler fields.

| Field | Value visible in the screenshots |
|---|---|
| Job ID | `1525886.stdct-mgmt-02` |
| Job name | `C_openmp_formal` |
| PBS job state | `F` |
| PBS exit status | `0` |
| Queue | `batch_gpu` |
| Compute node | `GN-A40-024` |
| Allocated resources | 36 CPUs, 1 GPU, 240 GB memory |
| Used walltime | `00:05:29` |

PBS exit status independently corroborates the successful script exit recorded in `run.log`. GPU allocation comes from `exec_vnode` and `Resource_List.ngpus`. Actual target execution is verified by all 12 GPU performance records in `samples.csv`, which report `gpu_verified=True` and `target_is_initial_device=False`. The scheduler field `resources_used.ngpus=0` is retained as displayed and is not used to determine whether the stencil ran on the device.

Original screenshots and raw job logs are retained by member C. [Job status index](../final_results_20261110/PBS_status.csv) · [Formal samples](../../deliverables/formal_20261106/samples.csv)
