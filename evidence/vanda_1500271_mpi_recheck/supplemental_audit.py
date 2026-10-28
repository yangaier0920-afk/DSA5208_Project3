import json, math, hashlib, runpy, re, shutil, statistics, tarfile
from collections import Counter
from pathlib import Path

root=Path('results/Vanda_mpi_recheck_1500271.stdct-mgmt-02')
out=Path('evidence/vanda_1500271_mpi_recheck')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
b=read(root/'benchmark/summary.json'); v=read(root/'validation/summary.json')
config=read(root/'sources/team_contract_v0.1.json')
helpers=runpy.run_path(str(root/'sources/prepare_team_references.py'))
cases=config['validation']['cases']+[
 dict(id='one_row_per_rank',n=4,max_iters=2,tolerance=0,expected_exit_code=0,expected_status='fixed_iterations'),
 dict(id='three_rows_per_rank',n=12,max_iters=17,tolerance=0,expected_exit_code=0,expected_status='fixed_iterations')]
fields=('max_update','max_error','residual_inf','boundary_error')
numerical=invalid=affinity=0
serials={r['id']:r['result'] for r in v['runs'] if 'result' in r and r['result']['mode']=='serial'}
for r in v['runs']:
 if 'result' not in r:
  assert r['exit_code']!=0 and not (root/'validation'/(r['id']+'.stdout.json')).read_text(encoding='utf-8').strip()
  invalid+=1; continue
 case=next(c for c in cases if r['id'].startswith(c['id']+'_'))
 d=r['result']; numerical+=1
 assert r['exit_code']==case['expected_exit_code']
 assert d['n']==case['n'] and d['tolerance']==case['tolerance']
 assert d['threads']==r['threads']==1
 assert all(math.isfinite(d[f]) and d[f]>=0 for f in fields+('compute_seconds',))
 helpers['validate'](dict(r),case,config['validation'])
 if d['mode']=='mpi':
  assert d['mpi_processes']==r['processes'] and d['exchange'] in ('sendrecv','overlap') and d['nodes']==1
  for f in fields: assert math.isclose(d[f],serials[case['id']+'_serial'][f],rel_tol=1e-10,abs_tol=1e-12),(r['id'],f)
 else: assert d['mode']=='serial' and r['processes']==1
assert b['job_id']==v['job_id']=='1500271.stdct-mgmt-02'
assert b['host']==v['host']=='IN-003'
assert b['status']==v['status']=='PASS'
assert b['serial_source']=='jacobi_serial_row_update.cpp'
assert len(v['runs'])==92 and len(b['runs'])==90
assert len(set(r['id'] for r in v['runs']))==92
assert len(set(r['id'] for r in b['runs']))==90
for section, summary in [('benchmark',b),('validation',v)]:
 expected_files={'summary.json','summary.csv'} if section=='benchmark' else {'summary.json'}
 for r in summary['runs']:
  for suffix in ['.stdout.json','.stderr.txt']:
   expected_files.add(r['id']+suffix)
   assert (root/section/(r['id']+suffix)).is_file()
  raw=(root/section/(r['id']+'.stdout.json')).read_text(encoding='utf-8')
  assert (json.loads(raw)==r['result']) if 'result' in r else not raw.strip()
 assert {p.name for p in (root/section).iterdir()}==expected_files
qstat=(root/'qstat_full.txt').read_text(encoding='utf-8')
assert qstat.startswith('Job Id: 1500271.stdct-mgmt-02')
for pattern in [r'job_state = F',r'Exit_status = 0',r'Resource_List.nodect = 1',r'Resource_List.ncpus = 12',r'Resource_List.mem = 4gb',r'resources_used.walltime = 00:05:23',r'exec_host = IN-003/']:
 assert re.search(pattern,qstat),pattern
log=(root/'run.log').read_text(encoding='utf-8')
assert log.rstrip().endswith('RUN_STATUS=PASSED\nJOB_EXIT_STATUS=0')
assert len((root/'pbs_nodefile.txt').read_text().splitlines())==12
assert 'Xeon(R) Gold 6438N' in (root/'lscpu.txt').read_text()
expected_ids={c['id']+'_serial' for c in cases}
expected_ids.update(f"{c['id']}_mpi_p{p}_t1_{e}" for c in cases for p in [1,2,4,12] if p<=c['n'] for e in ['sendrecv','overlap'])
expected_ids.update(['mpi_too_many_ranks','mpi_negative_tolerance','mpi_nan_tolerance','mpi_bad_exchange'])
assert Counter(r['id'] for r in v['runs'])==Counter(expected_ids)
assert (numerical,invalid)==(88,4)
grid_runs=[r for r in v['runs'] if 'grid' in r.get('result',{})]
assert len(grid_runs)==43
assert sum(r.get('result',{}).get('status')=='update_tolerance_reached' for r in v['runs'])==27
for name,sha in v['sha256'].items():
 assert hashlib.sha256((root/'sources'/name).read_bytes()).hexdigest()==sha

assert (b['n'],b['iterations'],b['tolerance'],b['order'],b['repeats'],b['warmups'])==(1024,1000,0,'interleaved',9,1)
cpus=b['pin_cpus']; assert len(set(cpus))==len(cpus)==b['allocated_cpus']==12
status=(root/'process_status.txt').read_text(encoding='utf-8')
mask=re.search(r'Cpus_allowed_list:\s*(.+)',status).group(1).strip()
def expand(s):
 values=[]
 for part in s.split(','):
  limits=list(map(int,part.split('-'))); values.extend(range(limits[0],limits[-1]+1))
 return values
assert set(expand(mask))==set(cpus),(mask,cpus)
for mode,digest in b['executable_sha256'].items():
 assert hashlib.sha256((root/'bin'/('jacobi_'+mode)).read_bytes()).hexdigest()==digest
 assert v['executable_sha256'][mode]==digest
for name,digest in b['source_sha256'].items(): assert hashlib.sha256((root/'sources'/name).read_bytes()).hexdigest()==digest
reference=next(r['result'] for r in b['runs'] if r['result']['mode']=='serial')
trials=[(g['mode'],g['processes'],g['threads'],g['exchange']) for g in b['groups']]
assert len(set(trials))==9
for index,r in enumerate(b['runs']):
 d=r['result']; m=d['mode']; p=d.get('mpi_processes',1); t=d['threads']; e=d.get('exchange','none')
 key=(m,p,t,e)
 assert d['n']==1024 and d['iterations']==1000 and d['tolerance']==0 and d['status']=='fixed_iterations'
 assert m in ('mpi','serial') and t==1 and r['exit_code']==0
 assert d.get('nodes',1)==1
 assert all(math.isfinite(d[f]) and d[f]>=0 for f in fields+('compute_seconds',))
 for f in fields: assert math.isclose(d[f],reference[f],rel_tol=1e-10,abs_tol=1e-12),(r['id'],f)
 actual=[json.loads(line.removeprefix('AB_AFFINITY ')) for line in (root/'benchmark'/(r['id']+'.stderr.txt')).read_text(encoding='utf-8').splitlines() if line.startswith('AB_AFFINITY ')]
 actual.sort(key=lambda x:x['rank'])
 assert actual==r['affinity_before_exec'] and len(actual)==p
 assert [x['rank'] for x in actual]==list(range(p))
 for a in actual: assert a['host']==b['host'] and a['cpus']==[cpus[a['rank']]]
 affinity+=len(actual)
 round_index=index//9-1; pos=index%9
 assert r['repeat_index']==round_index and r['warmup']==(round_index<0)
 expected=trials if round_index<0 else trials[round_index:]+trials[:round_index]
 assert key==expected[pos],(index,key,expected[pos])
assert affinity==390
assert trials==[('serial',1,1,'none')]+[('mpi',p,1,e) for p in [1,2,4,12] for e in ['sendrecv','overlap']]
for r in b['runs']:
 command=r['command']; d=r['result']
 assert command[command.index('--cpus')+1]==','.join(map(str,cpus))
 if d['mode']=='mpi':
  assert command[command.index('-np')+1]==str(d['mpi_processes'])
  assert command[command.index('--bind-to')+1]=='none'
  assert command[-5:]==['1024','1000','0','--exchange',d['exchange']]
 else:
  assert command[-3:]==['1024','1000','0']
 assert d['boundary_error']==0
numa1=re.search(r'NUMA node1 CPU\(s\):\s*(.+)',(root/'lscpu.txt').read_text()).group(1).strip()
assert set(cpus)<=set(expand(numa1))
for key in trials:
 positions=[i%9 for i,r in enumerate(b['runs']) if not r['warmup'] and (r['result']['mode'],r['result'].get('mpi_processes',1),r['result']['threads'],r['result'].get('exchange','none'))==key]
 assert Counter(positions)==Counter(range(9))
oldroot=Path('results/Vanda_mpi_recheck_1499881.stdct-mgmt-02')
source_matches={p.name:hashlib.sha256(p.read_bytes()).hexdigest()==hashlib.sha256((oldroot/'sources'/p.name).read_bytes()).hexdigest() for p in (root/'sources').iterdir() if p.is_file()}
assert all(source_matches.values()),source_matches
other=Path('results/Vanda_mpi_recheck_1500222.stdct-mgmt-02')
assert {p.name for p in (root/'sources').iterdir()}=={p.name for p in (other/'sources').iterdir()}
assert all(hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((other/'sources'/p.name).read_bytes()).digest() for p in (root/'sources').iterdir() if p.is_file())
archive=Path('results/raw_archives')/(root.name+'.tar.gz')
assert not archive.exists()
with tarfile.open(archive,'w:gz') as tar: tar.add(root,arcname=root.name)
with tarfile.open(archive,'r:gz') as tar:
 files={root.name+'/'+p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
 members={m.name:m for m in tar.getmembers() if m.isfile()}
 assert members.keys()==files.keys()
 for name,p in files.items(): assert hashlib.sha256(tar.extractfile(members[name]).read()).digest()==hashlib.sha256(p.read_bytes()).digest()
digest=hashlib.sha256(archive.read_bytes()).hexdigest()
for name in ['qstat_full.txt','run.log','metadata.txt','lscpu.txt','source_sha256.txt','executable_sha256.txt','process_status.txt','pbs_nodefile.txt']:
 shutil.copy2(root/name,out/name)
shutil.copy2(root/'benchmark/summary.json',out/'benchmark_summary.json')
shutil.copy2(root/'validation/summary.json',out/'validation_summary.json')
audit=read(out/'audit.json')
audit.update(numerical_validation_executions_rechecked=numerical,invalid_input_rejections_rechecked=invalid,benchmark_workload_metrics_rechecked=len(b['runs']),rank_affinity_records_rechecked=affinity,balanced_interleaved_order_checked=True,inherited_cpu_mask_checked=True,host=b['host'],pin_cpus=cpus,serial_source=b['serial_source'],source_files_identical_to_1499881=source_matches,raw_archive=archive.as_posix(),raw_archive_sha256=digest,raw_archive_contents_rechecked=True)
audit.update(independent_full_grid_executions_rechecked=43,converged_validation_executions_rechecked=27,validation_case_matrix_complete=True,raw_output_inventory_complete=True,affinity_scope='before exec; not continuous sampling',numa_nodes=[1],source_files_identical_to_1500222=True,raw_archive_files=len(files))
(out/'audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
print(json.dumps(audit,indent=2,ensure_ascii=False))

shutil.copy2(__file__,out/'supplemental_audit.py')
