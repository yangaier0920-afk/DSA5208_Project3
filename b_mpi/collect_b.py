#!/usr/bin/env python3
"""Local collector: query PBS, download completed jobs, retain scheduler evidence."""
import argparse,json,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--jobs',nargs='*');p.add_argument('--socket',default='/tmp/dsa5208-vanda-e1561365.sock');p.add_argument('--host',default='e1561365@vanda.nus.edu.sg');p.add_argument('--manifest',default='b_mpi/jobs_submitted.json');args=p.parse_args()
m=json.loads(pathlib.Path(args.manifest).read_text());out=pathlib.Path('results/final_202611/B_mpi');out.mkdir(parents=True,exist_ok=True)
jobs=[m['validation']]+m.get('additional_validations',[])+m['formal_jobs'];status=[]
if args.jobs:jobs=[j for j in jobs if j['job'].split('.')[0] in args.jobs or j['job'] in args.jobs]
for job in jobs:
 ident=job['job'];run=subprocess.run(['ssh','-S',args.socket,args.host,'qstat -xf -F json '+ident],text=True,capture_output=True)
 if run.returncode:status.append(dict(job=ident,error=run.stderr));continue
 data=json.loads(run.stdout);state=data['Jobs'][ident];status.append(dict(job=ident,state=state['job_state'],exit_status=state.get('Exit_status'),comment=state.get('comment','')))
 is_validation=job in [m['validation']]+m.get('additional_validations',[])
 folder=('validation_' if is_validation else 'Vanda_')+ident
 if state['job_state']=='F' and state.get('Exit_status') in (0,1):
  dest=out/folder
  if not dest.exists() or not (dest/'qstat_final.json').exists():
   subprocess.run(['scp','-r','-o','ControlPath='+args.socket,args.host+':'+m['remote_directory']+'/results/final_202611/B_mpi/'+folder,str(out)],check=True)
  (dest/'qstat_final.json').write_text(json.dumps(state,indent=2))
status_file=out/'job_status.json'
if args.jobs and status_file.exists():
 previous=json.loads(status_file.read_text());fresh={x['job']:x for x in status};status=[fresh.pop(x['job'],x) for x in previous]+list(fresh.values())
status_file.write_text(json.dumps(status,indent=2));print(json.dumps(status,indent=2))
