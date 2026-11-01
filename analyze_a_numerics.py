"""Plot A residual histories and tabulate continuous-grid errors; no reruns."""
import argparse
import csv
import math
from pathlib import Path

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    a=p.parse_args()
    with (a.directory/"summary.csv").open(encoding="utf-8") as f: rows=list(csv.DictReader(f))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(7,4.5))
    for r in rows:
        case=r["case_id"]
        if r["mode"]!="solve": continue
        with (a.directory/f"{case}_history.csv").open(encoding="utf-8") as f: h=list(csv.DictReader(f))
        ax.semilogy([int(v["iteration"]) for v in h],
                    [max(float(v["relative_residual"]),1e-18) for v in h],label=f"n={r['nx']}, Kmax={r['max_iters']}")
    ax.axhline(1e-8,color="gray",linestyle="--",label="R=1e-8")
    ax.axhline(1e-10,color="gray",linestyle=":",label="R=1e-10")
    ax.set(xlabel="Jacobi iteration",ylabel="Relative discrete L2 residual")
    ax.grid(alpha=.25);ax.legend();fig.tight_layout()
    fig.savefig(a.directory/"convergence.png",dpi=180);plt.close(fig)
    # Precision order uses only completed 3D solves, and only a factor-two h refinement.
    valid=sorted([r for r in rows if r["problem_id"]=="poisson3d_mms"
                  and r["mode"]=="solve" and r["status"]=="converged"],key=lambda r:int(r["nx"]))
    table=[];previous=None
    for r in valid:
        n=int(r["nx"]);e=float(r["continuous_error_inf"]);order="";ratio=""
        if previous and n+1==2*(previous[0]+1) and e>0:
            ratio=previous[1]/e;order=math.log2(ratio)
        table.append({"n":n,"h":1/(n+1),"continuous_error_inf":e,"coarse_to_fine_error_ratio":ratio,
                      "observed_order":order,"relative_residual":r["relative_residual"],
                      "iterations":r["iterations"],"first_check_le_1e8":r["first_check_le_1e8"],
                      "single_run_seconds":r["compute_seconds"]})
        previous=(n,e)
    if table:
        with (a.directory/"precision.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    print(f"Wrote convergence.png and {len(table)} precision rows in {a.directory}")
if __name__=="__main__": main()

