#!/usr/bin/env python3
"""Summarize completed pilot/formal C measurements; plot only real samples."""
import argparse
import csv
import json
from pathlib import Path
import statistics
import math
import hashlib
import textwrap


def summarize(rows):
    groups={}
    for r in rows:
        if int(r['warmup']):
            continue
        n,backend,T=int(r['nx']),r['backend'],int(r['requested_threads'])
        metrics=['cpu_seconds'] if backend=='cpu' else ['gpu_resident_seconds','gpu_e2e_seconds']
        for metric in metrics:
            groups.setdefault((n,backend,T,metric),[]).append((int(r['repeat']),float(r[metric])))
    result=[]
    for (n,backend,T,metric),values in sorted(groups.items()):
        if sorted(rep for rep,_ in values)!=[1,2,3]:
            raise ValueError(f'Expected exactly repeats 1/2/3: {n}, {backend}, {T}, {metric}')
        v=[x for _,x in values]
        if not all(math.isfinite(x) for x in v) or min(v)<=0:
            raise ValueError('Timing must be positive')
        result.append(dict(n=n,backend=backend,threads=T,metric=metric,
                           median=statistics.median(v),minimum=min(v),maximum=max(v),samples=len(v)))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('batch',help='Runner output directory containing samples.csv')
    p.add_argument('--tables-only',action='store_true',help='No matplotlib needed')
    a=p.parse_args()
    batch=Path(a.batch).resolve()
    status=json.loads((batch/'run_status.json').read_text())
    if status['status']!='COMPLETED' or status['cpu_only'] or status['suite']=='check':
        p.error('Requires completed real GPU pilot/formal batch; local checks are not performance evidence')
    with (batch/'samples.csv').open() as f:
        rows=list(csv.DictReader(f))
    if status['suite']=='formal':
        # Preserve support for another explicitly chosen Tc, but require the whole matrix.
        cpu_threads={int(r['requested_threads']) for r in rows if r['backend']=='cpu'}
        if len(cpu_threads)!=2 or 1 not in cpu_threads:
            p.error('Formal requires CPU1 and one multi-thread baseline')
        tc=max(cpu_threads)
        expected={(n,b,t) for n in (64,128,256) for b,t in (('cpu',1),('cpu',tc),('gpu',1))}
        actual={(int(r['nx']),r['backend'],int(r['requested_threads'])) for r in rows}
        if len(rows)!=36 or actual!=expected or sum(int(r['warmup']) for r in rows)!=9:
            p.error('Formal requires all 9 configurations: 36 calls, 9 warmups, 27 measured')
        for key in expected:
            group=[r for r in rows if (int(r['nx']),r['backend'],int(r['requested_threads']))==key]
            if sorted((int(r['repeat']),int(r['warmup'])) for r in group)!=[(0,1),(1,0),(2,0),(3,0)]:
                p.error('Each formal configuration requires warmup 0 and measured repeats 1/2/3')
        if any(int(r['iterations'])!=1000 or int(r['dimension'])!=3 or
               not (int(r['nx'])==int(r['ny'])==int(r['nz'])) for r in rows):
            p.error('Formal requires cubic 3D grids and K=1000')
    stats=summarize(rows)
    if not stats:
        p.error('No formal samples')
    for n in sorted({x['n'] for x in stats}):
        subset=[x for x in stats if x['n']==n]
        if len(subset)!=4:
            p.error('Expected four timing series per grid (Tc must be >1 for this comparison)')
    output=batch/'analysis'
    output.mkdir(exist_ok=True)
    def write_csv(name, data):
        with (output/name).open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write_csv('summary.csv',stats)
    ratios=[]
    for n in sorted({x['n'] for x in stats}):
        sub=[x for x in stats if x['n']==n]
        cpu={x['threads']:x['median'] for x in sub if x['backend']=='cpu'}
        gpu={x['metric']:x['median'] for x in sub if x['backend']=='gpu'}
        Tc=max(cpu)
        ratios.append(dict(n=n,Tc=Tc,cpu_speedup=cpu[1]/cpu[Tc],cpu_efficiency=cpu[1]/cpu[Tc]/Tc,
            gpu_resident_vs_cpu1=cpu[1]/gpu['gpu_resident_seconds'],
            gpu_e2e_vs_cpu1=cpu[1]/gpu['gpu_e2e_seconds'],
            gpu_resident_vs_cpuTc=cpu[Tc]/gpu['gpu_resident_seconds'],
            gpu_e2e_vs_cpuTc=cpu[Tc]/gpu['gpu_e2e_seconds'],
            e2e_minus_resident=gpu['gpu_e2e_seconds']-gpu['gpu_resident_seconds']))
    write_csv('speedups.csv',ratios)
    lines=['# C 实验统计','',f'批次类型：{status["suite"]}。每配置三次正式样本，预热排除。',
           '','| n | 模式 | 线程 | 时间指标 | 中位数（秒） | 最小–最大（秒） |',
           '|---:|---|---:|---|---:|---|']
    for r in stats:
        lines.append(f'| {r["n"]} | {r["backend"]} | {r["threads"]} | {r["metric"]} | {r["median"]:.6g} | {r["minimum"]:.6g}–{r["maximum"]:.6g} |')
    lines+=['','加速比见 speedups.csv；e2e_minus_resident 是设备分配、传输、释放等合计差值，不能称为纯 PCIe 传输时间。',
            '误差棒表示三次样本的 min/max，并非置信区间。GPU 的两种时间来自同一次运行。']
    (output/'summary.md').write_text('\n'.join(lines)+'\n')
    if not a.tables_only:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
        except ImportError:
            p.error('Tables saved. Plot on Mac after: python3 -m venv .venv; .venv/bin/python -m pip install matplotlib')
        from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
        environment=json.loads((batch/'environment.json').read_text())
        gpu_lines=environment.get('gpu',{}).get('stdout','').strip().splitlines()
        gpu_info=list(csv.DictReader(gpu_lines,skipinitialspace=True))
        gpu_name=gpu_info[0].get('name','GPU').strip() if gpu_info else 'GPU'
        cpu_name=next((line.split(':',1)[1].strip() for line in
            environment.get('lscpu',{}).get('stdout','').splitlines()
            if line.startswith('Model name:')), 'CPU')
        cpu_name=cpu_name.replace('Intel(R) ','Intel ').replace('(R)','').replace('(TM)','')
        platform=f'{gpu_name} + {cpu_name}'
        grids=sorted({r['n'] for r in stats})
        tc=max(r['threads'] for r in stats if r['backend']=='cpu')
        captions={}
        plt.rcParams.update({'font.size':10.5, 'axes.titlesize':13, 'axes.labelsize':11,
                             'savefig.facecolor':'white', 'pdf.fonttype':42})
        colors=['#1f4e79','#d55e00','#00856a','#9a4c95']
        def grid_axis(ax):
            ax.set_xscale('log',base=2)
            ax.xaxis.set_major_locator(FixedLocator(grids))
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{int(x)}'))
            ax.xaxis.set_minor_locator(NullLocator())
            ax.set_xlim(min(grids)/1.12,max(grids)*1.12)
            ax.grid(True,which='major',alpha=.22)
            ax.set_axisbelow(True)
        def save(fig,name,caption):
            fig.subplots_adjust(left=.10,right=.97,top=.85 if name=='speedup' else .88,bottom=.25,wspace=.32)
            fig.text(.10,.045,textwrap.fill(caption,115),ha='left',va='bottom',fontsize=9,linespacing=1.4)
            fig.savefig(output/(name+'.png'),dpi=300)
            fig.savefig(output/(name+'.pdf'))
            plt.close(fig)
            captions[name]=caption
        fig,ax=plt.subplots(figsize=(9.4,6.6))
        series=[('cpu',1,'cpu_seconds','CPU T=1'),('cpu',tc,'cpu_seconds',f'CPU T={tc}'),
                ('gpu',1,'gpu_resident_seconds','GPU resident'),('gpu',1,'gpu_e2e_seconds','GPU end-to-end')]
        for (backend,T,metric,label),color,marker in zip(series,colors,['o','s','^','D']):
            points=sorted([r for r in stats if (r['backend'],r['threads'],r['metric'])==(backend,T,metric)],key=lambda r:r['n'])
            med=[r['median'] for r in points]
            ax.errorbar([r['n'] for r in points],med,
                        yerr=[[r['median']-r['minimum'] for r in points],
                              [r['maximum']-r['median'] for r in points]],
                        marker=marker,color=color,linewidth=1.8,capsize=4,label=label)
        grid_axis(ax)
        ax.set_yscale('log')
        ax.set(xlabel='Interior side length n (log scale)',ylabel='Runtime (s; log scale)',
               title='OpenMP CPU and single-GPU Jacobi runtimes')
        ax.legend(loc='upper left',framealpha=.95)
        save(fig,'runtime',f'{platform}. K=1000; median of 3 formal runs per configuration; warmup excluded. '
             'Bars span the observed minimum to maximum, not confidence intervals. Both axes are logarithmic. '
             'Resident and end-to-end GPU times come from the same run; formal data only.')
        fig,axes=plt.subplots(1,2,figsize=(10.8,6.6))
        for ax,suffix,baseline in zip(axes,['cpu1','cpuTc'],['CPU T=1',f'CPU T={tc}']):
            keys=[f'gpu_resident_vs_{suffix}',f'gpu_e2e_vs_{suffix}']
            for key,label,color,marker in zip(keys,['GPU resident','GPU end-to-end'],colors[2:],['^','D']):
                ax.plot([r['n'] for r in ratios],[r[key] for r in ratios],marker=marker,
                        color=color,linewidth=1.8,label=label)
            ax.axhline(1,color='#666666',linestyle=':',linewidth=1.2)
            ax.annotate('1x',xy=(max(grids),1),xytext=(3,4),textcoords='offset points',fontsize=9,color='#666666')
            grid_axis(ax)
            ax.set(xlabel='Interior side length n (log scale)',ylabel='Speedup = median CPU / median GPU',
                   title=f'Baseline: {baseline}')
            ax.set_ylim(0,max(float(r[k]) for r in ratios for k in keys)*1.45)
            ax.legend(loc='upper left',fontsize=9.5,framealpha=.95)
        fig.suptitle('GPU speedup: resident and end-to-end timing',y=.97,fontsize=14)
        save(fig,'speedup',f'{platform}. K=1000; ratios of medians from 3 formal runs per configuration; warmup excluded. '
             f'Numerator: CPU1 (left) or CPU{tc} (right); denominator: GPU resident or end-to-end time. '
             'Above 1 means GPU is faster. Size axes logarithmic; speedup axes linear with separate ranges. '
             'No error bars or confidence intervals.')
        (output/'figure_captions.md').write_text('\n\n'.join(f'**{k}.** {v}' for k,v in captions.items())+'\n')
        metadata={'suite':status['suite'],'host':environment.get('host'),'platform':platform,
                  'samples_sha256':hashlib.sha256((batch/'samples.csv').read_bytes()).hexdigest(),
                  'analyzer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'runtime_axes':{'x':'log2','y':'log10'},'speedup_axes':{'x':'log2','y':'linear'},
                  'runtime_error_bars':'observed min/max of 3 measured runs','speedup_error_bars':None,
                  'warmup_excluded':True,'grids':grids,'matplotlib':matplotlib.__version__}
        (output/'plot_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(f'Analysis saved: {output}')

if __name__=='__main__':
    main()
