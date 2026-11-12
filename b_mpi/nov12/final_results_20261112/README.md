# B follow-up results — 12 November 2026

Only independently completed PBS jobs with exit zero enter the tables. Times are medians of all three formal samples (five for P1), after one warmup. Min/max bars are observed ranges, not confidence intervals. Slow samples are retained.

## Scheduler status (snapshot, not live)

Last collected: 2026-11-12T15:04:13.068685+08:00. SSH disconnected afterward; uncompleted jobs may have progressed.

| experiment | job | state | exit_status |
|---|---|---|---|
| clean144 | 1536849.stdct-mgmt-02 | F | 0 |
| paired144 | 1536850.stdct-mgmt-02 | Q | None |
| baseline | 1546654.stdct-mgmt-02 | R | None |
| optimize72 | 1546655.stdct-mgmt-02 | H | None |
| suspect_diag | 1536853.stdct-mgmt-02 | Q | None |
| link_suspect | 1546667.stdct-mgmt-02 | Q | None |
| link_reference | 1536855.stdct-mgmt-02 | F | 0 |

## Audited new measurements

| job | mode | case | P | T | median | minimum | maximum | max_deviation_pct |
|---|---|---|---|---|---|---|---|---|
| 1536849.stdct-mgmt-02 | clean144 | strong256 | 144 | 1 | 1.199994487 | 0.984019688 | 1.244006979 | 17.997982602398423 |
| 1536849.stdct-mgmt-02 | clean144 | strong128 | 144 | 1 | 0.354812486 | 0.25554742900000005 | 0.370043714 | 27.976765451258657 |
| 1536849.stdct-mgmt-02 | clean144 | weak64 | 144 | 1 | 1.4708567179999998 | 1.389114813 | 1.549147981 | 5.5574349288861065 |
| 1536849.stdct-mgmt-02 | clean144 | strong512 | 144 | 1 | 4.75848068 | 4.755006098 | 5.14623819 | 8.14876713968291 |

## Optional 432/720-core results recovered from 8 November

| id | nodes | median | minimum | maximum |
|---|---|---|---|---|
| strong_512x512x512_p720_t1 | 10 | 1.521555195 | 1.4999461680000001 | 1.5655860019999999 |
| weak_640x576x512_p720_t1 | 10 | 2.077773583 | 2.069086781 | 2.339810424 |
| weak_576x512x384_p432_t1 | 6 | 1.991137045 | 1.944318718 | 2.002234596 |

## Interpretation and limits

- The nine-host P144 rerun is separate from the four-host hybrid control. Its host count/ranks per host changed; recovery cannot uniquely identify faulty hardware. No monotonicity acceptance filter is used.

- The old P144 observations remain in the historical archive. Main tables replace them only after a completed four-host paired run. Open diamonds show the separate nine-host results.

- New exclusive P1 samples replace the old shared-node P1 denominator only when the full five-repeat job is audited. The old weak-P1 (64 cubed) denominator is retained and labelled by the reference efficiencies E1/E8/E72.

- Cross-core scaling combines allocations and dates on the same CPU model; occupancy, NUMA placement, CPU frequency and node topology can differ. A serial controls use the actual same core as MPI P1.

- Optimization gains must use the matched experimental baseline. The original binary is an external reference because the experimental source changes the allocation representation. First touch is implemented but actual NUMA page placement is not independently measured.

- Axis communication/wait totals aggregate both neighbors. Rank/host/neighbor tables identify participants, not a uniquely faulty one-way link. Link RTTs are descriptive windows, not fitted network alpha/beta constants.

- Optional 2D and 3D problems have different work sizes and decompositions; compare trends rather than claiming a dimension-only runtime advantage.

## Figures

![Strong scaling](strong_scaling.png)

![Weak scaling](weak_scaling.png)


## Measured conclusions

- Nine-host 256 cubed P144: 1.199994 s [0.984020, 1.244007], versus historical four-host 13.854904 s. This establishes a different observed operating regime, with host/layout/date confounding.

- Nine-host 128 cubed P144: 0.354812 s [0.255547, 0.370044], versus historical four-host 11.993227 s. This establishes a different observed operating regime, with host/layout/date confounding.

- Nine-host 512 cubed P144: 4.758481 s [4.755006, 5.146238], versus historical four-host 16.727098 s. This establishes a different observed operating regime, with host/layout/date confounding.

- Diagnostic 1536849.stdct-mgmt-02, slowest rank 112 (CN-142): largest axis wait is y, 0.199253 s; participants CN-140 / CN-142. Instrumented and formal runtimes are separate.
