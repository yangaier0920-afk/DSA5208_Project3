#!/usr/bin/env python3
import argparse,datetime,json,pathlib,shlex,subprocess,tarfile
p=argparse.ArgumentParser();p.add_argument('--host',default='e1561365@vanda.nus.edu.sg');p.add_argument('--socket',default='/tmp/dsa5208-vanda-e1561365.sock');p.add_argument('--remote',default='/home/svu/e1561365/dsa5208_b_20261109');p.add_argument('--out',default='results/final_202611/B_nov09');a=p.parse_args();out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True);ssh=['ssh','-S',a.socket,a.host]
manifest=out/'submitted_jobs.json'
if not manifest.exists():
 r=subprocess.run(ssh+['cat '+shlex.quote(a.remote+'/results/final_202611/B_nov09/submitted_jobs.json')],text=True,capture_output=True,check=True);manifest.write_text(r.stdout)
m=json.loads(manifest.read_text());states=[]
for item in m['submitted']:
 job=item['job'];r=subprocess.run(ssh+['qstat -xf -F json '+shlex.quote(job)],text=True,capture_output=True,check=True);q=json.loads(r.stdout).get('Jobs',{}).get(job)
 if q is None:states.append({'job':job,'status':'historical PBS record unavailable'});continue
 states.append({'job':job,'state':q['job_state'],'exit_status':q.get('Exit_status'),'comment':q.get('comment','')})
 if q['job_state']=='F':
  folder=item['name']+'_'+job;dest=out/folder
  if not (dest/'qstat_final.json').exists():
   archive=out/(folder+'.tar.gz');command='tar -C '+shlex.quote(a.remote+'/results/final_202611/B_nov09')+' -czf - '+shlex.quote(folder)
   with archive.open('wb') as f:subprocess.run(ssh+[command],stdout=f,stderr=subprocess.PIPE,check=True)
   with tarfile.open(archive) as t:t.extractall(out,filter='data')
  (dest/'qstat_final.json').write_text(json.dumps(q,indent=2))
(out/'job_status.json').write_text(json.dumps(states,indent=2));print(json.dumps(states,indent=2))

(out/'collection_snapshot.json').write_text(json.dumps({'time_singapore':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'states':states},indent=2))
