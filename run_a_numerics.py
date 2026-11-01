"""Run A's own numerical cases; no cluster submission. Output directory must be new."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--binary",required=True,type=Path)
    p.add_argument("--suite",choices=["smoke","formal"],default="smoke")
    p.add_argument("--out-dir",required=True,type=Path)
    a=p.parse_args()
    binary=a.binary.resolve()
    if not binary.is_file(): p.error("Binary does not exist")
    a.out_dir.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parent
    files=[binary,root/"jacobi_numerics.cpp",Path(__file__).resolve()]
    metadata={"platform":platform.platform(),"python":sys.version,"suite":a.suite,
              "purpose":"local basic check" if a.suite=="smoke" else "A numerical study; platform recorded",
              "pbs_job_id":os.getenv("PBS_JOBID"),"host":platform.node(),
              "sha256":{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
              "compiler_note":"See compile.log in the build/job directory for compiler and flags."}
    (a.out_dir/"environment.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    cases=([("poisson3d_mms",7,"fixed",1000,1e-8,0),
            ("poisson3d_mms",7,"solve",100000,1e-10,0),
            ("poisson3d_mms",7,"solve",1,1e-10,2)]
           if a.suite=="smoke" else
           [("poisson3d_mms",n,"solve",100000,1e-10,0) for n in (15,31,63)]
           +[("laplace2d_legacy",n,"fixed",1000,1e-8,0) for n in (1024,2048)])
    rows=[]
    for problem,n,mode,k,tol,expected in cases:
        name=f"{problem}_n{n}_{mode}_k{k}"
        cmd=[str(binary),"--problem",problem,"--nx",str(n),"--mode",mode,
             "--max-iters",str(k),"--tol",str(tol),"--check-every","10",
             "--history",str((a.out_dir/f"{name}_history.csv").resolve())]
        proc=subprocess.run(cmd,capture_output=True,text=True)
        (a.out_dir/f"{name}.stdout.json").write_text(proc.stdout,encoding="utf-8")
        (a.out_dir/f"{name}.stderr.txt").write_text(proc.stderr,encoding="utf-8")
        (a.out_dir/f"{name}.command.json").write_text(json.dumps({"argv":cmd,"exit_code":proc.returncode},indent=2),encoding="utf-8")
        if proc.returncode not in (0,2): raise RuntimeError(f"{name}: execution failed; see stderr")
        row=json.loads(proc.stdout)
        if a.suite=="smoke":
            assert proc.returncode==expected, (name,proc.returncode)
            assert row["boundary_error_inf"]<=1e-14
            if mode=="fixed": assert row["discrete_error_inf"]<=1e-9
            elif expected==0: assert row["relative_residual"]<=tol and row["converged"]
            else: assert row["status"]=="iteration_limit" and not row["converged"]
        row["case_id"]=name
        row["exit_code"]=proc.returncode
        rows.append(row)
        with (a.out_dir/"summary.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        print(f"{name}: {row['status']}, R={row['relative_residual']:.4g}",flush=True)
    (a.out_dir/"run_status.json").write_text(json.dumps({"status":"completed","cases":len(rows)}),encoding="utf-8")

if __name__=="__main__": main()

