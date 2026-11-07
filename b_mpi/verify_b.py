#!/usr/bin/env python3
"""Mathematical oracle, partition invariance, and halo/threads checks."""
import argparse,csv,json,math,os,pathlib,shlex,subprocess
p=argparse.ArgumentParser();p.add_argument('--binary',default='b_mpi/jacobi_cart_hybrid');p.add_argument('--launcher',default='mpirun --oversubscribe --bind-to none');p.add_argument('--expected-nodes',type=int,default=0);p.add_argument('--out',required=True);args=p.parse_args()
out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=False)
cases=[('3d_single',3,(7,7,7),(1,1,1),1,1000),('3d_faces',3,(7,7,7),(2,2,2),1,1000),('3d_uneven_hybrid',3,(9,7,5),(2,2,2),2,1000),('2d_rhs_hybrid',2,(7,7,1),(2,1,1),2,1000),('thin_3d',3,(2,3,2),(2,1,2),1,1000),('one_step',3,(9,7,5),(2,2,2),2,1)]
records=[]
for name,d,n,g,t,k in cases:
 prefix=out/name;cmd=shlex.split(args.launcher)+['-np',str(math.prod(g)),args.binary,'--dim',str(d),'--iterations',str(k),'--grid',str(prefix)]
 for key,value in zip(('nx','ny','nz','px','py','pz'),n+g):cmd+=['--'+key,str(value)]
 env=dict(os.environ,OMP_NUM_THREADS=str(t),OMP_DYNAMIC='FALSE',OMP_PROC_BIND='FALSE')
 run=subprocess.run(cmd,text=True,capture_output=True,env=env,timeout=180)
 (out/(name+'.stdout.json')).write_text(run.stdout);(out/(name+'.stderr.txt')).write_text(run.stderr)
 if run.returncode:raise RuntimeError(f'{name}: {run.stderr}')
 data=json.loads(run.stdout)
 if args.expected_nodes and math.prod(g)>=8:assert data['nodes']==args.expected_nodes,(name,data['nodes'],args.expected_nodes)
 assert data['threads']==t and data['ranks']==math.prod(g)
 vals={}
 for file in out.glob(name+'.rank*.csv'):
  for row in csv.DictReader(file.open()):
   q=tuple(int(row[x]) for x in ('i','j','k'));assert q not in vals;vals[q]=float(row['u'])
 assert len(vals)==math.prod(n)
 h=[1/(n[i]+1) for i in range(d)];a=[1/x**2 for x in h];coef=(14 if d==3 else 5)*math.pi**2
 lam=sum(4*a[i]*math.sin((i+1)*math.pi*h[i]/2)**2 for i in range(d))
 def lin(q):return sum((i+1)*q[i]*h[i] for i in range(d))
 def wav(q):return math.prod(math.sin((i+1)*math.pi*q[i]*h[i]) for i in range(d))
 error=0
 for q,value in vals.items():
  if k==1000:expected=lin(q)+coef/lam*wav(q)
  else:
   nb=0
   for axis in range(d):
    for sign in (-1,1):
     v=list(q);v[axis]+=sign
     if v[axis] in (0,n[axis]+1):nb+=a[axis]*lin(v)
   expected=(nb+coef*wav(q))/(2*sum(a))
  error=max(error,abs(value-expected))
 assert error<=1e-9,(name,error)
 assert abs(error-data['discrete_error_inf'])<1e-12 if k==1000 else True
 assert data['boundary_error_inf']<=1e-12 and data['status']=='fixed_iterations'
 records.append(dict(case=name,oracle_error_inf=error,command=cmd,result=data))
(out/'summary.json').write_text(json.dumps(dict(status='PASS',cases=records),indent=2))
print(json.dumps({'status':'PASS','cases':len(records),'max_oracle_error':max(r['oracle_error_inf'] for r in records)}))
