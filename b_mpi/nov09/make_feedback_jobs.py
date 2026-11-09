#!/usr/bin/env python3
"""Prepare scripts only; topology constraints are explicit and reviewable."""
import argparse,json,pathlib
p=argparse.ArgumentParser();p.add_argument('--project',default='personal-e1561365');p.add_argument('--out',default='b_mpi/nov09/jobs');a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
good=['cn-003','cn-110','cn-126','cn-136','cn-139','cn-141','cn-143','cn-145','cn-146']
def selection(hosts,cores):return '+'.join(f'1:ncpus={cores}:mpiprocs={cores}:ompthreads=1:mem=8gb:host={h}' for h in hosts)
plans=[('clean144','clean144',selection(good,16),'scatter','00:20:00'),('paired144','paired144',selection(good[:4],36),'scatter','00:20:00'),('baseline','baseline','1:ncpus=72:mpiprocs=1:ompthreads=1:mem=16gb','scatter:exclhost','00:45:00'),('optimize72','optimize72','1:ncpus=72:mpiprocs=72:ompthreads=1:mem=16gb','scatter:exclhost','00:45:00'),('suspect_diag','suspect_diag',selection(['cn-011','cn-084','cn-108','cn-152'],36),'scatter','00:10:00'),('link_reference','links',selection(['cn-003','cn-110'],1),'scatter','00:10:00'),('link_suspect','links',selection(['cn-011','cn-108'],1),'scatter','00:10:00')]
for name,mode,select,place,wall in plans:
 body=f'''#!/bin/bash
#PBS -N B09_{name}
#PBS -P {a.project}
#PBS -l select={select}
#PBS -l place={place}
#PBS -l walltime={wall}
#PBS -j oe
#PBS -S /bin/bash
set -euo pipefail
: "${{PBS_JOBID:?Submit through PBS}}"
cd "$PBS_O_WORKDIR"
source ./b_mpi/runtime_modules.sh
out="results/final_202611/B_nov09/{name}_${{PBS_JOBID}}"
mkdir -p "$out"
exec > >(tee "$out/run.log") 2>&1
trap 'status=$?; echo JOB_EXIT_STATUS=$status' EXIT
qstat -f "$PBS_JOBID" > "$out/qstat_start.txt"
cp "$PBS_NODEFILE" "$out/pbs_nodefile.txt"
module list
python3 b_mpi/nov09/run_feedback.py --mode {mode} --out "$out/data"
echo RUN_STATUS=PASSED
'''
 (out/(name+'.pbs')).write_text(body)
(out/'plan.json').write_text(json.dumps({'good_hosts':good,'excluded_old144_hosts':['cn-011','cn-108','cn-084','cn-152','cn-039','gn-a40-047'],'jobs':[dict(name=x[0],mode=x[1],select=x[2],place=x[3],walltime=x[4]) for x in plans],'submission_order':'clean144 -> paired144 -> baseline -> optimize72; reference link after paired144; suspect links after suspect_diag to avoid same-user overlapping-host allocations'},indent=2))
print(out)
