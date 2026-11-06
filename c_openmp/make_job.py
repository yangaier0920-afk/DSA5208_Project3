#!/usr/bin/env python3
"""Generate a PBS GPU job only after user confirms current resource rules."""
import argparse
from pathlib import Path
import re

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--queue',required=True)
p.add_argument('--project',help='Authorized billing project, e.g. personal-yixu_zhu; verify hpc project')
p.add_argument('--select',required=True,help='Actual PBS select, e.g. 1:ncpus=12:ngpus=1:mem=8gb ONLY if queue permits it')
p.add_argument('--threads',type=int,required=True)
p.add_argument('--suite',choices=['check','pilot','formal'],required=True)
p.add_argument('--walltime',required=True,help='HH:MM:SS, based on queue limit / pilot')
p.add_argument('--confirmed-resources',action='store_true')
p.add_argument('--small-memory',action='store_true')
p.add_argument('--output',required=True)
a=p.parse_args()
if not a.confirmed_resources:
    p.error('Inspect queue/resource rules first, then pass --confirmed-resources')
if a.project and not re.fullmatch(r'[A-Za-z0-9_.-]+',a.project):p.error('Invalid project')
if not re.fullmatch(r'[A-Za-z0-9_-]+',a.queue):p.error('Invalid queue')
if not re.fullmatch(r'1(?::[A-Za-z0-9_]+=[A-Za-z0-9_.-]+)+',a.select):p.error('Expected one PBS chunk with key=value resources')
resources=dict(x.split('=',1) for x in a.select.split(':')[1:])
if resources.get('ngpus')!='1':p.error('Expected ngpus=1; if school uses another resource name, adapt this script after checking')
if not 2<=a.threads<=12 or int(resources.get('ncpus','0'))<a.threads:p.error('Require 2<=Tc<=12 and ncpus>=Tc')
if not re.fullmatch(r'\d{2,3}:[0-5]\d:[0-5]\d',a.walltime) or a.walltime=='00:00:00':p.error('Invalid walltime')
extra=' --small-memory' if a.small_memory else ''
text='''#!/usr/bin/env bash
#PBS -N C_openmp_SUITE
#PBS -q QUEUE
PROJECT_LINE
#PBS -l select=SELECT
#PBS -l walltime=WALLTIME
#PBS -j oe
set -euo pipefail
: "${PBS_O_WORKDIR:?Submit with qsub from c_openmp directory}"
: "${PBS_JOBID:?This script runs inside PBS, not with bash on a login node}"
cd "$PBS_O_WORKDIR"
batch="$PBS_O_WORKDIR/results/C_SUITE_${PBS_JOBID//[^a-zA-Z0-9_.-]/_}"
mkdir -p "$batch"
exec > >(tee "$batch/run.log") 2>&1
trap 'rc=$?; echo "JOB_EXIT_STATUS=$rc"; exit "$rc"' EXIT
mkdir "$batch/source_build"
cp jacobi_c_openmp.cpp jacobi_c_target.c jacobi_c_target.h build.sh run_c.py analyze_c.py README.md make_job.py cluster_env.sh "$batch/source_build/"
cp "$PBS_O_WORKDIR/JOBFILE" "$batch/source_build/"
cd "$batch/source_build"
source ./cluster_env.sh
module list 2>&1
hostname
lscpu
nvidia-smi
nvc++ --version
python3 --version
export OMP_TARGET_OFFLOAD=MANDATORY OMP_DYNAMIC=FALSE OMP_PROC_BIND=close OMP_PLACES=cores
echo 'BUILD=separate C++ multicore host + C OpenMP GPU; see build.sh for exact flags'
bash build.sh nvidia
python3 run_c.py --binary build/jacobi_c_gpu --suite SUITE --threads THREADS --out "$batch/data"EXTRA
echo RUN_STATUS=COMPLETED
'''
output=Path(a.output)
if output.exists():p.error('Output exists; choose new filename')
if not re.fullmatch(r'[A-Za-z0-9_.-]+\.pbs',output.name):p.error('Use a simple .pbs filename')
# Simultaneous replacement: tokens in user resource strings are not reinterpreted.
values=dict(SUITE=a.suite,QUEUE=a.queue,SELECT=a.select,WALLTIME=a.walltime,
            THREADS=str(a.threads),EXTRA=extra,JOBFILE=output.name,PROJECT_LINE=('#PBS -P '+a.project if a.project else ''))
text=re.sub(r'PROJECT_LINE|SUITE|QUEUE|SELECT|WALLTIME|THREADS|JOBFILE|EXTRA',lambda m:values[m.group()],text)
output.write_text(text)
print(f'Written {output}. Run qsub {output.name} only after editing cluster_env.sh and checking resource rules.')
