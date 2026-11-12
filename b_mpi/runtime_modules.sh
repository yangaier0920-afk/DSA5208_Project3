# B-specific runtime setup. Source from the project root on Vanda.
source /app1/ebenv
source ./vanda_modules.example.sh
# Needed by the Open MPI PBS integration plugins used for allocation probes.
export LD_LIBRARY_PATH="/opt/pbs/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
