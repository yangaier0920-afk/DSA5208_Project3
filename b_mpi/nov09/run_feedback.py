#!/usr/bin/env python3
"""Predeclared November 9 experiments. No acceptance filter based on speed."""
import argparse,collections,hashlib,json,math,os,pathlib,subprocess,time,sys
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['clean144','paired144','baseline','optimize72','suspect_diag','links'],required=True);p.add_argument('--out',required=True);p.add_argument('--local-smoke',action='store_true');a=p.parse_args()
if not a.local_smoke:assert os.getenv('PBS_JOBID'),'Use a PBS compute allocation'
out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=False)
build=out/'build';build.mkdir();sources=['b_mpi/jacobi_cart.cpp','b_mpi/nov09/jacobi_cart_tuned.cpp','b_mpi/nov09/mpi_link_probe.cpp','a_scaling_20261104/jacobi_a_scaling.cpp']
binaries={};compile_commands={}
for key,src,omp in [('mpi',sources[0],False),('hybrid',sources[0],True),('tuned',sources[1],True),('axis',sources[1],False),('link',sources[2],False),('serial',sources[3],False)]:
 cmd=['mpicxx' if key!='serial' else 'c++','-std=c++17','-O2','-Wall','-Wextra']+(['-fopenmp'] if omp else [])+[src,'-o',str(build/key)]
 if not a.local_smoke and key in ('mpi','serial'):cmd.insert(-3,'-fopt-info-vec-all='+str((out/(key+'.vectorization.log')).resolve()))
 if a.local_smoke and omp:cmd[cmd.index('-fopenmp'):cmd.index('-fopenmp')+1]=['-Xpreprocessor','-fopenmp','-I/opt/homebrew/opt/libomp/include','-L/opt/homebrew/opt/libomp/lib','-lomp']
 compile_commands[key]=cmd
 r=subprocess.run(cmd,capture_output=True,text=True,check=True);(out/(key+'.compile.log')).write_text(r.stdout+r.stderr);binaries[key]=(build/key).resolve()
 for_src=out/'source';for_src.mkdir(exist_ok=True);(for_src/pathlib.Path(src).name).write_bytes(pathlib.Path(src).read_bytes())
nodefile=os.getenv('PBS_NODEFILE');hosts=set(pathlib.Path(nodefile).read_text().split()) if nodefile else {'local'}
meta={'mode':a.mode,'local_smoke':a.local_smoke,'job':os.getenv('PBS_JOBID'),'hosts':sorted(hosts),'source_sha256':{s:hashlib.sha256(pathlib.Path(s).read_bytes()).hexdigest() for s in sources},'compile_commands':compile_commands,'binary_sha256':{k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in binaries.items()}}
if not a.local_smoke:
 hd=out/'hardware';hd.mkdir();probe="import pathlib,socket,subprocess,json,os,sys; pathlib.Path(sys.argv[1],socket.gethostname()+'.json').write_text(json.dumps({'host':socket.gethostname(),'lscpu':subprocess.check_output(['lscpu'],text=True),'meminfo':open('/proc/meminfo').read(),'allowed_cpus':sorted(os.sched_getaffinity(0))}))"
 subprocess.run(['mpirun','--map-by','ppr:1:node','--bind-to','none','-np',str(len(hosts)),'python3','-c',probe,str(hd.resolve())],check=True,timeout=90)
 meta['hardware']=[json.loads(f.read_text()) for f in hd.glob('*.json')];assert len(meta['hardware'])==len(hosts)
 for h in meta['hardware']:
  fields={line.split(':',1)[0].strip():line.split(':',1)[1].strip() for line in h['lscpu'].splitlines() if ':' in line}
  assert 'Platinum 8452Y' in fields['Model name'] and fields['Thread(s) per core']=='1'
  mem_kib=int(h['meminfo'].splitlines()[0].split()[1]);h['mem_total_kib']=mem_kib
  if a.mode not in ('optimize72',):assert 490*1024**2<mem_kib<530*1024**2,'Require nominal 512-GiB hosts'
 if a.mode in ('clean144','paired144'):assert not {h.lower() for h in hosts}&{'cn-011','cn-108','cn-084','cn-152','cn-039','gn-a40-047'},'Review must exclude all old 144 hosts'
 if a.mode in ('baseline','optimize72'):assert len(hosts)==1 and len(meta['hardware'][0]['allowed_cpus'])==72,'Requires an entire 72-core allocation'
(out/'metadata.json').write_text(json.dumps(meta,indent=2))
def launch(P,T):
 if a.local_smoke:return ['mpirun','--oversubscribe','--bind-to','none','-np',str(P)]
 assert P%len(hosts)==0
 return ['mpirun','--hostfile',nodefile,'--mca','ras','^tm','--mca','plm','rsh','--map-by',f'ppr:{P//len(hosts)}:node:PE={T}','--bind-to','core','--report-bindings']+sum([['-x',k] for k in ['OMP_NUM_THREADS','OMP_DYNAMIC','OMP_PLACES','OMP_PROC_BIND','PATH','LD_LIBRARY_PATH']],[])+['-np',str(P),'python3','b_mpi/exec_affinity.py']
baseline_cpu=None
if a.mode=='baseline' and not a.local_smoke:
 probe_env=dict(os.environ,OMP_NUM_THREADS='1',OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='close')
 probe=subprocess.run(launch(1,1)+[sys.executable,'-c','import os,json;print(json.dumps(sorted(os.sched_getaffinity(0))))'],env=probe_env,text=True,capture_output=True,check=True,timeout=60)
 cpus=json.loads(probe.stdout);assert len(cpus)==1;baseline_cpu=cpus[0];meta['reference_cpu']=baseline_cpu;(out/'metadata.json').write_text(json.dumps(meta,indent=2))
if a.mode=='links':
 cmd=launch(2,1)+[str(binaries['link'])];env=dict(os.environ,OMP_NUM_THREADS='1',OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='close');r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=240);(out/'link.stdout.json').write_text(r.stdout);(out/'link.stderr.txt').write_text(r.stderr);assert r.returncode==0;r=json.loads(r.stdout);assert len(set(r['hosts']))==2 or a.local_smoke;(out/'COMPLETE.json').write_text(json.dumps({'status':'PASS','local_smoke':a.local_smoke}));print('LINK_PROBE_PASS');raise SystemExit
G144=(6,6,4);G72=(6,4,3)
def cfg(id,n,P,T,g,binary='mpi',variant=None,diag=False):return dict(id=id,n=n,P=P,T=T,grid=g,binary=binary,variant=variant,diagnostic=diag)
configs=[]
if a.mode=='clean144':
 configs=[cfg('strong'+str(n),(n,n,n),144,1,G144) for n in [128,256,512]]+[cfg('weak64',(384,384,256),144,1,G144),cfg('axis144',(256,)*3,144,1,G144,'axis','baseline',True)]
elif a.mode=='suspect_diag':configs=[cfg('suspect_axis144',(256,)*3,144,1,G144,'axis','baseline',True)]
elif a.mode=='paired144':
 configs=[cfg('strong'+str(n),(n,n,n),144,1,G144) for n in [128,256,512]]+[cfg('weak64',(384,384,256),144,1,G144)]
 configs += [cfg(f'pair_{P}x{T}',(256,)*3,P,T,g,'hybrid') for P,T,g in [(24,6,(4,3,2)),(12,12,(3,2,2)),(4,36,(2,2,1))]]
 configs += [cfg('axis144',(256,)*3,144,1,G144,'axis','baseline',True)]
elif a.mode=='baseline':configs=[cfg(f'{key}_{n}',(n,)*3,1,1,(1,1,1),key) for n in [128,256] for key in ['mpi','serial']]
else:
 for P,T,g in [(72,1,G72),(12,6,(3,2,2)),(6,12,(3,2,1)),(2,36,(2,1,1))]:
  configs+=[cfg(f'original_{P}x{T}',(256,)*3,P,T,g,'mpi' if T==1 else 'hybrid')]
  for v in ['baseline','parallel_pack','first_touch','persistent','optimized']:configs.append(cfg(f'{v}_{P}x{T}',(256,)*3,P,T,g,'tuned',v))
 # Instrumented before/after comparisons on one predeclared layout, outside timing samples.
 configs += [cfg(f'axis_{v}_6x12',(256,)*3,6,12,(3,2,1),'tuned',v,True) for v in ['baseline','optimized']]
if a.local_smoke:configs=[cfg(c['id'],(7,7,7),2,2,(2,1,1),'tuned',c['variant'] or 'baseline',c['diagnostic']) for c in configs[:2]]
repeats=5 if a.mode=='baseline' else 3
numerics={}
for rep in [-1]+list(range(1 if a.local_smoke else repeats)):
 shift=rep%len(configs)
 for c in configs[shift:]+configs[:shift]:
  if c['diagnostic'] and rep!=0:continue
  prefix=out/f"{c['id']}_r{rep}";P,T=c['P'],c['T'];env=dict(os.environ,OMP_NUM_THREADS=str(T),OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='close')
  cmd=(['taskset','-c',str(baseline_cpu)] if baseline_cpu is not None else []) if c['binary']=='serial' else launch(P,T)
  cmd+=[str(binaries[c['binary']])]
  if c['binary']=='serial':cmd+=['--problem','poisson3d_mms','--max-iters',str(5 if a.local_smoke else 1000)]
  else:cmd+=['--iterations',str(5 if a.local_smoke else 1000),'--px',str(c['grid'][0]),'--py',str(c['grid'][1]),'--pz',str(c['grid'][2]),'--diagnostic',str(int(c['diagnostic']))]
  for k,v in zip(['nx','ny','nz'],c['n']):cmd+=['--'+k,str(v)]
  if c['variant']:cmd+=['--variant',c['variant']]
  pathlib.Path(str(prefix)+'.command.json').write_text(json.dumps({'argv':cmd,'config':c,'repeat':rep,'OMP':{k:v for k,v in env.items() if k.startswith('OMP_')}},indent=2))
  started=time.monotonic()
  with pathlib.Path(str(prefix)+'.stdout.json').open('w') as so,pathlib.Path(str(prefix)+'.stderr.txt').open('w') as se:r=subprocess.run(cmd,env=env,stdout=so,stderr=se,text=True,timeout=900)
  assert r.returncode==0,(c['id'],r.returncode);data=json.loads(pathlib.Path(str(prefix)+'.stdout.json').read_text())
  assert data['iterations']==(5 if a.local_smoke else 1000) and data['status']=='fixed_iterations' and data['boundary_error_inf']<=1e-12
  if c['binary']!='serial':assert data['ranks']==P and data['threads']==T and (data['nodes']==len(hosts) or a.local_smoke)
  assert all(math.isfinite(data[k]) for k in ['compute_seconds','relative_residual','residual_l2'])
  n=tuple(c['n']);old=numerics.setdefault(n,data['relative_residual']);assert abs(old-data['relative_residual'])<1e-10
  if c['diagnostic']:
   for t,axis in zip(data['rank_timings'],data['rank_axis_seconds']):assert math.isclose(t[3],sum(axis[:3]),abs_tol=1e-8,rel_tol=1e-8)
  pathlib.Path(str(prefix)+'.record.json').write_text(json.dumps({'config':c,'repeat':rep,'result':data,'process_returncode':0,'local_smoke':a.local_smoke,'wall_seconds':time.monotonic()-started},indent=2));print(c['id'],rep,data['compute_seconds'],flush=True)
(out/'COMPLETE.json').write_text(json.dumps({'status':'PASS','local_smoke':a.local_smoke}))
