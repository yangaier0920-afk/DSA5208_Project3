#!/usr/bin/env python3
"""Explicit cohort selection: preserve originals; never choose points by speed."""
import csv,json,pathlib,re,shutil,subprocess,sys
ROOT=pathlib.Path('.').resolve();RAW=ROOT/'results/final_202611/B_mpi';STD=ROOT/'results/final_202611/B_mpi_standardized';HYB=ROOT/'results/final_202611/B_mpi_hybrid_paired';REV=ROOT/'results/final_202611/B_mpi_review144'
source_jobs={1:1529163,8:1529168,12:1529166,36:1529210,72:1529288,144:1529165,288:1529289};new144=1529278
catalog=json.loads((RAW/'closeout_nodes_initial.json').read_text());memory={}
for _,v in catalog.items():
 a=v['resources_available'];host=a.get('host','').lower();t=a.get('mem','0b');n=float(re.match(r'[\d.]+',t)[0]);unit=re.sub(r'[\d.]','',t);memory[host]=memory.get(host,0)+n*{'mb':1,'kb':1/1024,'gb':1024,'b':1/1048576}.get(unit,0)
def folder(job):return RAW/f'Vanda_{job}.stdct-mgmt-02'
def view(src,dest,predicate):
 q=json.loads((src/'qstat_final.json').read_text());assert q['job_state']=='F' and q['Exit_status']==0,(src,q.get('Exit_status'))
 dest.mkdir(parents=True,exist_ok=True);shutil.copy2(src/'qstat_final.json',dest/'qstat_final.json');data=dest/'data';data.mkdir(exist_ok=True)
 for name in ('metadata.json','source.cpp','COMPLETE.json'):
  if (src/'data'/name).exists():shutil.copy2(src/'data'/name,data/name)
 for f in (src/'data').glob('*.record.json'):
  r=json.loads(f.read_text())
  if not predicate(r):continue
  prefix=f.name[:-len('.record.json')]
  for part in f.parent.glob(prefix+'.*'):shutil.copy2(part,data/part.name)
for p,j in source_jobs.items():
 src=folder(j);q=json.loads((src/'qstat_final.json').read_text());hosts={x.split('/')[0].lower() for x in q['exec_host'].split('+')}
 assert all(490000<memory[h]<530000 for h in hosts),(p,[(h,memory.get(h)) for h in hosts])
 view(src,STD/src.name,lambda r:r['config']['suite']!='hybrid')
for j in (1529164,new144):view(folder(j),HYB/folder(j).name,lambda r:r['config']['suite']=='hybrid' or (r['config']['suite']=='strong' and r['config']['n']==[256]*3))
view(folder(new144),REV/folder(new144).name,lambda r:r['config']['suite']=='diagnostic' or (r['config']['suite']=='strong' and r['config']['n']==[256]*3))
# Actual OS masks complement the MPI binding report for every newly measured sample.
affinity_samples=0
for j in (1529288,new144,1529289):
 data=folder(j)/'data';meta=json.loads((data/'metadata.json').read_text());allowed={r['host'].lower():set(r['allowed_cpus']) for r in meta['hardware']}
 for f in data.glob('*.record.json'):
  r=json.loads(f.read_text());log=pathlib.Path(str(f).replace('.record.json','.stderr.txt')).read_text();records=[]
  for line in log.splitlines():
   if 'AFFINITY_JSON ' in line:records.append(json.loads(line.split('AFFINITY_JSON ',1)[1]))
  assert {x['rank'] for x in records}==set(range(r['result']['ranks'])),f
  occupied=set()
  for x in records:
   host=x['host'].lower();cpus=set(x['cpus']);assert len(cpus)==r['result']['threads'] and cpus<=allowed[host]
   keys={(host,c) for c in cpus};assert not occupied&keys;occupied|=keys
  assert len(occupied)==r['result']['ranks']*r['result']['threads'];affinity_samples+=1
for input_root,out in ((STD,STD/'analysis'),(HYB,HYB/'analysis'),(REV,ROOT/'closeout/review144')):
 subprocess.run([sys.executable,'b_mpi/analyze_b.py','--input',str(input_root),'--out',str(out)],check=True,stdout=subprocess.DEVNULL)
def read(p):return list(csv.DictReader(p.open()))
scaling=read(STD/'analysis/summary.csv');h=read(HYB/'analysis/summary.csv');assert len(scaling)==20 and len(h)==8
for r in h:
 C=int(r['cores']);baseline=next(x for x in h if int(x['cores'])==C and x['suite']=='strong');r['paired_baseline_seconds']=baseline['median'];r['speedup']=str(float(baseline['median'])/float(r['median']));r['efficiency']='';r['cohort']='paired_72_original_single_host' if C==72 else 'paired_144_review_four_hosts';r['baseline']=r['cohort']
for r in scaling:r['paired_baseline_seconds']='';r['cohort']='standard_memory_scaling'
rows=scaling+[r for r in h if r['suite']=='hybrid'];assert len(rows)==26
fields=list(rows[0])
def write(p,rs):
 with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rs)
legacy=ROOT/'results/final_202611/B_mpi_legacy_analysis_20261107'
if not legacy.exists():shutil.copytree(RAW/'analysis',legacy)
write(RAW/'analysis/summary.csv',rows);write(ROOT/'closeout/hybrid_summary.csv',h);write(RAW/'analysis/hybrid_summary.csv',h)
shutil.copy2(STD/'analysis/diagnostics.csv',RAW/'analysis/diagnostics.csv')
audit=json.loads((STD/'analysis/audit.json').read_text());audit.update(core_complete=True,formal_configurations=26,missing_core=[],hardware_scope='Scaling: matched CPU topology and nominal 512-GB capacity family. Hybrid: paired baselines within explicitly separate allocations; 72-core hybrid remains a 1-TB single-node cohort.',cohort_selection='closeout/prepare_cohorts.py',supplementary_os_affinity_samples=affinity_samples,paired_baseline_configurations=2,paired_baseline_formal_samples=6,reported_cohort_configurations=28,reported_formal_samples=84)
(RAW/'analysis/audit.json').write_text(json.dumps(audit,indent=2))
from_cpu=[{'P':p,'job':j,'hosts':sorted({x.split('/')[0] for x in json.loads((folder(j)/'qstat_final.json').read_text())['exec_host'].split('+')})} for p,j in source_jobs.items()]
completion={'standardized_scaling':True,'main_configs':26,'main_formal_samples':78,'paired_baseline_configs':2,'paired_baseline_formal_samples':6,'reported_formal_samples':84,'diagnostics':3,'independent_review_job':new144,'original_144_samples_retained':True,'affinity_samples_verified':affinity_samples,'scaling_sources':from_cpu,'hybrid_sources':[1529164,new144],'author_information':'intentionally omitted at user request'}
(ROOT/'closeout/completion.json').write_text(json.dumps(completion,indent=2));print(json.dumps(completion,indent=2))
