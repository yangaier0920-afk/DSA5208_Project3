#!/usr/bin/env python3
import csv,json,pathlib,math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
ROOT=pathlib.Path('.');OUT=ROOT/'closeout/figures';OUT.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.size':10,'axes.labelsize':10,'legend.fontsize':8,'pdf.fonttype':42})
def read(p):return list(csv.DictReader(open(p)))
def save(fig,name):
 fig.tight_layout(pad=.8);fig.savefig(OUT/(name+'.png'),dpi=220);fig.savefig(OUT/(name+'.pdf'));plt.close(fig)
def err(ax,rs,x,y,label,**kw):
 xx=[float(r[x]) for r in rs];v=[float(r[y]) for r in rs]
 mn='minimum' if 'minimum' in rs[0] else 'min_seconds';mx='maximum' if 'maximum' in rs[0] else 'max_seconds'
 ax.errorbar(xx,v,yerr=[[a-float(r[mn]) for a,r in zip(v,rs)],[float(r[mx])-a for a,r in zip(v,rs)]],marker='o',capsize=3,label=label,**kw)
def logx(ax,xs):ax.set_xscale('log',base=2);ax.set_xticks(xs,[str(x) for x in xs]);ax.grid(alpha=.22)
a=read('a_scaling_20261104/Vanda_1522376.stdct-mgmt-02/data/summary.csv')
fig,axs=plt.subplots(1,2,figsize=(7.2,3.25))
for ax,D in zip(axs,[2,3]):
 rs=[r for r in a if r['problem_id']==f'poisson{D}d_mms'];xx=[int(r['n']) for r in rs];err(ax,rs,'n','median_seconds','Measured')
 ax.plot(xx,[float(rs[0]['median_seconds'])*(x/xx[0])**D for x in xx],'--',color='gray',label=f'n^{D} reference');logx(ax,xx);ax.set_yscale('log');ax.set(xlabel='Interior side n',ylabel='Iteration time (s)',title=f'{D}D serial, K=1000');ax.legend()
save(fig,'serial_scaling')
fig,axs=plt.subplots(1,2,figsize=(7.2,3.25))
for n in [15,31,63]:
 rs=read(f'evidence/vanda_1512708_a_numerics/data/poisson3d_mms_n{n}_solve_k100000_history.csv');axs[0].semilogy([int(r['iteration']) for r in rs],[float(r['relative_residual']) for r in rs],label=f'{n}³')
axs[0].set(xlabel='Iteration k (linear)',ylabel='Relative L2 residual');axs[0].grid(alpha=.2);axs[0].legend()
h=[1/16,1/32,1/64];e=[.0227631872,.00563935389,.00140667331];axs[1].loglog(h,e,'o-',label='Continuous error');axs[1].loglog(h,[e[0]*(x/h[0])**2 for x in h],'--',color='gray',label='Order 2 reference');axs[1].set(xlabel='Grid spacing h',ylabel='Continuous L∞ error');axs[1].legend();axs[1].grid(alpha=.2);save(fig,'numerical_accuracy')
B=ROOT/'results/final_202611/B_mpi/analysis'
b=read(B/'summary.csv')
for metric,name,ylab in [('median','mpi_time','Iteration time (s)'),('speedup','mpi_speedup','Speedup (baseline stated)'),('efficiency','mpi_efficiency','Efficiency (%)')]:
 fig,ax=plt.subplots(figsize=(7.2,3.3))
 for n in [128,256,512]:
  rs=sorted([r for r in b if r['suite']=='strong' and int(r['nx'])==n],key=lambda r:int(r['P']));xs=[int(r['P']) for r in rs]
  if metric=='median':err(ax,rs,'P','median',f'{n}³')
  else:ax.plot(xs,[float(r[metric])*(100 if metric=='efficiency' else 1) for r in rs],'o-',label=f'{n}³ (base '+('72' if n==512 else '1')+')')
 logx(ax,[1,12,36,72,144,288]);ax.set(xlabel='MPI ranks / physical CPU cores',ylabel=ylab)
 if metric!='efficiency':ax.set_yscale('log')
 else:ax.set_ylim(0,105)
 if metric=='speedup':ax.plot([1,288],[1,288],'k--',label='Ideal (P1 base)');ax.plot([72,288],[1,4],'k:',label='Ideal (P72 base)')
 review=ROOT/'closeout/review144/summary.csv'
 if review.exists():
  r=read(review)[0];p=144;v=float(r['median'])
  base=float(next(x['median'] for x in b if x['suite']=='strong' and int(x['nx'])==256 and int(x['P'])==1))
  if metric=='median':value=v
  elif metric=='speedup':value=base/v
  else:value=base/v/p*100
  ax.scatter([p],[value],marker='D',facecolors='none',edgecolors='#c22638',s=80,label='256³ independent 144 review',zorder=5)
 ax.legend(ncol=2,fontsize=8);save(fig,name)
w=sorted([r for r in b if r['suite']=='weak'],key=lambda r:int(r['P']));fig,axs=plt.subplots(1,2,figsize=(7.2,3.25));xs=[int(r['P']) for r in w]
axs[0].errorbar(xs,[1000*float(r['median'])/1000 for r in w],yerr=[[float(r['median'])-float(r['minimum']) for r in w],[float(r['maximum'])-float(r['median']) for r in w]],marker='o',capsize=3);axs[0].set_yscale('log');axs[0].set_ylabel('Milliseconds per sweep')
axs[1].plot(xs,[100*float(r['efficiency']) for r in w],'o-');axs[1].set_ylabel('Weak efficiency (%)');axs[1].set_ylim(0,105)
for ax in axs:logx(ax,xs);ax.set_xlabel('MPI ranks / CPU cores')
save(fig,'weak_scaling')
hyb=read(ROOT/'closeout/hybrid_summary.csv') if (ROOT/'closeout/hybrid_summary.csv').exists() else [r for r in b if r['suite']=='hybrid' or (r['suite']=='strong' and r['nx']=='256' and r['P'] in ('72','144'))]
hyb.sort(key=lambda r:(int(r['cores']),-int(r['P'])));fig,ax=plt.subplots(figsize=(7.2,3.3));x=list(range(len(hyb)));ax.errorbar(x,[float(r['median']) for r in hyb],yerr=[[float(r['median'])-float(r['minimum']) for r in hyb],[float(r['maximum'])-float(r['median']) for r in hyb]],fmt='o',capsize=3);ax.set_xticks(x,[r['P']+'×'+r['T'] for r in hyb],fontsize=9);ax.set_yscale('log');ax.set(xlabel='MPI ranks × threads per rank',ylabel='Iteration time (s)');ax.axvline(3.5,color='gray',ls=':');ax.grid(axis='y',alpha=.22);save(fig,'hybrid_layouts')
d=read(B/'diagnostics.csv');fig,ax=plt.subplots(figsize=(7.2,3.3))
for j,(key,label) in enumerate([('update','Update'),('pack_unpack','Pack/unpack'),('communication_wait','Communication/wait')]):
 ax.scatter([float(r['P'])*(1+.06*(j-1)) for r in d],[float(r[key]) for r in d],label=label,s=35)
logx(ax,[72,144,288]);ax.set_yscale('log');ax.set(xlabel='MPI ranks / CPU cores',ylabel='Accumulated seconds (1000 sweeps)');ax.legend(ncol=3);save(fig,'communication')
c=read('c_openmp/deliverables/formal_20261106/analysis/summary.csv');fig,ax=plt.subplots(figsize=(7.2,3.7))
for backend,t,key,label in [('cpu','1','cpu_seconds','CPU1'),('cpu','12','cpu_seconds','CPU12'),('gpu','1','gpu_resident_seconds','GPU resident'),('gpu','1','gpu_e2e_seconds','GPU end-to-end')]:
 rs=sorted([r for r in c if r['backend']==backend and r['threads']==t and r['metric']==key],key=lambda r:int(r['n']));err(ax,rs,'n','median',label)
logx(ax,[64,128,256]);ax.set_yscale('log');ax.set(xlabel='Interior side n',ylabel='Iteration / data-region time (s)');ax.legend(ncol=2);save(fig,'gpu_runtime')
c=read('c_openmp/deliverables/formal_20261106/analysis/speedups.csv');fig,axs=plt.subplots(1,2,figsize=(7.2,3.25))
for ax,suffix,label in zip(axs,['cpu1','cpuTc'],['CPU1 baseline','CPU12 baseline']):
 for key,legend in [('gpu_resident_vs_','Resident'),('gpu_e2e_vs_','End-to-end')]:ax.plot([int(r['n']) for r in c],[float(r[key+suffix]) for r in c],'o-',label=legend)
 logx(ax,[64,128,256]);ax.axhline(1,color='gray',ls=':');ax.set(xlabel='Interior side n',ylabel='Median CPU / median GPU',title=label);ax.legend()
save(fig,'gpu_speedup')
for name,eq in [('jacobi',r'$u^{k+1}_{\mathbf{i}}=\frac{\sum_{d=1}^{D}a_d(u^k_{\mathbf{i}-\mathbf{e}_d}+u^k_{\mathbf{i}+\mathbf{e}_d})+f_{\mathbf{i}}}{2\sum_{d=1}^{D}a_d},\quad a_d=h_d^{-2}$'),('discrete',r'$\lambda_h=\sum_{d=1}^{D}4a_d\sin^2(m_d\pi h_d/2),\quad u_h^*=\ell+\frac{c_D}{\lambda_h}\prod_{d=1}^{D}\sin(m_d\pi x_d)$')]:
 fig=plt.figure(figsize=(7.2,.8));fig.text(.5,.5,eq,ha='center',va='center',fontsize=15);fig.savefig(OUT/(name+'.png'),dpi=220,bbox_inches='tight',pad_inches=.05);plt.close(fig)
print('Report figures generated')
