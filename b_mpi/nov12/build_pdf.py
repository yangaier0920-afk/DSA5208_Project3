#!/usr/bin/env python3
"""B-specific review report, generated from the audited CSVs only."""
import csv
import html
import json
import importlib.util
import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'b_mpi/nov12/final_results_20261112'
OUT=ROOT/'output/pdf/DSA5208_B_Completed_Experiments_20261112.pdf'
OUT.parent.mkdir(parents=True,exist_ok=True)
if os.environ.get('REPORT_FONT_DIR'):
    FONT=Path(os.environ['REPORT_FONT_DIR'])
elif importlib.util.find_spec('matplotlib'):
    import matplotlib
    FONT=Path(matplotlib.get_data_path())/'fonts/ttf'
else:
    FONT=Path('/Library/Frameworks/Python.framework/Versions/3.12/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf')
for name,file in [('Body','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
styles=getSampleStyleSheet()
for name,size,leading,font,color in [('BodyB',9.2,13,'Body','#24323d'),('TitleB',22,28,'Bold','#123c49'),
        ('HeadingB',15,20,'Bold','#123c49'),('SubB',10.5,15,'Bold','#14677a'),
        ('CellB',7.4,10,'Body','#24323d'),('HeadB',7.4,10,'Bold','#ffffff'),('CaptionB',7.6,10.5,'Body','#53616b')]:
    styles.add(ParagraphStyle(name=name,fontName=font,fontSize=size,leading=leading,textColor=colors.HexColor(color),spaceAfter=7))
W=174*mm
story=[]
def read(name):
    p=DATA/name
    return list(csv.DictReader(p.open())) if p.exists() else []
def text(s,style='BodyB'):
    story.append(Paragraph(html.escape(str(s)),styles[style]))
def heading(s):text(s,'HeadingB')
def table(headers,rows,widths=None):
    data=[[Paragraph(html.escape(str(x)),styles['HeadB']) for x in headers]]
    data += [[Paragraph(html.escape(str(x)),styles['CellB']) for x in row] for row in rows]
    t=Table(data,colWidths=widths or [W/len(headers)]*len(headers),repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#174c5b')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#edf4f6'),colors.white])]))
    story.extend([t,Spacer(1,8)])
def image(name,height):story.append(Image(str(DATA/name),width=W,height=height*mm))
def page():story.append(PageBreak())
def f(x,d=3):return f'{float(x):.{d}f}'
new=read('summary.csv');old=read('historical_summary.csv');strong=read('strong_scaling.csv')
core=json.loads((DATA/'core_task_audit.json').read_text())
states=read('PBS_status.csv');phase=read('phase_summary.csv');axes=read('axis_summary.csv')
def get(mode,case):return next(r for r in new if r['mode']==mode and r['case']==case)

text('Cartesian MPI Jacobi','TitleB')
text('B experiment completion and review response | 12 November 2026','SubB')
text('DSA5208 Project 3. B-specific supplement; member identities and individual contribution declarations remain omitted as requested.')
heading('1. Completed core work')
text(f"All {core['required_configurations']} required performance configurations are present and audited. "
     f"The new core suite contains {core['core_formal_samples']} formal timing samples and {core['core_diagnostic_runs']} separately instrumented runs. "
     'Each accepted job has independent PBS exit status zero, the prescribed repeats, valid numerical output, source hashes and disjoint CPU binding evidence.')
table(['Review item','Completed evidence'],[
 ['P144 rerun','Nine-host pure MPI and separate four-host complete MPI/OpenMP matrix; all six earlier P144 hosts excluded.'],
 ['P1 baseline','Exclusive 72-core CN-094 allocation; MPI P1 and A serial on the same bound core; 1 warmup + 5 formal repeats at 128 and 256 cubed.'],
 ['Directional diagnostics','Per-rank x/y/z Sendrecv and pack/unpack intervals, host mapping and both neighbors.'],
 ['P72 optimization','Four rank/thread layouts, original code plus five experimental variants, 1 warmup + 3 formal repeats each.'],
 ['Interpretation','Alternative weak references, baseline sensitivity, small-domain saturation and qualified P144/hybrid conclusions.'],
 ['Optional scaling','Recovered completed P432/P720 jobs from 8 November, including P720 strong scaling.']],[39*mm,135*mm])
text('Main finding','SubB')
text('The nine-host P144 run recovers much of the lost performance, but a different four-host P144 allocation reproduces the high-wait regime. This rules out a simple claim that replacing CN-011/CN-108 uniquely fixes the problem. Layout and runtime conditions matter; hardware fault attribution remains unproven.')
text('Parallel packing provides the clear P72 improvement. Parallel first touch and a persistent team alone have little effect here. Even the optimized hybrid result only approaches the same-allocation pure-MPI result; it does not establish a general hybrid advantage.')
text('Timing scope: K=1000 fixed Jacobi sweeps; maximum rank iteration interval. Initialization and final residual evaluation are outside that interval. All formal samples, including slow observations, are retained. Error bars are observed min/max, not confidence intervals.','CaptionB')
page()

heading('2. Stable baseline and updated strong scaling')
base=[r for r in new if r['mode']=='baseline']
table(['Implementation / grid','Median (s)','Min - max (s)','Max deviation'],[
 [r['case'],f(r['median'],6),f(r['minimum'],6)+' - '+f(r['maximum'],6),f(r['max_deviation_pct'],2)+'%'] for r in sorted(base,key=lambda r:r['case'])],[53*mm,30*mm,59*mm,32*mm])
text('All four five-repeat series meet the predeclared 5% maximum deviation target without deleting samples. MPI P1 is faster than the A serial control on this common core; the earlier cross-platform A/B ordering is not an inherent MPI overhead measurement. Separate source loops, data layout and generated code can contribute. GCC vectorization diagnostics are archived; neither build reports a successfully vectorized loop under these flags. This comparison does not isolate a unique compiler cause.')
image('strong_scaling.png',61)
text('Connected P144 points use the predeclared nine-host pure-MPI cohort. Open diamonds retain the separate four-host high-wait control. P1 is the new exclusive baseline; 512 cubed uses P72 as its reference. Allocations and dates differ.','CaptionB')
table(['Grid','P1 (s)','P72 (s)','P144, 9 hosts','P288 (s)','P720 (s)'],[
 [str(n)+' cubed']+[f(next(r['median'] for r in strong if int(r['n'])==n and int(r['P'])==p),4)
                      if any(int(r['n'])==n and int(r['P'])==p for r in strong) else '-' for p in (1,72,144,288,720)] for n in (128,256,512)])
text('At 128 cubed, the P36/P72/P144/P288 domains are small enough that halo exchange, packing and launch/synchronization costs can offset the reduced arithmetic. The new P144 point is not forced to lie monotonically between its neighbors. Larger grids retain more useful work per rank. Updated speedup/efficiency values are in strong_scaling.csv; the old P1 and all old samples remain in historical_summary.csv.')
page()

heading('3. Weak scaling and the P144 layout effect')
image('weak_scaling.png',61)
text('64 cubed unknowns per rank; different Cartesian aspect ratios are recorded in the raw commands. Total seconds over 1000 sweeps are numerically equal to milliseconds per sweep. Connected P144 uses nine hosts; the open diamond shows the four-host control.','CaptionB')
weak=read('weak_scaling.csv')
table(['P','Median (ms/sweep)','E1','E8','E72'],[[r['P'],f(r['median'],4)]+[f(100*float(r[k]),2)+'%' if r[k] else '-' for k in ('E1','E8','E72')] for r in weak])
text('E1/E8/E72 are reference-time / measured-time ratios. P1 and P8 were each single-node allocations on different physical hosts, so their loss does not by itself prove within-node bandwidth saturation. Node occupancy, memory placement and MPI costs are alternative contributors. The E8/E72 views separate that initial loss from additional scaling losses without changing any samples.')
text('Same process count, distinct allocations','SubB')
rows=[]
for case,label in [('strong128','128 cubed'),('strong256','256 cubed'),('strong512','512 cubed'),('weak64','64 cubed / rank')]:
    h=next(r for r in old if r['suite']==('weak' if case=='weak64' else 'strong') and int(r['P'])==144 and (case=='weak64' or int(r['nx'])==int(get('clean144',case)['nx'])))
    rows.append([label,f(h['median']),f(get('paired144',case)['median']),f(get('clean144',case)['median'])])
table(['Workload','Historical 4 hosts (s)','New 4 hosts (s)','New 9 hosts (s)'],rows)
text('The new four-host allocation is CN-004/CN-041/CN-086/GN-A40-076; the nine-host run uses CN-005/083/086/096/100/118/140/142/146. Both exclude all hosts from the two earlier P144 runs. Recovery on nine hosts is therefore evidence for a layout-dependent operating regime, not a unique failed-node diagnosis. The new four-host run and nine-host run share CN-086, so they are not mutually node-independent.')
page()

heading('4. P72 ablation and paired P144 hybrid results')
image('optimization_ablation.png',77)
text('CN-094, exclusive 72 cores, 256 cubed. Original is the frozen Nov7 source; all other variants share the experimental allocation representation. Gains below use experimental baseline / variant, not the original binary.','CaptionB')
ab=read('optimization_gains.csv')
table(['Variant','72 x 1 (s)','12 x 6 (s)','6 x 12 (s)','2 x 36 (s)'],[
 [variant]+[f(next(r['median'] for r in ab if r['variant']==variant and r['layout']==layout),4)
             for layout in ('72x1','12x6','6x12','2x36')]
 for variant in ('original','baseline','parallel_pack','first_touch','persistent','optimized')],[42*mm,33*mm,33*mm,33*mm,33*mm])
text('Parallel packing gives approximately 1.51x / 1.30x / 1.33x improvements for 12x6 / 6x12 / 2x36 relative to the matched experimental baseline. First touch and persistence alone change little. The combined 12x6 median is 1.182 s versus 1.192 s for original pure MPI; observed ranges overlap, so a robust win over pure MPI is not established. A packing-only option is the simpler supported design choice.')
table(['P144 layout','Median (s)','Range (s)','Own MPI / layout'],[
 [r['layout'],f(r['median']),f(r['minimum'])+' - '+f(r['maximum']),f(r['same_allocation_MPI_over_layout'],2)+'x'] for r in read('hybrid_144_comparison.csv')])
text('P144 hybrid gains remain conditional on a slow four-host pure-MPI reference. The nine-host MPI result is never used as a denominator for these four-host layouts. The 4x36 range is wide; its variability is retained rather than replaced by a preferred run. NUMA first writes are implemented without serial zero-fill, but physical page placement was not independently measured.')
page()

heading('5. Communication evidence and directionality')
table(['Diagnostic','Total (s)','Update (s)','Pack (s)','Comm/wait (s)','Comm %'],[
 [r['mode']+' / '+r['case'],f(r['total']),f(r['update']),f(r['pack_unpack']),f(r['communication_wait']),f(r['communication_pct'],1)+'%'] for r in phase],[55*mm,23*mm,24*mm,24*mm,25*mm,23*mm])
text('Rows describe each diagnostic run\'s slowest rank. Instrumentation changes timing; these are not substitutes for the formal medians. Remaining time includes synchronization and loop overhead. On 6x12, packing drops from about 0.440 s to 0.095 s with the combined treatment, consistent with the packing-only ablation.')
table(['Layout / axis','Rank at max','Host','Max wait (s)','Neighbors of that axis'],[
 [('9 hosts' if r['mode']=='clean144' else '4 hosts')+' / '+r['axis'],r['rank_at_max'],r['host'],f(r['maximum_wait']),r['low_host']+' / '+r['high_host']]
 for r in axes if r['mode'] in ('clean144','paired144')],[35*mm,23*mm,32*mm,28*mm,56*mm])
text('The four-host maximum x wait is 11.994 s on rank 130 (GN-A40-076), with CN-086 as its non-boundary neighbor. The largest z waits involve ranks on the same host; waiting can propagate through the sequential blocking exchanges, so axis labels cannot uniquely identify a network link or a faulty physical direction. Full per-rank neighbor tables, including worst cross-host participants, are published in axis_summary.csv and axis_rank_pairs.csv.')
text('Two-rank reference ping-pong: CN-005 / CN-083','SubB')
table(['Payload (bytes)','Median RTT (us)','Min RTT (us)','Max RTT (us)'],[
 [r['bytes'],f(float(r['median_rtt_seconds'])*1e6,2),f(float(r['minimum'])*1e6,2),f(float(r['maximum'])*1e6,2)] for r in read('link_round_trips.csv')])
text('Each payload has 100 warmup round trips and three timing windows (2000 round trips for 8 bytes; 500 for the other payloads). These are measured RTT windows, not one-way latency or fitted alpha/beta constants. Original-node probes remain optional while their requested resources are unavailable.')
page()

heading('6. Optional checks, provenance and remaining scope')
table(['Optional observation','Job','Median (s)','Range (s)'],[
 [r['suite']+' P'+r['P'],('1529169' if r['P']=='432' else '1529170'),f(r['median'],6),f(r['minimum'],6)+' - '+f(r['maximum'],6)] for r in read('optional_summary.csv')],[40*mm,24*mm,40*mm,70*mm])
text('P432 weak scaling uses six hosts; P720 weak/strong uses ten. Both PBS jobs completed on 8 November, but were collected and audited on 12 November. P720 512-cubed speedup is about 6.41x relative to P72 (64.1% relative efficiency). Hardware, residual, source and binding checks passed. Physical host count and load still differ.')
two=read('two_dimensional_scaling.csv')
if two:
    text('Optional 2D extension: 512 x 512, K=1000','SubB')
    table(['MPI ranks','Median (s)','Speedup','Efficiency'],[[r['P'],f(r['median'],6),f(r['speedup'],2),f(100*float(r['efficiency']),2)+'%'] for r in two])
    text('These 2D and 3D grids contain different amounts of work. Their absolute timing ratio is not a dimension-only comparison. Perimeter/surface growth provides a qualitative model; changing local sizes and startup costs remain material.')
else:
    text('Optional 2D: the single-host P1/P12/P36/P72 extension is submitted as job 1546883 and is not included as a result until independent completion evidence is available.')
text('Scheduler snapshot','SubB')
table(['Experiment','Job','State','Exit'],[[r['experiment'],r['job'].split('.')[0],r['state'],r['exit_status']] for r in states],[64*mm,38*mm,32*mm,40*mm])
text('Q/H/R entries are not completed measurements. Original-host diagnostic/probe requests are optional supplements; the mandatory directional analysis is already available from both new P144 allocations. Queue availability is an external limit, and no login-node performance run is used.')
text('Reproduction and evidence','SubB')
text('Use b_mpi/nov12/README.md for collection/rebuild commands. final_results_20261112 contains audited CSVs, all outcomes, snapshots of actual allocations, source and binary hashes, and raw_evidence.zip with a SHA-256 manifest. The frozen Nov7 source remains unchanged. Rebuild commands retain every sample and replace denominators only after the prescribed audit. No participant identities or unconfirmed contribution statements have been added.')

def footer(canvas,doc):
    canvas.saveState();canvas.setStrokeColor(colors.HexColor('#d4e2e7'));canvas.line(18*mm,16*mm,192*mm,16*mm)
    canvas.setFont('Body',7);canvas.setFillColor(colors.HexColor('#65747e'))
    canvas.drawString(18*mm,12*mm,'DSA5208 Project 3 | B follow-up | 12 November 2026')
    canvas.drawRightString(192*mm,12*mm,str(doc.page));canvas.restoreState()
doc=SimpleDocTemplate(str(OUT),pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=23*mm)
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(OUT)
