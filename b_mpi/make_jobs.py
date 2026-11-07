#!/usr/bin/env python3
"""Generate inspectable PBS scripts; never submit implicitly."""
import argparse,json,pathlib
from run_b import matrix
p=argparse.ArgumentParser();p.add_argument('--out',default='b_mpi/jobs');args=p.parse_args();out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
(out/'matrix.json').write_text(json.dumps(matrix(),indent=2))
for cores in sorted(set(r['cores'] for r in matrix())):
 nodes=9 if cores==288 else 4 if cores==144 else max(1,cores//72)
 ncpus=32 if cores==288 else 36 if cores==144 else max(2,min(72,cores))
 slots=min(ncpus,cores)
 script=f'''#!/bin/bash
#PBS -N B_cart_{cores}
#PBS -P personal-e1561365
#PBS -l place=scatter
#PBS -l select={nodes}:ncpus={ncpus}:mpiprocs={slots}:ompthreads=1:mem=16gb
#PBS -l walltime=01:00:00
#PBS -j oe
#PBS -S /bin/bash
set -euo pipefail
: "${{PBS_JOBID:?Submit through PBS}}"
cd "$PBS_O_WORKDIR"
source ./b_mpi/runtime_modules.sh
out="results/final_202611/B_mpi/Vanda_${{PBS_JOBID}}"
mkdir -p "$out/environment" "$out/source"
exec > >(tee "$out/run.log") 2>&1
trap 'status=$?; echo JOB_EXIT_STATUS=$status' EXIT
module list
lscpu > "$out/environment/lscpu.txt"
mpirun --version > "$out/environment/mpi.txt"
mpicxx --showme > "$out/environment/compiler_wrapper.txt"
g++ --version > "$out/environment/compiler.txt"
cat "$PBS_NODEFILE" > "$out/environment/pbs_nodefile.txt"
qstat -f "$PBS_JOBID" > "$out/environment/qstat_start.txt"
cp b_mpi/*.py b_mpi/*.cpp "$out/source/"
mkdir -p build
mpicxx -std=c++17 -O2 -Wall -Wextra -Wpedantic b_mpi/jacobi_cart.cpp -o "$out/jacobi_cart_mpi"
mpicxx -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp b_mpi/jacobi_cart.cpp -o "$out/jacobi_cart_hybrid"
printf '%s\\n' 'mpicxx -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp' > "$out/environment/flags.txt"
# Per-host physical CPU topology; binding evidence is also retained for every sample.
mpirun --map-by ppr:1:node -np {nodes} sh -c 'hostname; lscpu' > "$out/environment/nodes.txt"
python3 b_mpi/run_b.py --group {cores} --mpi-binary "$out/jacobi_cart_mpi" --binary "$out/jacobi_cart_hybrid" --out "$out/data"
echo RUN_STATUS=PASSED
'''
 (out/f'b_{cores}.pbs').write_text(script)
# Eight ranks distributed across two nodes, plus the full representative validation suite.
(out/'b_validate.pbs').write_text('''#!/bin/bash
#PBS -N B_cart_validate
#PBS -q auto_free
#PBS -l select=2:ncpus=8:mpiprocs=4:ompthreads=2:mem=2gb
#PBS -l walltime=00:15:00
#PBS -j oe
#PBS -S /bin/bash
set -euo pipefail
cd "$PBS_O_WORKDIR"
source ./b_mpi/runtime_modules.sh
out="results/final_202611/B_mpi/validation_${PBS_JOBID}"
mkdir -p "$out"
exec > >(tee "$out/run.log") 2>&1
mpicxx -std=c++17 -O2 -fopenmp b_mpi/jacobi_cart.cpp -o "$out/jacobi_cart_hybrid"
python3 b_mpi/verify_b.py --binary "$out/jacobi_cart_hybrid" --expected-nodes 2 --launcher 'mpirun --map-by node --bind-to none --report-bindings' --out "$out/checks"
echo RUN_STATUS=PASSED
''')
print(out)
