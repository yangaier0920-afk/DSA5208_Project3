import csv,hashlib,json,pathlib,subprocess,tempfile,zipfile
ROOT=pathlib.Path('.').resolve();target=ROOT/'output/DSA5208_Project3_Review_Package.zip';checks=[]
with tempfile.TemporaryDirectory(prefix='dsa5208_review_check_') as temp:
 temp=pathlib.Path(temp)
 with zipfile.ZipFile(target) as z:
  assert z.testzip() is None;z.extractall(temp)
  manifest=json.loads(z.read('SUBMISSION_MANIFEST.json'))
  for row in manifest['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
 checks.append('ZIP integrity and all source/input manifest hashes PASS')
 flags='-Xpreprocessor -fopenmp -I/opt/homebrew/opt/libomp/include -L/opt/homebrew/opt/libomp/lib -lomp'
 def run(cmd):
  p=subprocess.run(cmd,cwd=temp,capture_output=True,text=True,timeout=180)
  assert p.returncode==0,(cmd,p.stdout[-1000:],p.stderr[-2000:]);return p.stdout
 run(['make','all','OMPFLAGS='+flags]);checks.append('All serial/MPI/hybrid/CPU sources compile from the standalone ZIP on this Mac')
 for cmd in [ ['build/jacobi_numerics','--problem','poisson3d_mms','--nx','7','--max-iters','1000'],['build/jacobi_a_scaling','--problem','poisson2d_mms','--nx','7','--max-iters','1000'] ]:
  r=json.loads(run(cmd));assert r['discrete_error_inf']<1e-9 and r['boundary_error_inf']<=1e-12
 checks.append('Packaged A 2D/3D discrete-solution examples PASS')
 run(['python3','b_mpi/verify_b.py','--binary','build/jacobi_cart_hybrid','--launcher','mpirun --oversubscribe --bind-to none','--out','verify_b'])
 assert json.loads((temp/'verify_b/summary.json').read_text())['status']=='PASS';checks.append('Packaged B six mathematical/partition/thread checks PASS (local correctness only)')
 run(['python3','c_openmp/run_c.py','--binary','c_openmp/build/jacobi_c_cpu','--suite','check','--threads','2','--cpu-only','--out','verify_c'])
 status=json.loads((temp/'verify_c/run_status.json').read_text());assert status['status']=='COMPLETED';checks.append('Packaged C CPU checks PASS; actual GPU evidence remains the formal Vanda run')
 run(['python3','closeout/plot_report.py']);assert len(list((temp/'closeout/figures').glob('*.png')))>=10
 checks.append('All integrated report figures reproduce from packaged concise CSV, without logs')
 pdf_python='/Users/kendallshao/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
 run([pdf_python,'closeout/build_report.py']);checks.append('PDF regenerates from the standalone ZIP inputs')
 output={'status':'PASS','checks':checks,'package_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
 (ROOT/'closeout/package_verification.json').write_text(json.dumps(output,indent=2));print(json.dumps(output,indent=2))
