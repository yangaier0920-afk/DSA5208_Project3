#!/usr/bin/env python3
"""Explicit submission only; never retries or invents job IDs on server failure."""
import argparse,json,pathlib,subprocess,re
p=argparse.ArgumentParser();p.add_argument('--submit',action='store_true');p.add_argument('--out',default='results/final_202611/B_nov09/submitted_jobs.json');a=p.parse_args()
if not a.submit:print('Prepared only. Run inside the Vanda project directory with --submit after checking PBS availability.');raise SystemExit
check=subprocess.run(['qstat','-Q'],text=True,capture_output=True)
if check.returncode:raise SystemExit('PBS unavailable; no jobs submitted:\n'+check.stderr)
file=pathlib.Path(a.out);file.parent.mkdir(parents=True,exist_ok=True)
if file.exists():raise SystemExit('Submission manifest already exists; inspect it rather than duplicate jobs')
rows=[];ids={}
order=[('clean144',None),('paired144','clean144'),('baseline',None),('optimize72','baseline'),('suspect_diag',None),('link_suspect',None),('link_reference','clean144')]
for name,parent in order:
 cmd=['qsub']+(['-W','depend=afterok:'+ids[parent]] if parent else [])+['b_mpi/nov09/jobs/'+name+'.pbs']
 r=subprocess.run(cmd,text=True,capture_output=True)
 if r.returncode:
  file.write_text(json.dumps({'status':'PARTIAL','submitted':rows,'failure':{'command':cmd,'stderr':r.stderr}},indent=2));raise SystemExit(r.stderr)
 job=r.stdout.strip();assert re.fullmatch(r'\d+\.[\w.-]+',job),job
 ids[name]=job;rows.append({'name':name,'job':job,'depends_on':ids.get(parent),'command':cmd})
 file.write_text(json.dumps({'status':'SUBMITTING','submitted':rows},indent=2));print(name,job,flush=True)
file.write_text(json.dumps({'status':'SUBMITTED','submitted':rows},indent=2))
