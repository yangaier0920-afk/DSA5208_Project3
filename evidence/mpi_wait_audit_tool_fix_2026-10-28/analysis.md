# Cross-Python CV rounding audit fix

The first read-only audit stopped on three CV differences of 2.78e-17, 5.55e-17 and 2.22e-16. Saved raw timings, medians, min/max and comparison records matched exactly. Only CV comparison now allows rel_tol=1e-12 / abs_tol=1e-14; other checks remain exact. Negative checks reject changes to medians, CV, samples and comparison counts. The pre-fix local script is preserved here and the original cluster script remains inside the unchanged raw snapshot. No solver rerun or raw-result edit occurred.
