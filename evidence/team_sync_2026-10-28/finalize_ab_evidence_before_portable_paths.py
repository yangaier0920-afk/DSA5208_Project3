"""Finalize saved A/B evidence after wait diagnostic, without new solver runs.
Raw directories and earlier reports are read-only. New output must not exist.
"""
import argparse
from datetime import datetime,timedelta,timezone
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import statistics
import tarfile
import difflib
import mpi_wait_diagnostic as m

BASE=Path(__file__).resolve().parent
ROOT=BASE/'results/Vanda_mpi_wait_1502229.stdct-mgmt-02'
PRIMARY=BASE/'evidence/vanda_1502229_mpi_wait'
CST=timezone(timedelta(hours=8))


def csv_save(path,rows):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def same_or_copy(source,target):
    if target.exists():
        m.require(m.sha(source)==m.sha(target),'Existing selected evidence differs')
    else:
        shutil.copy2(source,target)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out-dir',type=Path,default=BASE/'evidence/ab_final_2026-10-28')
    args=ap.parse_args()
    out=args.out_dir.resolve();m.require(not out.exists(),'New output required')
    audit=m.read(PRIMARY/'audit.json')
    s=m.read(ROOT/'diagnostic/summary.json')
    m.require(audit['status']==s['status']=='PASS','Primary audit incomplete')
    m.require(audit['job_id']==s['job_id']=='1502229.stdct-mgmt-02','Wrong job')
    # Prove that files actually run match the upload, not the later local CV audit fix.
    source_matches=[]
    with tarfile.open(BASE/'results/mpi_wait_upload_20261028_v1.tar.gz','r:gz') as tar:
        for p in sorted((ROOT/'sources').iterdir()):
            if p.is_file():
                same=hashlib.sha256(tar.extractfile(p.name).read()).hexdigest()==m.sha(p)
                m.require(same,'Submitted snapshot changed: '+p.name)
                source_matches.append(dict(name=p.name,sha256=m.sha(p),identical_to_uploaded_bundle=same))
    m.require(len(source_matches)==8,'Expected eight submitted runtime files')
    prep=m.read(BASE/'results/mpi_wait_local_20261028/checks.json')
    m.require(prep['source_change_roundtrip'] and prep['diagnostic_source_sha256']==m.sha(ROOT/'sources/jacobi_mpi_wait_diagnostic.cpp'),'Diagnostic source delta not verified')
    m.require(m.sha(BASE/'evidence/mpi_wait_audit_tool_fix_2026-10-28/mpi_wait_diagnostic_before.py')==m.sha(ROOT/'sources/mpi_wait_diagnostic.py'),'Pre-fix script not preserved exactly')
    matches=[]
    for name in ('Vanda_mpi_recheck_1499881','Vanda_mpi_recheck_1500222','Vanda_mpi_recheck_1500271','Vanda_ab_dual_1501884'):
        old=BASE/'results'/(name+'.stdct-mgmt-02')
        same=m.sha(old/'bin/jacobi_mpi')==m.sha(ROOT/'bin/jacobi_mpi')
        m.require(same,'Original MPI executable changed')
        m.require(m.sha(old/'sources/jacobi_mpi.cpp')==m.sha(ROOT/'sources/jacobi_mpi.cpp'),'Original MPI source changed')
        matches.append(dict(prior_job=name,original_source_identical=True,original_binary_identical=True))
    log=(ROOT/'run.log').read_text(encoding='utf-8')
    builds=[line for line in log.splitlines() if line.startswith('+ mpicxx ')]
    expected={'jacobi_mpi.cpp':'jacobi_mpi','jacobi_mpi_wait_diagnostic.cpp':'jacobi_mpi_wait_diagnostic'}
    m.require(len(builds)==2,'Build count')
    for line in builds:
        match=re.search(r'/sources/(\S+) -o (\S+)$',line)
        m.require(match and match.group(1) in expected and match.group(2).endswith('/bin/'+expected[match.group(1)]),'Build source/output mapping')
        m.require('-std=c++17 -O2 -Wall -Wextra -Wpedantic' in line,'Compiler flags')
    hw=(ROOT/'lscpu.txt').read_text(encoding='utf-8')
    numa=re.search(r'^NUMA node1 CPU\(s\):\s*(.+)$',hw,re.M)
    m.require(numa is not None,'NUMA topology missing')
    def expand(text):
        result=[]
        for part in text.split(','):
            v=list(map(int,part.split('-')));result.extend(range(v[0],v[-1]+1))
        return result
    m.require(set(s['pin_cpus'])<=set(expand(numa.group(1))),'CPU list outside recorded NUMA node1')
    qstat=(ROOT/'qstat_full.txt').read_text()
    m.require('resources_used.walltime = 00:04:45' in qstat and 'run_count = 1' in qstat,'Unexpected job metadata')
    validations=[];maximum=0.0
    for r in s['validation_runs']:
        case=next(c for c in m.CASES if c['id']==r['case_id'])
        oracle=m.oracle(case)
        difference=None
        if 'grid' in r['result']:
            difference=max(abs(a-b) for ra,rb in zip(r['result']['grid'],oracle['grid']) for a,b in zip(ra,rb))
            maximum=max(maximum,difference)
        validations.append(dict(id=r['id'],case_id=r['case_id'],n=r['n'],p=r['p'],kind=r['kind'],
                                exchange=r['exchange'],iterations=r['result']['iterations'],tolerance=r['tol'],
                                status=r['result']['status'],max_error=r['result']['max_error'],
                                residual_inf=r['result']['residual_inf'],full_grid_max_difference=difference,
                                comparison_scope='full grid and independent metrics' if difference is not None else 'independent metrics only'))
    m.require(sum(x['full_grid_max_difference'] is not None for x in validations)==35,'Full-grid count')
    m.require(sum(x['tolerance']>0 for x in validations)==5,'Convergence count')
    pairs=[]
    for n,p in m.COMBINATIONS:
        for repeat in range(5):
            runs={r['exchange']:r for r in s['performance_runs'] if not r['warmup'] and (r['n'],r['p'],r['repeat_index'])==(n,p,repeat)}
            m.require(set(runs)==set(m.SCHEMES),'Incomplete triplet')
            m.require(max(r['sequence'] for r in runs.values())-min(r['sequence'] for r in runs.values())==2,'Schemes not adjacent')
            for baseline,candidate in (('sendrecv','immediate'),('immediate','overlap'),('sendrecv','overlap')):
                a,b=runs[baseline],runs[candidate]
                pairs.append(dict(n=n,p=p,repeat_index=repeat,baseline=baseline,candidate=candidate,
                                  baseline_seconds=a['result']['compute_seconds'],candidate_seconds=b['result']['compute_seconds'],
                                  reduction_percent=100*(1-b['result']['compute_seconds']/a['result']['compute_seconds']),
                                  baseline_sequence=a['sequence'],candidate_sequence=b['sequence']))
    sequence=[]
    for section,runs in [('validation',s['validation_runs']),('performance',s['performance_runs'])]:
        for r in runs:
            sequence.append(dict(global_sequence=len(sequence),section=section,id=r['id'],n=r['n'],p=r['p'],
                                 kind=r['kind'],exchange=r['exchange'],warmup=r.get('warmup',''),
                                 repeat_index=r.get('repeat_index',''),
                                 started_at_cst=datetime.fromisoformat(r['started_at_utc']).astimezone(CST).isoformat(),
                                 finished_at_cst=datetime.fromisoformat(r['finished_at_utc']).astimezone(CST).isoformat()))
    # Saved CV differences are isolated; independent mean/stdev/median calculation is retained.
    groups,comparisons=m.statistics_for(s['performance_runs'])
    m.verify_saved_statistics(groups,comparisons,s)
    cv_diffs=[dict(n=g['n'],p=g['p'],exchange=g['exchange'],
                   local=g['sample_cv_percent'],archived=h['sample_cv_percent'])
              for g,h in zip(groups,s['groups']) if g['sample_cv_percent']!=h['sample_cv_percent']]
    manifests=m.read(BASE/'evidence/ab_summary_2026-10-28/raw_archives_manifest.json')
    for entry in manifests:
        m.require(m.sha(BASE/entry['path'])==entry['sha256'],'Historical archive changed')
    path=Path(audit['raw_archive']['path'])
    m.require(m.sha(path)==audit['raw_archive']['sha256'],'Current archive changed')
    # Recheck archive members after supplemental inspection; do not rewrite the archive.
    archive=m.archive_checked(ROOT,path)
    manifests.append(dict(path=path.relative_to(BASE).as_posix(),size_bytes=path.stat().st_size,
                          sha256=archive['sha256'],files=archive['files'],
                          contents_rechecked_against_downloaded_directory=True,
                          member_check_evidence='evidence/vanda_1502229_mpi_wait/audit.json'))
    review=dict(status='PASS',job_id=s['job_id'],host=s['host'],walltime='00:04:45',pin_cpus=s['pin_cpus'],
                numa_nodes=[1],upload_source_matches=source_matches,
                original_source_and_binary_identity=matches,
                diagnostic_is_separate_binary=True,performance_only_uses_diagnostic_binary=True,
                validation_executions=45,validation_original=18,validation_diagnostic=27,
                validation_full_grids=35,validation_max_grid_difference=maximum,validation_converged=5,
                performance_executions=54,performance_warmups=9,performance_formal=45,
                validation_affinity_records=205,performance_affinity_records=468,total_affinity_records=673,
                adjacent_formal_triplets_verified=15,scheme_position_counts='1 or 2, not exact balance',
                cv_cross_python_rounding_differences=cv_diffs,
                cv_tolerance=dict(relative=1e-12,absolute=1e-14),
                raw_timings_medians_and_comparisons_checked_exactly=True,
                raw_archive=archive,performance_samples_removed=0,new_cluster_runs_during_audit=0)
    out.mkdir(parents=True)
    m.save(out/'wait_diagnostic_review.json',review)
    m.save(out/'raw_archives_manifest.json',manifests)
    csv_save(out/'diagnostic_performance.csv',[{k:v for k,v in g.items() if k!='samples_seconds'} for g in groups])
    csv_save(out/'diagnostic_comparisons.csv',[{k:v for k,v in c.items() if k!='round_reductions_percent'} for c in comparisons])
    csv_save(out/'diagnostic_paired_rounds.csv',pairs)
    csv_save(out/'diagnostic_validation.csv',validations)
    csv_save(out/'diagnostic_execution_sequence.csv',sequence)
    main_summary=m.read(BASE/'evidence/ab_summary_2026-10-28/summary.json')
    final=dict(status='PASS',date='2026-10-28',completed_experiments=[1,3,2],
               formal_scaling_source='evidence/ab_summary_2026-10-28/summary.json',
               formal_scaling_jobs=4,formal_scaling_datasets=5,formal_scaling_groups=45,
               formal_scaling_performance_executions=450,formal_scaling_formal_samples=405,
               wait_diagnostic_job=s['job_id'],wait_diagnostic_groups=9,
               wait_diagnostic_performance_executions=54,wait_diagnostic_formal_samples=45,
               total_performance_executions=504,total_performance_formal_samples=450,
               total_structured_validation_numerical=428,total_expected_rejections=16,
               total_structured_full_grid_executions=238,
               timed_run_affinity_records=2418,total_affinity_records_including_diagnostic_validation=2623,
               raw_archives=7,main_performance=main_summary['performance'],
               wait_diagnostic_groups_data=groups,wait_diagnostic_comparisons=comparisons,
               pooling_policy='Never pool jobs, problem sizes, production and diagnostic binaries or timing baselines.',
               extra_serial_prechecks='Excluded from structured totals; see earlier reviewed evidence.',
               stop_rule='All three authorized supplementary experiments complete; no more cluster runs for this reporting round.',
               phase_instrumentation=False,git_committed_or_pushed=False,email_sent=False)
    m.save(out/'summary.json',final)
    # Backup mutable report before integrating experiment2, without deleting any earlier content.
    report_snapshot=BASE/'evidence/ab_final_2026-10-28/stage_report_before_experiment2.md'
    if not report_snapshot.exists():
        report_snapshot=BASE/'docs/AB_STAGE_REPORT_DRAFT_2026-10-28.md'
    same_or_copy(report_snapshot,out/'stage_report_before_experiment2.md')
    for name in ('run.log','qstat_full.txt','qstat_at_start.txt','metadata.txt','environment.txt','lscpu.txt',
                 'process_status.txt','pin_cpus.txt','pbs_nodefile.txt','source_sha256.txt','executable_sha256.txt'):
        same_or_copy(ROOT/name,PRIMARY/name)
    same_or_copy(ROOT/'diagnostic/summary.json',PRIMARY/'diagnostic_summary.json')
    source=(ROOT/'sources/jacobi_mpi.cpp').read_text(encoding='utf-8')
    diagnostic=(ROOT/'sources/jacobi_mpi_wait_diagnostic.cpp').read_text(encoding='utf-8')
    delta=''.join(difflib.unified_diff(source.splitlines(True),diagnostic.splitlines(True),
                                    fromfile='production/jacobi_mpi.cpp',tofile='diagnostic/jacobi_mpi_wait_diagnostic.cpp'))
    target=PRIMARY/'source_changes.diff'
    if target.exists():m.require(target.read_text(encoding='utf-8')==delta,'Existing source diff differs')
    else:target.write_text(delta,encoding='utf-8')
    target=PRIMARY/'supplemental_review.json'
    if target.exists():m.require(m.read(target)==review,'Existing supplemental review differs')
    else:m.save(target,review)
    print(json.dumps(dict(status='PASS',out=str(out),archive_files=archive['files'],max_grid_difference=maximum,
                          performance_samples_retained=54,completed_experiments=[1,3,2]),ensure_ascii=True,indent=2))


if __name__=='__main__':
    main()
