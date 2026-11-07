#!/usr/bin/env python3
"""Build a source/report/figure whitelist; never archive raw cluster logs."""
import json,pathlib,zipfile
base=pathlib.Path('.');results=base/'results/final_202611/B_mpi';analysis=results/'analysis'
audit=json.loads((analysis/'audit.json').read_text());assert audit['core_complete'],'Core experiments are incomplete'
target=results/'B_core_deliverables_20261107.zip'
files=['b_mpi/jacobi_cart.cpp','b_mpi/run_b.py','b_mpi/verify_b.py','b_mpi/exec_affinity.py','b_mpi/make_jobs.py','b_mpi/analyze_b.py','b_mpi/plot_b.py','b_mpi/write_results.py','b_mpi/README.md','vanda_modules.example.sh','b_mpi/runtime_modules.sh','docs/final_B_mpi.md']
files += [str(p) for p in (base/'b_mpi/jobs').glob('*.pbs')]+['b_mpi/jobs/matrix.json']
files += [str(p) for p in analysis.iterdir() if p.suffix in ('.csv','.png','.pdf')]
make='''MPICXX = mpicxx
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra -Wpedantic
OMPFLAGS = -fopenmp
.PHONY: all b-mpi
all: b-mpi
b-mpi: build/jacobi_cart_mpi build/jacobi_cart_hybrid
build:
\tmkdir -p build
build/jacobi_cart_mpi: b_mpi/jacobi_cart.cpp | build
\t$(MPICXX) $(CXXFLAGS) $< -o $@
build/jacobi_cart_hybrid: b_mpi/jacobi_cart.cpp | build
\t$(MPICXX) $(CXXFLAGS) $(OMPFLAGS) $< -o $@
'''
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
 for name in files:z.write(name,name)
 z.writestr('Makefile',make)
 supplement=(base/'docs/B_RESULTS_2026-11-07.md').read_text()
 start=supplement.index('## Job status');end=supplement.index('## Figures and reproducibility',start)
 supplement=supplement[:start]+supplement[end:]
 z.writestr('docs/B_RESULTS_2026-11-07.md',supplement)
 z.writestr('README.md','''# Member B core experiment deliverable

Core execution complete: 20 scaling configurations plus 8 paired-layout configurations
(84 formal samples), three communication diagnostics, and actual two-node validation.
The main summary has 26 IDs/78 samples; two extra paired controls supply 6 samples.
Optional 432/720-core extensions remain queued and are excluded from reported results.

Read docs/final_B_mpi.md for the full English chapter and limitations;
docs/B_RESULTS_2026-11-07.md has measured tables. Build/run instructions are in
b_mpi/README.md. On GNU/Open MPI: make b-mpi. The Mac OpenMP flags are documented.

Scaling now matches Xeon Platinum 8452Y, 2x36 cores, SMT off and the nominal
512-GB memory-capacity family. The single-node 72-core hybrid comparison is a
separate paired larger-memory cohort; hybrid_summary.csv supplies its correct
paired controls. Node placement and shared load still vary. Original slow data
and earlier hybrid observations remain in the internal legacy cohort.

The analysis CSV and figures are under results/final_202611/B_mpi/analysis/.
Reproduce the figures from the included concise CSV:
python3 b_mpi/plot_b.py --csv results/final_202611/B_mpi/analysis/summary.csv --out reproduced_figures
The internal raw logs are intentionally omitted here. Raw-evidence auditing uses
analyze_b.py when those internal files are available.

No member name, student ID, personal understanding or final sign-off is fabricated.
Fill in and review your contribution/AI declaration before the course submission.
This is B's module, to be merged with A and C's final report and source package.
''')
with zipfile.ZipFile(target) as z:
 assert z.testzip() is None
 assert not any(n.endswith(('.txt','.log','.stdout.json','.stderr.txt','.exe')) or 'qstat' in n or '/data/' in n for n in z.namelist())
print(target.resolve())
