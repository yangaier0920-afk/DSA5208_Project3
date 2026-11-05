"""Verify downloaded A scaling samples and regenerate publication figures."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('batch', type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    data = a.batch/'data'
    rows = list(csv.DictReader((data/'samples.csv').open(encoding='utf-8')))
    summary = list(csv.DictReader((data/'summary.csv').open(encoding='utf-8')))
    env = json.loads((data/'environment.json').read_text())
    status = json.loads((data/'run_status.json').read_text())
    require = lambda ok, msg: None if ok else (_ for _ in ()).throw(ValueError(msg))
    require(status == dict(status='completed',configurations=10,warmups=10,formal_samples=30), 'Incomplete run')
    require(len(rows)==40 and len(summary)==10, 'Sample count')
    require('Exit_status = 0' in (a.batch/'qstat_full.txt').read_text(), 'PBS exit')
    require('JOB_EXIT_STATUS=0' in (a.batch/'run.log').read_text(), 'Job exit')
    source_hashes = {}
    for name in ['jacobi_a_scaling.cpp','run_a_scaling.py']:
        digest=hashlib.sha256((a.batch/'source'/name).read_bytes()).hexdigest()
        require(digest==env['sha256'][name], 'Downloaded source hash '+name)
        require(digest==hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest(), 'Local source hash '+name)
        source_hashes[name]=digest
    for check in json.loads((data/'validation.json').read_text()):
        require(check['discrete_error_inf']<=1e-9 and check['boundary_error_inf']<=1e-12, 'Small-grid validation')
    require(len({(r['problem_id'],r['nx'],r['repeat']) for r in rows})==40,'Duplicate sample')
    for r in rows:
        name=f"{r['problem_id']}_n{r['nx']}_r{r['repeat']}"
        raw=json.loads((data/(name+'.stdout.json')).read_text())
        command=json.loads((data/(name+'.command.json')).read_text())
        require(command['exit_code']==0,'Sample exit '+name)
        require(int(r['warmup'])==int(r['repeat']=='0'),'Warmup '+name)
        require(int(r['iterations'])==1000 and int(r['max_iters'])==1000,'Workload '+name)
        require(raw['problem_id']==r['problem_id'] and raw['nx']==int(r['nx']),'Problem '+name)
        require(raw['iterations']==1000 and raw['status']=='fixed_iterations','Raw workload '+name)
        require(math.isclose(raw['compute_seconds'],float(r['compute_seconds']),rel_tol=1e-14),'Raw time '+name)
        require(float(r['boundary_error_inf'])<=1e-12,'Boundary '+name)
        require(all(math.isfinite(float(r[k])) for k in ['compute_seconds','relative_residual','continuous_error_inf','discrete_error_inf']),'Finite '+name)
    prior={}
    for s in summary:
        problem,n=s['problem_id'],int(s['n'])
        subset=[r for r in rows if r['problem_id']==problem and int(r['nx'])==n and r['warmup']=='0']
        require(len(subset)==3,'Formal count')
        times=[float(r['compute_seconds']) for r in subset]
        med=statistics.median(times)
        expected=dict(median_seconds=med,min_seconds=min(times),max_seconds=max(times),seconds_per_point_update=med/(1000*int(s['N'])))
        if problem in prior:
            pn,pt=prior[problem]
            expected['local_exponent']=math.log(med/pt)/math.log(n/pn)
        prior[problem]=(n,med)
        require(all(math.isclose(float(s[k]),v,rel_tol=1e-12,abs_tol=1e-16) for k,v in expected.items()),'Statistics '+str((problem,n)))
    a.output.mkdir(parents=True,exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':150})
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    cost,caxes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    slopes={}
    for d,ax,cax in zip([2,3],axes,caxes):
        points=[s for s in summary if s['problem_id']==f'poisson{d}d_mms']
        ns=[int(s['n']) for s in points]
        ts=[float(s['median_seconds']) for s in points]
        lows=[t-float(s['min_seconds']) for s,t in zip(points,ts)]
        highs=[float(s['max_seconds'])-t for s,t in zip(points,ts)]
        ax.errorbar(ns,ts,yerr=[lows,highs],fmt='o-',capsize=3,label='Median; min/max')
        ax.plot(ns,[ts[0]*(n/ns[0])**d for n in ns],'--',color='gray',label=f'Reference: n^{d}')
        ax.set(xscale='log',yscale='log',xlabel='Interior points per axis, n',ylabel='1000-iteration time (s)',title=f'{d}D Poisson')
        ax.set_xticks(ns,labels=[str(n) for n in ns]);ax.grid(True,which='both',alpha=.18);ax.legend(fontsize=8)
        scale=[1000*n**d for n in ns]
        cax.errorbar(ns,[t/q*1e9 for t,q in zip(ts,scale)],yerr=[[v/q*1e9 for v,q in zip(lows,scale)],[v/q*1e9 for v,q in zip(highs,scale)]],fmt='o-',capsize=3)
        cax.set(xscale='log',xlabel='Interior points per axis, n',ylabel='Time per point update (ns)',title=f'{d}D normalized cost')
        cax.set_xticks(ns,labels=[str(n) for n in ns]);cax.set_ylim(bottom=0);cax.grid(True,alpha=.18)
        # The vertical normalized quantity is also a time axis: use log per Lecture 12.
        cax.set_yscale('log');cax.set_ylim(.9,4)
        slopes[str(d)]=math.log(ts[-1]/ts[0])/math.log(ns[-1]/ns[0])
    fig.savefig(a.output/'serial_scaling.png',bbox_inches='tight')
    fig.savefig(a.output/'serial_scaling.pdf',bbox_inches='tight')
    cost.savefig(a.output/'point_update_cost.png',bbox_inches='tight')
    cost.savefig(a.output/'point_update_cost.pdf',bbox_inches='tight')
    plt.close('all')
    report={'status':'PASS','performance_samples':40,'formal_samples':30,'configurations':10,'source_hashes':source_hashes,'endpoint_exponents':slopes,'all_boundary_errors_zero':all(float(r['boundary_error_inf'])==0 for r in rows),'max_formal_relative_range':max((float(s['max_seconds'])-float(s['min_seconds']))/float(s['median_seconds']) for s in summary)}
    (a.output/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
