#!/bin/bash
# Execute inside a PBS allocation after loading a compatible C++/MPI/Python stack.
set -euo pipefail
: "${PBS_JOBID:?Run inside a PBS batch or interactive job}"
: "${PBS_O_WORKDIR:?Missing PBS working directory}"
cluster_name="${1:?Usage: bash run_cluster.sh Atlas|Vanda}"
cd "$PBS_O_WORKDIR"
run_dir="$PBS_O_WORKDIR/results/${cluster_name}_parallel_${PBS_JOBID}"
mkdir -p "$run_dir"
exec > >(tee "$run_dir/run.log") 2>&1
trap 'status=$?; printf "JOB_EXIT_STATUS=%s\n" "$status"; exit "$status"' EXIT
# A new output directory is required for every independent PBS job.
if [ -e "$run_dir/metadata.txt" ]; then
    echo 'Existing run metadata; do not overwrite a previous run.' >&2
    exit 1
fi
{
    date -Is
    hostname
    whoami
    printf 'CLUSTER=%s\nJOB_ID=%s\nQUEUE=%s\n' "$cluster_name" "$PBS_JOBID" "${PBS_QUEUE:-unknown}"
    printf 'N=%s\nK=%s\nREPEATS=%s\n' "${JACOBI_N:-1024}" "${JACOBI_K:-1000}" "${JACOBI_REPEATS:-5}"
    command -v g++ mpicxx mpirun python3
    g++ --version
    mpicxx --showme 2>/dev/null || mpicxx -show
    mpirun --version
    python3 --version
    type module >/dev/null 2>&1 && module list || true
    if command -v git >/dev/null 2>&1; then
        git rev-parse HEAD || true
        git status --short || true
    fi
} > "$run_dir/metadata.txt" 2>&1
cat "$run_dir/metadata.txt"
if [ -r "${PBS_NODEFILE:-/nonexistent}" ]; then
    cp "$PBS_NODEFILE" "$run_dir/pbs_nodefile.txt"
    cat "$run_dir/pbs_nodefile.txt"
fi
mkdir "$run_dir/sources"
cp jacobi.cpp jacobi_mpi.cpp Makefile verify_small.py verify_parallel.py prepare_team_references.py \
    team_contract_v0.1.json benchmark_parallel.py run_cluster.sh atlas_jacobi.pbs vanda_jacobi.pbs vanda_modules.example.sh "$run_dir/sources/"
if [ -f vanda_modules.sh ]; then cp vanda_modules.sh "$run_dir/sources/"; fi
sha256sum "$run_dir"/sources/* > "$run_dir/source_sha256.txt"
# Build from the archived sources, preserving exactly what produced the executable.
make -C "$run_dir/sources" all BUILD="$run_dir/bin" CXX=g++ MPICXX=mpicxx
sha256sum "$run_dir"/bin/* > "$run_dir/executable_sha256.txt"
export OMP_DYNAMIC=FALSE
export OMP_NUM_THREADS=1
python3 "$run_dir/sources/verify_small.py" "$run_dir/bin/jacobi_serial" "$run_dir/bin/jacobi_omp"
python3 "$run_dir/sources/verify_parallel.py" --serial "$run_dir/bin/jacobi_serial" \
    --mpi "$run_dir/bin/jacobi_mpi" --hybrid "$run_dir/bin/jacobi_hybrid" \
    --launcher 'mpirun --bind-to none' --out-dir "$run_dir/validation"
python3 "$run_dir/sources/benchmark_parallel.py" --build-dir "$run_dir/bin" \
    --out-dir "$run_dir/benchmark" --cluster "$cluster_name" --allocated-cpus 12 \
    --n "${JACOBI_N:-1024}" --iterations "${JACOBI_K:-1000}" \
    --repeats "${JACOBI_REPEATS:-5}" \
    --configs 'mpi:1:1,mpi:2:1,mpi:3:1,mpi:4:1,mpi:6:1,mpi:12:1,openmp:1:12,hybrid:1:12,hybrid:2:6,hybrid:3:4,hybrid:4:3,hybrid:6:2,hybrid:12:1' \
    --mpi-args='--map-by slot:PE={threads} --bind-to core --report-bindings'
printf 'RUN_STATUS=PASSED\n'
