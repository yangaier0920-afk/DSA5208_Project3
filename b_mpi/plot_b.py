#!/usr/bin/env python3
"""Reproduce report figures from the concise, audited numerical CSV."""
import argparse,csv,pathlib

def plot_rows(rows,out,paired_rows=None):
 warnings=[]
 try:
  import matplotlib;matplotlib.use('Agg')
  import matplotlib.pyplot as plt
 except ImportError:plt=None;warnings.append('matplotlib unavailable; CSV still generated')
 if plt and rows:
  def save(fig,name):fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=180);fig.savefig(out/(name+'.pdf'));plt.close(fig)
  strong=[r for r in rows if r['suite']=='strong']
  if strong:
   fig,axes=plt.subplots(1,3,figsize=(13,4))
   for n in sorted({r['nx'] for r in strong}):
    rs=sorted([r for r in strong if r['nx']==n],key=lambda x:x['P']);xs=[r['P'] for r in rs];ys=[r['median'] for r in rs];axes[0].errorbar(xs,ys,yerr=[[r['median']-r['minimum'] for r in rs],[r['maximum']-r['median'] for r in rs]],marker='o',label=f'{n}³')
    rs=[r for r in rs if r['speedup']!=''];axes[1].plot([r['P'] for r in rs],[r['speedup'] for r in rs],'o-',label=f'{n}³; base '+('72' if n==512 else '1'));axes[2].plot([r['P'] for r in rs],[100*r['efficiency'] for r in rs],'o-',label=f'{n}³')
   for ax,y in zip(axes,['Iteration time (s)','Speedup','Efficiency (%)']):ax.set_xscale('log',base=2);ax.set_xlabel('MPI ranks / CPU cores');ax.set_ylabel(y);ax.grid(True,alpha=.3);ax.legend(fontsize=7)
   axes[0].set_yscale('log');axes[1].set_yscale('log')
   xmax=max(r['P'] for r in strong);axes[1].plot([1,xmax],[1,xmax],'k--',label='Ideal, P1 baseline');axes[1].legend(fontsize=7)
   if any(r['nx']==512 for r in strong):axes[1].plot([72,xmax],[1,xmax/72],'k:',label='Ideal, P72 baseline');axes[1].legend(fontsize=7)
   ticks=sorted({r['P'] for r in strong})
   for ax in axes:ax.set_xticks(ticks,[str(x) for x in ticks],fontsize=8)
   axes[2].set_ylim(0,105)
   if not any(r['speedup']!='' for r in strong):axes[1].set_ylim(.5,2);axes[1].text(.5,.5,'Baseline pending',transform=axes[1].transAxes,ha='center')
   save(fig,'strong_scaling')
  weak=sorted([r for r in rows if r['suite']=='weak'],key=lambda x:x['P'])
  if weak:
   fig,axes=plt.subplots(1,2,figsize=(9,4));axes[0].errorbar([r['P'] for r in weak],[r['median']/1000 for r in weak],yerr=[[ (r['median']-r['minimum'])/1000 for r in weak],[(r['maximum']-r['median'])/1000 for r in weak]],marker='o');axes[0].set_yscale('log');axes[0].set_ylabel('Seconds / iteration')
   valid=[r for r in weak if r['efficiency']!=''];axes[1].plot([r['P'] for r in valid],[100*r['efficiency'] for r in valid],'o-');axes[1].set_ylabel('Weak efficiency (%)')
   for ax in axes:ax.set_xscale('log',base=2);ax.set_xlabel('MPI ranks / CPU cores');ax.grid(True,alpha=.3)
   axes[1].set_ylim(0,105)
   for ax in axes:ax.set_xticks([r['P'] for r in weak],[str(r['P']) for r in weak],fontsize=8)
   save(fig,'weak_scaling')
  hybrid=paired_rows if paired_rows is not None else [r for r in rows if r['suite']=='hybrid']+[r for r in rows if r['suite']=='strong' and r['nx']==256 and r['P'] in (72,144)]
  if hybrid:
   hybrid.sort(key=lambda r:(r['cores'],-r['P']));fig,ax=plt.subplots(figsize=(9,4));ax.errorbar(range(len(hybrid)),[r['median'] for r in hybrid],yerr=[[r['median']-r['minimum'] for r in hybrid],[r['maximum']-r['median'] for r in hybrid]],fmt='o');ax.set_xticks(range(len(hybrid)),[f"{r['P']}×{r['T']}" for r in hybrid]);ax.set_yscale('log');ax.set_ylabel('Iteration time (s)');ax.set_xlabel('MPI ranks × OpenMP threads');save(fig,'hybrid_layouts')
 return warnings

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--paired-csv');p.add_argument('--csv',required=True);p.add_argument('--out',required=True);args=p.parse_args()
 out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
 rows=list(csv.DictReader(open(args.csv)))
 paired=pathlib.Path(args.paired_csv) if args.paired_csv else pathlib.Path(args.csv).with_name('hybrid_summary.csv')
 paired_rows=list(csv.DictReader(paired.open())) if paired.exists() else None
 for row in rows+(paired_rows or []):
  for key in ('nx','ny','nz','P','T','cores','nodes','K'):row[key]=int(row[key])
  for key in ('median','minimum','maximum','relative_residual','speedup','efficiency'):
   if row[key]!='':row[key]=float(row[key])
 print(plot_rows(rows,out,paired_rows))
