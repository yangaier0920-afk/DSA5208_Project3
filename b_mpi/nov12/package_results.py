#!/usr/bin/env python3
"""Create a B-only source/report/evidence package without binaries or credentials."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[2]
files={}
for directory in ('b_mpi/nov09','b_mpi/nov12'):
    for p in (ROOT/directory).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            files[str(p.relative_to(ROOT))]=p
for name in ('b_mpi/README.md','b_mpi/collect_b.py','b_mpi/jacobi_cart.cpp','b_mpi/exec_affinity.py','b_mpi/verify_b.py',
             'b_mpi/runtime_modules.sh','b_mpi/analyze_b.py','b_mpi/run_b.py','b_mpi/plot_b.py',
             'vanda_modules.example.sh','a_scaling_20261104/jacobi_a_scaling.cpp',
             'docs/final_B_mpi.md','docs/B_COMPLETION_STATUS_2026-11-12.md',
             'docs/archive/final_B_mpi_pre_20261112.md',
             'results/final_202611/B_mpi/analysis/summary.csv',
             'output/pdf/DSA5208_B_Completed_Experiments_20261112.pdf'):
    p=ROOT/name
    assert p.is_file(),name
    files[name]=p
manifest={name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in files.items()}
out=ROOT/'output/DSA5208_B_Completed_20261112.zip'
readme='''B completed core follow-up, 12 November 2026

This B-only package includes all 39 required follow-up configurations,
the optional 2D and recovered 432/720 results, sources, report, derived tables,
raw evidence and checksums. Original-node probes remain queued optional
supplements; refer to the dated PBS snapshot rather than claiming completion.

Unzip this package into a new folder. Then extract
b_mpi/nov12/final_results_20261112/raw_evidence.zip at that folder's root.
Install matplotlib/reportlab and follow b_mpi/nov12/README.md to audit/rebuild.
The historical summary is included as the frozen Nov7 reference. Source and
binary hashes describe the original builds; no compiled programs or passwords
are distributed. Regenerate job templates with your own project name for new
Vanda submissions. Existing job IDs belong to the original account.
'''
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for name,p in sorted(files.items()):z.write(p,name)
    z.writestr('README_B_PACKAGE.txt',readme)
    z.writestr('MANIFEST_SHA256.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
print(out,len(files),out.stat().st_size)
