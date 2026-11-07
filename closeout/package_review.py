#!/usr/bin/env python3
"""Course-review whitelist: source + report + concise numerical inputs only."""
import csv,hashlib,json,pathlib,zipfile
ROOT=pathlib.Path('.').resolve();OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
completion=json.loads((ROOT/'closeout/completion.json').read_text());assert completion['standardized_scaling']
files=set()
def add(path):
 p=ROOT/path;assert p.is_file(),p;files.add(path)
for name in ['jacobi_numerics.cpp','run_a_numerics.py','analyze_a_numerics.py','vanda_a_numerics.pbs','vanda_modules.example.sh','jacobi.cpp','jacobi_serial_local_update.cpp','jacobi_serial_row_update.cpp','jacobi_mpi.cpp','diagnose_single_rank.py','pin_cpu.py']:
 add(name)
for name in ['jacobi_a_scaling.cpp','run_a_scaling.py','analyze_a_scaling.py','vanda_a_scaling.pbs']:add('a_scaling_20261104/'+name)
for p in (ROOT/'b_mpi').glob('*.py'):
 if p.name not in ('collect_b.py','package_b.py'):add(str(p.relative_to(ROOT)))
add('b_mpi/jacobi_cart.cpp');add('b_mpi/runtime_modules.sh');add('b_mpi/README.md');add('b_mpi/jobs/matrix.json')
for p in (ROOT/'b_mpi/jobs').glob('*.pbs'):add(str(p.relative_to(ROOT)))
for name in ['jacobi_c_openmp.cpp','jacobi_c_target.c','jacobi_c_target.h','build.sh','run_c.py','make_job.py','analyze_c.py','cluster_env.sh.example','requirements-plots.txt']:add('c_openmp/'+name)
for name in ['samples.csv','environment.json','run_status.json']:add('c_openmp/deliverables/formal_20261106/'+name)
for name in ['summary.csv','speedups.csv','validation_summary.csv']:add('c_openmp/deliverables/formal_20261106/analysis/'+name)
for name in ['samples.csv','summary.csv']:add('a_scaling_20261104/Vanda_1522376.stdct-mgmt-02/data/'+name)
for name in ['precision.csv','summary.csv']+[f'poisson3d_mms_n{n}_solve_k100000_history.csv' for n in (15,31,63)]:add('evidence/vanda_1512708_a_numerics/data/'+name)
for name in ['summary.csv','diagnostics.csv','hybrid_summary.csv']:add('results/final_202611/B_mpi/analysis/'+name)
for name in ['summary.csv','diagnostics.csv']:add('closeout/review144/'+name)
for name in ['plot_report.py','build_report.py','package_review.py','completion.json','hybrid_summary.csv','README_REVIEW.md']:add('closeout/'+name)
for p in (ROOT/'closeout/figures').glob('*'):
 if p.suffix in ('.png','.pdf'):add(str(p.relative_to(ROOT)))
for name in ['final_report_review.md','final_B_mpi.md','final_C_openmp.md','B_CODE_REVIEW_GUIDE_zh.md']:add('docs/'+name)
add('output/pdf/DSA5208_Project3_Review_Report.pdf')
readme='''# DSA5208 Project 3 - technical review package

Author names, student IDs and personal contribution statements are intentionally
omitted at the user's request. Add and personally review them before Canvas upload.
This package is a review edition, not a submission receipt.

Start with output/pdf/DSA5208_Project3_Review_Report.pdf. Editable Markdown is in
docs/final_report_review.md; B/C English chapters and a B code-review guide are included.

## Reported datasets

- A: ten serial configurations, three formal samples each; independent 3D numerical
  convergence/accuracy on 15/31/63. K=1000 scaling is separate from convergence.
- B: twenty scaling configurations plus eight paired-layout configurations, three
  formal samples each (84 total), and three separate diagnostics. Main summary.csv
  has 26 IDs/78 samples; six additional paired-control samples are represented in
  hybrid_summary.csv. Scaling uses matched CPU/topology and nominal 512-GB hosts.
  Actual scaling nodes at P72/144/288 are 3/4/9. The single-node 72-core hybrid
  comparison is a separate larger-memory paired cohort. Never substitute a scaling
  point for its paired pure-MPI control. Original slow P144 observations are retained.
- C: three grids x CPU1/CPU12/A40, with one warmup and three formal samples each.
  Resident and device-data-region end-to-end scopes are distinct; every GPU call
  has real offload evidence. Independent historical PBS exit status is unavailable.
- Optional 432/720-core queue requests have no accepted result and are omitted.

## Build (GNU / Open MPI compute node)

Load the site GCC/Open MPI stack; on Vanda source b_mpi/runtime_modules.sh.
Run make numerics scaling b-mpi c-cpu. For NVHPC GPU: make c-gpu, or
bash c_openmp/build.sh nvidia under NVHPC 24.7 / CUDA 12.3 / GCC 13.2.
The CPU/GPU build is intentionally split into C++ host and C target units.

A examples:
  build/jacobi_numerics --problem poisson3d_mms --nx 7 --max-iters 1000
  build/jacobi_a_scaling --problem poisson2d_mms --nx 7 --max-iters 1000
B validation (new output directory):
  python3 b_mpi/verify_b.py --binary build/jacobi_cart_hybrid --launcher 'mpirun --bind-to none' --out validation_b
C CPU checks:
  python3 c_openmp/run_c.py --binary c_openmp/build/jacobi_c_cpu --suite check --threads 2 --cpu-only --out validation_c

Mac: use OMPFLAGS='-Xpreprocessor -fopenmp -I/opt/homebrew/opt/libomp/include -L/opt/homebrew/opt/libomp/lib -lomp'
for the make targets. Homebrew Open MPI and libomp must already be available.
The Linux formal runner records OS CPU masks; --local mode is correctness-only.

## Formal reproduction

Use the supplied PBS generators and runners from a compute allocation. Replace
YOUR_PROJECT with your own valid CPU project. B launchers are restricted to
PBS_NODEFILE, bind ranks to their PEs and explicitly export OpenMP settings.
The run_b.py B_CASE_IDS filter selects a declared subset; for the standardized
72-rank scaling case use three 24-core chunks and select strong 128/256/512,
weak 384x256x192 and the 256-cube diagnostic, excluding hybrid thread layouts.
For the single-node 72-core paired hybrid study allocate 72 cores on one host
and retain its own MPI control. P144/P288 scaling use four 36-core / nine
32-core hosts in the same capacity class. Validate host model/memory and actual
CPU masks; do not oversubscribe or silently mix platform cohorts.
A's PBS and C's make_job.py specify their own allocation/module protocol.

## Reproduce the report figures without raw logs

Python >=3.10; install requirements-review.txt in a virtual environment.
From the package root:
  python3 closeout/plot_report.py
  python3 closeout/build_report.py

PDF building uses DejaVu fonts supplied with matplotlib; alternatively set
REPORT_FONT_DIR to the directory containing DejaVuSans.ttf and bold/oblique files.
All numerical inputs required by plot_report.py are included at their original
relative paths. Error bars show min/max, not confidence intervals.
The independent P144 review is separate from the original main series.

Raw stdout/stderr, scheduler output, terminal logs, binaries, full job archives,
credentials, SSH sockets and private connection configuration are excluded.
The public source manifest lists SHA256 for every included file. No email,
repository push or Canvas action is performed by this package.
'''
make='''CXX = c++
MPICXX = mpicxx
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra -Wpedantic
OMPFLAGS = -fopenmp
.PHONY: all numerics scaling b-mpi c-cpu c-gpu historical
all: numerics scaling b-mpi c-cpu
build:
\tmkdir -p build
numerics: build/jacobi_numerics
scaling: build/jacobi_a_scaling
b-mpi: build/jacobi_cart_mpi build/jacobi_cart_hybrid
build/jacobi_numerics: jacobi_numerics.cpp | build
\t$(CXX) $(CXXFLAGS) $< -o $@
build/jacobi_a_scaling: a_scaling_20261104/jacobi_a_scaling.cpp | build
\t$(CXX) $(CXXFLAGS) $< -o $@
build/jacobi_cart_mpi: b_mpi/jacobi_cart.cpp | build
\t$(MPICXX) $(CXXFLAGS) $< -o $@
build/jacobi_cart_hybrid: b_mpi/jacobi_cart.cpp | build
\t$(MPICXX) $(CXXFLAGS) $(OMPFLAGS) $< -o $@
c-cpu:
\tmkdir -p c_openmp/build
\t$(CXX) $(CXXFLAGS) $(OMPFLAGS) c_openmp/jacobi_c_openmp.cpp -o c_openmp/build/jacobi_c_cpu
c-gpu:
\tbash c_openmp/build.sh nvidia
historical: | build
\t$(CXX) $(CXXFLAGS) jacobi.cpp -o build/jacobi_serial
\t$(CXX) $(CXXFLAGS) jacobi_serial_local_update.cpp -o build/jacobi_serial_local_update
\t$(CXX) $(CXXFLAGS) jacobi_serial_row_update.cpp -o build/jacobi_serial_row_update
\t$(MPICXX) $(CXXFLAGS) jacobi_mpi.cpp -o build/jacobi_mpi
'''
texts={'README.md':readme,'Makefile':make,'requirements-review.txt':'matplotlib>=3.6\nreportlab>=4\nPillow>=9\npypdf>=4\n'}
# Trim internal job-status lists from the public numerical supplement.
s=(ROOT/'docs/B_RESULTS_2026-11-07.md').read_text()
if '## Job status' in s:
 start=s.index('## Job status');end=s.index('## Figures and reproducibility',start);s=s[:start]+s[end:]
texts['docs/B_RESULTS_2026-11-07.md']=s
contents={name:(ROOT/name).read_bytes() for name in sorted(files)}
for name,data in list(contents.items()):
 if pathlib.Path(name).suffix in ('.py','.sh','.pbs','.md'):
  text=data.decode().replace('personal-e1561365','YOUR_PROJECT')
  contents[name]=text.encode()
# Publish typed environment metadata, never pasted terminal output under a JSON suffix.
legacy_env=json.loads((ROOT/'c_openmp/deliverables/formal_20261106/environment.json').read_text())
if 'cpu_model' in legacy_env:
 public_env=legacy_env
else:
 device=list(csv.DictReader(legacy_env['gpu']['stdout'].strip().splitlines(),skipinitialspace=True))[0]
 cpu=next(line.split(':',1)[1].strip() for line in legacy_env['lscpu']['stdout'].splitlines() if line.startswith('Model name:'))
 public_env={'description':'Structured formal platform metadata; terminal transcripts omitted','host':legacy_env['host'],'cpu_model':cpu,'gpu_device':{'name':device['name'].strip(),'memory_mib':int(device['memory.total [MiB]'].strip().split()[0]),'driver_version':device['driver_version'].strip()},'compiler':legacy_env['compiler'],'allocation':legacy_env['allocation'],'numerical_protocol':legacy_env['numerical_protocol']}
contents['c_openmp/deliverables/formal_20261106/environment.json']=json.dumps(public_env,indent=2).encode()
contents.update({k:v.encode() for k,v in texts.items()})
manifest={'edition':'technical review; identities intentionally omitted','files':[{'path':k,'sha256':hashlib.sha256(v).hexdigest(),'bytes':len(v)} for k,v in sorted(contents.items())]}
contents['SUBMISSION_MANIFEST.json']=json.dumps(manifest,indent=2).encode()
zip_path=OUT/'DSA5208_Project3_Review_Package.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for k,v in sorted(contents.items()):z.writestr(k,v)
with zipfile.ZipFile(zip_path) as z:
 assert z.testzip() is None
 for name in z.namelist():
  assert not name.endswith(('.log','.exe','.so','.dylib','.stdout.json','.stderr.txt'))
  assert not any(x in name for x in ('qstat','run.log','.ssh','raw_archives','run_b.pyc'))
print(zip_path);print('Whitelisted files:',len(contents),'bytes:',zip_path.stat().st_size)
