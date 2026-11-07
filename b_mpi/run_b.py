#!/usr/bin/env python3
"""Run one allocation group. Each invocation retains every sample and binding log."""
import argparse,datetime,hashlib,json,math,os,pathlib,platform,shlex,subprocess
GRIDS={1:(1,1,1),8:(2,2,2),12:(3,2,2),36:(4,3,3),72:(6,4,3),144:(6,6,4),288:(8,6,6),432:(9,8,6),720:(10,9,8)}
def matrix():
 rows=[]
 for n,ps in [(128,[1,12,36,72,144,288]),(256,[1,12,36,72,144,288]),(512,[72,144,288,720])]:
  for p in ps:rows.append(dict(suite='strong',n=[n]*3,p=p,t=1,grid=GRIDS[p],diagnostic=False))
 for p in [1,8,72,144,288,432,720]:rows.append(dict(suite='weak',n=[64*x for x in GRIDS[p]],p=p,t=1,grid=GRIDS[p],diagnostic=False))
 for p,t,g in [(12,6,(3,2,2)),(6,12,(3,2,1)),(2,36,(2,1,1)),(24,6,(4,3,2)),(12,12,(3,2,2)),(4,36,(2,2,1))]:rows.append(dict(suite='hybrid',n=[256]*3,p=p,t=t,grid=g,diagnostic=False))
 for p in [72,144,288]:rows.append(dict(suite='diagnostic',n=[256]*3,p=p,t=1,grid=GRIDS[p],diagnostic=True))
 for r in rows:r.update(id=f"{r['suite']}_{r['n'][0]}x{r['n'][1]}x{r['n'][2]}_p{r['p']}_t{r['t']}",cores=r['p']*r['t'])
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--resume-root',default=os.getenv('B_RESUME_ROOT',''));p.add_argument('--case-ids',default=os.getenv('B_CASE_IDS',''));p.add_argument('--group',required=True);p.add_argument('--out',required=True);p.add_argument('--binary',default='build/jacobi_cart_hybrid');p.add_argument('--mpi-binary');p.add_argument('--local',action='store_true');p.add_argument('--iterations',type=int,default=1000);p.add_argument('--repeats',type=int,default=3);p.add_argument('--smoke',action='store_true');args=p.parse_args()
 rows=[r for r in matrix() if str(r['cores'])==args.group]
 if args.case_ids:rows=[r for r in rows if r['id'] in args.case_ids.split(';')]
 assert rows
 out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=False)
 source=pathlib.Path('b_mpi/jacobi_cart.cpp');(out/'source.cpp').write_bytes(source.read_bytes())
 meta={'mpi_binary_sha256':hashlib.sha256(pathlib.Path(args.mpi_binary).read_bytes()).hexdigest() if args.mpi_binary else None,'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),'local':args.local,'pbs_jobid':os.getenv('PBS_JOBID'),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'binary_sha256':hashlib.sha256(pathlib.Path(args.binary).read_bytes()).hexdigest(),'platform':platform.platform(),'rows':rows}
 nodefile=os.getenv('PBS_NODEFILE')
 if not args.local:
  assert nodefile, 'formal runs require PBS allocation'
  hosts=set(pathlib.Path(nodefile).read_text().split())
  hardware_dir=out/'hardware';hardware_dir.mkdir()
  probe="import json,socket,subprocess,os,pathlib,sys; pathlib.Path(sys.argv[1],socket.gethostname()+'.json').write_text(json.dumps({'host':socket.gethostname(),'lscpu':subprocess.check_output(['lscpu'],text=True),'meminfo':open('/proc/meminfo').read(),'allowed_cpus':sorted(os.sched_getaffinity(0))}))"
  subprocess.run(['mpirun','--map-by','ppr:1:node','--bind-to','none','-np',str(len(hosts)),'python3','-c',probe,str(hardware_dir.resolve())],text=True,capture_output=True,check=True,timeout=60)
  meta['hardware']=[json.loads(file.read_text()) for file in sorted(hardware_dir.glob('*.json'))]
  signatures=[]
  for host in meta['hardware']:
   signature=[line.strip() for line in host['lscpu'].splitlines() if line.startswith(('Model name:','Thread(s) per core:','Core(s) per socket:','Socket(s):'))]
   signatures.append(signature)
  assert len(signatures)==len(hosts) and all(s==signatures[0] for s in signatures), 'mixed node hardware'
  meta['hardware_signature']=signatures[0]
 (out/'metadata.json').write_text(json.dumps(meta,indent=2))
 completed=set()
 if args.resume_root:
  for record in pathlib.Path(args.resume_root).rglob('*.record.json'):
   old=json.loads(record.read_text());oldmeta=json.loads((record.parent/'metadata.json').read_text())
   if old['repeat']<0 or old['local'] or old.get('smoke'):continue
   assert oldmeta['source_sha256']==meta['source_sha256'] and oldmeta['hardware_signature']==meta['hardware_signature']
   raw=json.loads(pathlib.Path(str(record).replace('.record.json','.stdout.json')).read_text())
   assert raw==old['result'] and raw['status']=='fixed_iterations' and raw['iterations']==args.iterations
   assert raw['nodes']==len(hosts) and raw['ranks']==old['config']['p'] and raw['threads']==old['config']['t']
   completed.add((old['config']['id'],old['repeat']))
  meta['resume_root']=args.resume_root;meta['retained_records']=sorted([list(x) for x in completed])
  (out/'metadata.json').write_text(json.dumps(meta,indent=2))
 configs=rows[:1] if args.smoke else rows
 repeats=1 if args.smoke else args.repeats
 # Interleave cases between rounds. A separate process resets all arrays each run.
 for repeat in [-1]+list(range(repeats)):
  for r in configs[repeat%len(configs):]+configs[:repeat%len(configs)]:
   if r['diagnostic'] and repeat!=0:continue
   if repeat>=0 and (r['id'],repeat) in completed:continue
   threads=r['t'];ranks=r['p'];g=r['grid'];n=r['n']
   if args.smoke:n=[7]*3
   nodefile=os.getenv('PBS_NODEFILE');nodes=len(set(pathlib.Path(nodefile).read_text().split())) if nodefile else max(1,math.ceil(r['cores']/72));rpn=ranks//nodes
   assert ranks%nodes==0
   launch=['mpirun','--report-bindings']+([] if args.local else ['--hostfile',os.environ['PBS_NODEFILE'],'--mca','ras','^tm','--mca','plm','rsh','-x','OMP_NUM_THREADS','-x','OMP_DYNAMIC','-x','OMP_PLACES','-x','OMP_PROC_BIND','-x','PATH','-x','LD_LIBRARY_PATH'])+(['--oversubscribe','--bind-to','none'] if args.local else ['--map-by',f'ppr:{rpn}:node:PE={threads}','--bind-to','core'])
   binary=args.mpi_binary if threads==1 and args.mpi_binary else args.binary
   command_binary=[binary] if args.local else ['python3','b_mpi/exec_affinity.py',str(pathlib.Path(binary).resolve())]
   cmd=launch+['-np',str(ranks)]+command_binary+['--iterations',str(args.iterations),'--diagnostic',str(int(r['diagnostic']))]
   for key,value in zip(('nx','ny','nz','px','py','pz'),n+list(g)):cmd+=['--'+key,str(value)]
   env=dict(os.environ,OMP_NUM_THREADS=str(threads),OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='close')
   prefix=out/(r['id']+f'_r{repeat}')
   pathlib.Path(str(prefix)+'.command.json').write_text(json.dumps({'command':cmd,'OMP':{k:v for k,v in env.items() if k.startswith('OMP_')}},indent=2))
   with pathlib.Path(str(prefix)+'.stdout.json').open('w') as stdout, pathlib.Path(str(prefix)+'.stderr.txt').open('w') as stderr:
    run=subprocess.run(cmd,env=env,text=True,stdout=stdout,stderr=stderr,timeout=600)
   raw=pathlib.Path(str(prefix)+'.stdout.json').read_text()
   if run.returncode:raise RuntimeError(f"failed {prefix}: {run.returncode}")
   data=json.loads(raw)
   assert data['iterations']==args.iterations and data['ranks']==ranks and data['threads']==threads
   assert data['status']=='fixed_iterations' and data['boundary_error_inf']<=1e-12
   assert all(math.isfinite(data[k]) for k in ('compute_seconds','relative_residual','discrete_error_inf','residual_l2'))
   if not args.local:assert data['nodes']==nodes,(data['nodes'],nodes)
   pathlib.Path(str(prefix)+'.record.json').write_text(json.dumps(dict(config=r,repeat=repeat,result=data,process_returncode=run.returncode,local=args.local,smoke=args.smoke),indent=2))
   print(r['id'],repeat,data['compute_seconds'],flush=True)
 (out/'COMPLETE.json').write_text(json.dumps({'status':'PASS','local':args.local,'smoke':args.smoke}))
