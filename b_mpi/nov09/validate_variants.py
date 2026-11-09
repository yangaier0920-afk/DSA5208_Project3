#!/usr/bin/env python3
import argparse,json,pathlib,subprocess,os
p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--out',required=True);p.add_argument('--launcher',default='mpirun --oversubscribe --bind-to none');a=p.parse_args()
out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=False);binary=pathlib.Path(a.binary).resolve();results=[]
for variant in ('baseline','parallel_pack','first_touch','persistent','optimized'):
 wrapper=out/('exec_'+variant+'.sh');wrapper.write_text('#!/bin/sh\nexec '+str(binary)+' "$@" --variant '+variant+'\n');wrapper.chmod(0o755)
 r=subprocess.run(['python3','b_mpi/verify_b.py','--binary',str(wrapper.resolve()),'--launcher',a.launcher,'--out',str(out/variant)],text=True,capture_output=True,timeout=180)
 (out/(variant+'.validation.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,(variant,r.stderr)
 summary=json.loads((out/variant/'summary.json').read_text());assert summary['status']=='PASS';results.append({'variant':variant,'cases':len(summary['cases']),'maximum_oracle_error':max(x['oracle_error_inf'] for x in summary['cases'])})
(out/'summary.json').write_text(json.dumps({'status':'PASS','variants':results},indent=2));print(json.dumps(results))
