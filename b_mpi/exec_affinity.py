#!/usr/bin/env python3
"""Audit the actual OS CPU mask before exec; no work enters the solver timer."""
import json,os,socket,sys
cpus=sorted(os.sched_getaffinity(0));threads=int(os.environ['OMP_NUM_THREADS'])
print('AFFINITY_JSON '+json.dumps({'rank':int(os.environ['OMPI_COMM_WORLD_RANK']),'host':socket.gethostname(),'cpus':cpus,'threads':threads}),file=sys.stderr,flush=True)
if len(cpus)!=threads:raise SystemExit('CPU mask size differs from requested threads')
os.execv(sys.argv[1],sys.argv[1:])
