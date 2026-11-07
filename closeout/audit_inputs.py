import csv,json,math,pathlib,sys,statistics,hashlib
sys.path.insert(0,'c_openmp');from analyze_c import summarize
root=pathlib.Path('.');out=pathlib.Path('closeout');out.mkdir(exist_ok=True)
b=root/'c_openmp/deliverables/formal_20261106';rows=list(csv.DictReader((b/'samples.csv').open()));stats=summarize(rows);saved=list(csv.DictReader((b/'analysis/summary.csv').open()))
assert len(rows)==36 and len(stats)==12 and sum(int(r['warmup'])==0 for r in rows)==27
for computed,stored in zip(stats,saved):
 for k in ('median','minimum','maximum'):assert math.isclose(computed[k],float(stored[k]),rel_tol=1e-12)
for r in rows:
 assert int(r['iterations'])==1000 and float(r['boundary_error_inf'])<=1e-12
 if r['backend']=='gpu':assert r['gpu_verified'].lower()=='true' and r['target_is_initial_device'].lower()=='false' and int(r['num_devices'])>=1
 else:assert int(r['actual_threads'])==int(r['requested_threads'])
for n in (64,128,256):
 vals=[float(r['relative_residual']) for r in rows if int(r['nx'])==n];assert max(vals)-min(vals)<1e-10
A=root/'a_scaling_20261104/Vanda_1522376.stdct-mgmt-02/data';summary=list(csv.DictReader((A/'summary.csv').open()));samples=list(csv.DictReader((A/'samples.csv').open()));assert len(summary)==10 and len(samples)==40
for row in summary:
 n=int(row['n']);g=[r for r in samples if r['problem_id']==row['problem_id'] and int(r['nx'])==n and int(r['warmup'])==0]
 assert sorted(int(r['repeat']) for r in g)==[1,2,3]
 vals=[float(r['compute_seconds']) for r in g]
 for key,value in [('median_seconds',statistics.median(vals)),('min_seconds',min(vals)),('max_seconds',max(vals))]:assert math.isclose(float(row[key]),value,rel_tol=1e-12)
 assert all(int(r['iterations'])==1000 and float(r['boundary_error_inf'])<=1e-12 for r in g)
 assert math.isclose(float(row['seconds_per_point_update']),statistics.median(vals)/(1000*int(row['N'])),rel_tol=1e-12)
env=json.loads((A/'environment.json').read_text())
assert hashlib.sha256((root/'a_scaling_20261104/jacobi_a_scaling.cpp').read_bytes()).hexdigest()==env['sha256']['jacobi_a_scaling.cpp']
record={'A_serial_configs':len(summary),'A_serial_calls':len(samples),'A_summary_recalculation':'PASS','A_formal_source_hash':'PASS','C_performance_calls':len(rows),'C_formal_samples':27,'C_device_evidence':'all GPU samples verified actual offload','C_summary_recalculation':'PASS','author_identification':'omitted at user request','personal_contributions':'not asserted'}
(out/'input_audit.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
