#!/usr/bin/env python3
"""Only audited complete formal groups enter plots. Local smoke is excluded."""
import argparse,csv,hashlib,json,math,pathlib,re,statistics
from run_b import matrix
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);args=p.parse_args();root=pathlib.Path(args.input);out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
groups={};diags=[];signatures=set();source_signatures=set();numerics={};warnings=[];interrupted=set()
for f in root.rglob('*.record.json'):
 r=json.loads(f.read_text())
 if r['local'] or r.get('smoke') or r['repeat']<0:continue
 qstat=f.parent.parent/'qstat_final.json'
 if not qstat.exists():continue
 scheduler=json.loads(qstat.read_text())
 if scheduler.get('job_state')!='F' or scheduler.get('Exit_status') not in (0,1):continue
 if scheduler.get('Exit_status')==1:interrupted.add(f.parent.parent.name)
 meta=json.loads((f.parent/'metadata.json').read_text())
 source_signatures.add(meta['source_sha256'])
 if hashlib.sha256((f.parent/'source.cpp').read_bytes()).hexdigest()!=meta['source_sha256']:raise RuntimeError('source snapshot hash mismatch')
 raw=json.loads(pathlib.Path(str(f).replace('.record.json','.stdout.json')).read_text())
 if raw!=r['result']:raise RuntimeError('raw JSON and analysis record mismatch')
 if raw['status']!='fixed_iterations' or raw['boundary_error_inf']>1e-12:raise RuntimeError('numerical acceptance failed')
 if not all(math.isfinite(raw[k]) for k in ('compute_seconds','residual_l2','relative_residual','discrete_error_inf')):raise RuntimeError('nonfinite metric')
 if raw['ranks']!=r['config']['p'] or raw['threads']!=r['config']['t']:raise RuntimeError('resource mismatch')
 if [raw[k] for k in ('nx','ny','nz')]!=r['config']['n']:raise RuntimeError('mesh mismatch')
 allocated_hosts={x.split('/')[0] for x in scheduler.get('exec_host','').split('+')}
 if raw['nodes']!=len(allocated_hosts):raise RuntimeError('actual node count differs from PBS')
 signature=tuple(':'.join(part.strip() for part in line.split(':',1)) for line in meta.get('hardware_signature',[]))
 if not signature:raise RuntimeError(str(f)+': missing hardware signature')
 signatures.add(signature)
 log=pathlib.Path(str(f).replace('.record.json','.stderr.txt')).read_text()
 bound={int(x) for x in re.findall(r'MCW rank (\d+) bound to',log)}
 full_allocation=re.findall(r'\[([^\]:]+):\d+\].*MCW rank (\d+) is not bound \(or bound to all available processors\)',log)
 if full_allocation:
  assert raw['ranks']==raw['nodes'] and int(scheduler['Resource_List']['ncpus'])==raw['ranks']*raw['threads'], 'unbound ranks do not cover exactly one complete host allocation'
  assert len({h for h,_ in full_allocation})==len(full_allocation)
  bound.update(int(x) for _,x in full_allocation)
 if bound!=set(range(r['result']['ranks'])):raise RuntimeError(str(f)+': incomplete CPU binding evidence')
 occupied=set()
 for line in log.splitlines():
  m=re.search(r'\[([^\]:]+):\d+\].*MCW rank (\d+) bound to (.*)',line)
  if not m:continue
  host,rank_text,description=m.groups();parts=re.split(r'socket (\d+)\[',description);mask=set()
  for i in range(1,len(parts),2):
   mask.update((host,int(parts[i]),int(core)) for core in re.findall(r'core (\d+)\[hwt',parts[i+1]))
  if len(mask)!=raw['threads'] or occupied.intersection(mask):raise RuntimeError(str(f)+': overlapping or incorrect core masks')
  occupied.update(mask)
 if len(occupied)+len(full_allocation)*raw['threads']!=raw['ranks']*raw['threads']:raise RuntimeError(str(f)+': incomplete physical-core mask audit')
 nkey=tuple(r['config']['n'])
 numerics.setdefault(nkey,[]).append(r['result']['relative_residual'])
 if r['result']['iterations']!=1000:continue
 if r['config']['diagnostic']:diags.append(r);continue
 groups.setdefault(r['config']['id'],[]).append(r)
if len(source_signatures)>1:raise RuntimeError('different solver sources; separate source versions')
if len(signatures)>1:raise RuntimeError('mixed CPU models/topology; separate hardware groups before analysis')
for n,values in numerics.items():
 if max(values)-min(values)>1e-9*max(1,max(values)):raise RuntimeError(str(n)+': cross-layout residual mismatch')
rows=[]
for key,recs in groups.items():
 if len(recs)!=3 or {r['repeat'] for r in recs}!={0,1,2}:warnings.append(key+': incomplete/duplicate repeats');continue
 c=recs[0]['config'];vals=[r['result']['compute_seconds'] for r in recs];residuals=[r['result']['relative_residual'] for r in recs]
 if max(residuals)-min(residuals)>1e-10*max(1,max(residuals)):raise RuntimeError(key+': residual mismatch')
 rows.append(dict(id=key,suite=c['suite'],nx=c['n'][0],ny=c['n'][1],nz=c['n'][2],P=c['p'],T=c['t'],cores=c['cores'],nodes=recs[0]['result']['nodes'],grid='x'.join(map(str,c['grid'])),K=1000,median=statistics.median(vals),minimum=min(vals),maximum=max(vals),relative_residual=statistics.median(residuals)))
lookup={(r['suite'],r['nx'],r['P']):r for r in rows}
for r in rows:
 r.update(speedup='',efficiency='',baseline='')
 if r['suite']=='strong':
  basep=72 if r['nx']==512 else 1;b=lookup.get(('strong',r['nx'],basep))
  if b:r.update(speedup=b['median']/r['median'],efficiency=b['median']/r['median']/(r['P']/basep),baseline=f'MPI P={basep}')
 elif r['suite']=='weak':
  b=next((x for x in rows if x['suite']=='weak' and x['P']==1),None)
  if b:r.update(efficiency=b['median']/r['median'],baseline='weak P=1')
 else:
  b=lookup.get(('strong',256,r['cores']))
  if b:r.update(speedup=b['median']/r['median'],baseline=f'pure MPI P={r["cores"]}; layout improvement')
if rows:
 with (out/'summary.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
from plot_b import plot_rows
warnings.extend(plot_rows(rows,out))
diagrows=[]
for r in diags:
 times=r['result']['rank_timings'];slow=max(range(len(times)),key=lambda i:times[i][0]);t=times[slow]
 diagrows.append(dict(P=r['config']['p'],slowest_rank=slow,total=t[0],update=t[1],pack_unpack=t[2],communication_wait=t[3],swap=t[4],uninstrumented=t[0]-sum(t[1:]),min_rank_total=min(x[0] for x in times),max_rank_total=max(x[0] for x in times)))
if diagrows:
 with (out/'diagnostics.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(diagrows[0]));w.writeheader();w.writerows(diagrows)
expected_core={r['id'] for r in matrix() if not r['diagnostic'] and r['cores']<=288}
expected_optional={r['id'] for r in matrix() if not r['diagnostic'] and r['cores']>288}
actual={r['id'] for r in rows}
missing_core=sorted(expected_core-actual)
missing_diagnostics=sorted({72,144,288}-{int(r['P']) for r in diagrows})
audit=dict(formal_configurations=len(rows),diagnostics=len(diagrows),core_complete=not missing_core and not missing_diagnostics,hardware_scope='CPU model and topology matched; physical RAM capacity, node count and shared-node load vary. Scaling is qualified accordingly.',missing_core=missing_core,missing_diagnostics=missing_diagnostics,missing_optional=sorted(expected_optional-actual),retained_from_interrupted_jobs=sorted(interrupted),warnings=warnings)
(out/'audit.json').write_text(json.dumps(audit,indent=2))
print(json.dumps(audit))
