#!/usr/bin/env python3
"""Audit completed cluster results; never select measurements by speed."""
import argparse,collections,csv,json,math,pathlib,statistics
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();root=pathlib.Path(a.input);out=pathlib.Path(a.out);out.mkdir(parents=True,exist_ok=True)
groups=collections.defaultdict(list);axis=[];links=[];seen_jobs=set()
for meta_file in root.rglob('metadata.json'):
 data_dir=meta_file.parent;meta=json.loads(meta_file.read_text())
 if meta.get('local_smoke'):continue
 done=data_dir/'COMPLETE.json';qstat=data_dir.parent/'qstat_final.json'
 if not done.exists() or not qstat.exists():continue
 q=json.loads(qstat.read_text())
 if q.get('job_state')!='F' or q.get('Exit_status')!=0:continue
 mode=meta['mode'];seen_jobs.add(meta['job'])
 if mode=='links':
  result=json.loads((data_dir/'link.stdout.json').read_text());assert len(set(result['hosts']))==2
  by_size=collections.defaultdict(list)
  for row in result['measurements']:by_size[row['bytes']].append(row['round_trip_seconds'])
  for size,values in by_size.items():
   assert len(values)==3 and all(math.isfinite(v) and v>0 for v in values)
   links.append(dict(job=meta['job'],hosts=' / '.join(result['hosts']),bytes=size,median_rtt_seconds=statistics.median(values),minimum=min(values),maximum=max(values)))
  continue
 for record in data_dir.glob('*.record.json'):
  r=json.loads(record.read_text());c=r['config'];v=r['result'];raw=json.loads(pathlib.Path(str(record).replace('.record.json','.stdout.json')).read_text());assert raw==v and r['process_returncode']==0
  assert v['iterations']==1000 and v['status']=='fixed_iterations' and v['boundary_error_inf']<=1e-12
  assert [v[k] for k in ['nx','ny','nz']]==c['n'] and all(math.isfinite(v[k]) for k in ['compute_seconds','relative_residual'])
  if c['binary']!='serial':
   log=pathlib.Path(str(record).replace('.record.json','.stderr.txt')).read_text();masks=[]
   for line in log.splitlines():
    if 'AFFINITY_JSON ' in line:masks.append(json.JSONDecoder().raw_decode(line.split('AFFINITY_JSON ',1)[1])[0])
   assert {m['rank'] for m in masks}==set(range(c['P']))
   allowed={h['host'].lower():set(h['allowed_cpus']) for h in meta['hardware']};used=set()
   for m in masks:
    host=m['host'].lower();mask=set(m['cpus']);assert len(mask)==c['T'] and mask<=allowed[host];keys={(host,x) for x in mask};assert not used&keys;used|=keys
  if c['diagnostic']:
   names=v['rank_hosts'];topology=v['rank_topology'];slow=max(range(c['P']),key=lambda j:v['rank_timings'][j][0])
   for rank,(timing,t,xyz) in enumerate(zip(v['rank_timings'],topology,v['rank_axis_seconds'])):
    assert math.isclose(timing[3],sum(xyz[:3]),rel_tol=1e-8,abs_tol=1e-8)
    for d,label in enumerate(['x','y','z']):
     lo,hi=t[3+2*d:5+2*d];axis.append(dict(job=meta['job'],mode=mode,case=c['id'],rank=rank,host=names[rank],axis=label,low_neighbor=lo,high_neighbor=hi,low_host=names[lo] if lo>=0 else 'boundary',high_host=names[hi] if hi>=0 else 'boundary',communication_wait_seconds=xyz[d],pack_unpack_seconds=xyz[d+3],rank_total_seconds=timing[0],is_slowest_rank=int(rank==slow)))
   continue
  if r['repeat']>=0:groups[(meta['job'],mode,c['id'])].append(r)
summary=[]
for (job,mode,id),samples in groups.items():
 reps=5 if mode=='baseline' else 3
 assert sorted(r['repeat'] for r in samples)==list(range(reps)),(job,id,'missing/duplicate repeats')
 times=[r['result']['compute_seconds'] for r in samples];res=[r['result']['relative_residual'] for r in samples];assert max(res)-min(res)<1e-10
 c=samples[0]['config'];m=statistics.median(times);spread=(max(times)-min(times))/m;deviation=max(abs(x/m-1) for x in times)
 summary.append(dict(job=job,mode=mode,case=id,nx=c['n'][0],ny=c['n'][1],nz=c['n'][2],P=c['P'],T=c['T'],binary=c['binary'],variant=c['variant'] or 'original',samples=reps,median=m,minimum=min(times),maximum=max(times),range_over_median_pct=100*spread,max_deviation_pct=100*deviation,baseline_five_percent_target_met=(deviation<.05) if mode=='baseline' else '',relative_residual=statistics.median(res)))
def write(name,rows):
 if not rows:return
 with (out/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
write('summary.csv',summary);write('axis_rank_pairs.csv',axis);write('link_round_trips.csv',links)
# An axis aggregates two Sendrecv calls involving both neighbors; do not claim
# it uniquely isolates a specific directional network link.
write('slowest_rank_axes.csv',[r for r in axis if r['is_slowest_rank']])
(out/'audit.json').write_text(json.dumps({'accepted_jobs':sorted(seen_jobs),'performance_configurations':len(summary),'axis_rows':len(axis),'link_measurements':len(links),'speed_filter_applied':False},indent=2));print(json.dumps({'configurations':len(summary),'axis_rows':len(axis),'links':len(links)}))
