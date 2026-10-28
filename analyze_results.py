'''Audit a complete downloaded PBS run; generate data-driven tables and plots.
Standard library for auditing; --plots additionally needs matplotlib.
'''
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_rows(benchmark):
    '''Recompute statistics from recorded executions, independently of saved tables.'''
    groups = benchmark['groups']
    serial_groups = [g for g in groups if g['mode'] == 'serial']
    require(len(serial_groups) == 1, 'Expected exactly one serial baseline')
    serial = serial_groups[0]['median_seconds']
    mpi_base = {g['exchange']: g['median_seconds'] for g in groups
                if g['mode'] == 'mpi' and g['processes'] == 1}
    rows = []
    keys = set()
    for group in groups:
        key = (group['mode'], group['processes'], group['threads'], group['exchange'])
        require(key not in keys, f'Duplicate configuration: {key}')
        keys.add(key)
        records = [r for r in benchmark['runs']
                   if (r['result']['mode'], r['result'].get('mpi_processes', 1),
                       r['result']['threads'], r['result'].get('exchange', 'none')) == key]
        require(sum(r['warmup'] for r in records) == benchmark['warmups'],
                f'Wrong warmup count: {key}')
        times = [r['result']['compute_seconds'] for r in records if not r['warmup']]
        require(len(times) == benchmark['repeats'], f'Wrong measurement count: {key}')
        require(all(math.isfinite(t) and t > 0 for t in times), f'Invalid time: {key}')
        require(statistics.median(times) == group['median_seconds'] and
                min(times) == group['min_seconds'] and max(times) == group['max_seconds'],
                f'Saved statistics differ from executions: {key}')
        require(group['total_cores'] == group['processes'] * group['threads'],
                f'Wrong core count: {key}')
        require(math.isclose(serial / group['median_seconds'], group['speedup']) and
                math.isclose(group['speedup'] / group['total_cores'], group['efficiency']),
                f'Wrong speedup/efficiency: {key}')
        row = dict(group)
        base = mpi_base.get(group['exchange']) if group['mode'] == 'mpi' else None
        row['mpi_relative_speedup'] = base / group['median_seconds'] if base else ''
        row['mpi_relative_efficiency'] = (row['mpi_relative_speedup'] / group['processes']
                                          if base else '')
        rows.append(row)
    require(sum((benchmark['warmups'] + benchmark['repeats']) for _ in rows) ==
            len(benchmark['runs']), 'Executions outside configured groups')
    return rows


def make_report(benchmark, validation, rows, warnings):
    '''Describe this dataset only; causal explanations remain a manual review task.'''
    b, v = benchmark, validation
    numerical = [r['result'] for r in v['runs'] if 'result' in r]
    invalid = len(v['runs']) - len(numerical)
    sizes = ', '.join(map(str, sorted({d['n'] for d in numerical})))
    nodes = sorted({r['result']['nodes'] for r in b['runs'] if 'nodes' in r['result']})
    node_text = ', '.join(map(str, nodes)) if nodes else 'not recorded'
    table = '\n'.join(
        f"| {r['mode']} | {r['processes']}x{r['threads']} | {r['exchange']} | "
        f"{r['median_seconds']:.6f} | {r['min_seconds']:.6f}-{r['max_seconds']:.6f} | "
        f"{r['speedup']:.3f} | {100*r['efficiency']:.1f}% |" for r in rows)
    normalized = '\n'.join(
        f"| {r['processes']} | {r['exchange']} | {r['mpi_relative_speedup']:.3f} | "
        f"{100*r['mpi_relative_efficiency']:.1f}% |"
        for r in rows if r['mpi_relative_speedup'] != '')
    observations = []
    serial = next(r for r in rows if r['mode'] == 'serial')
    for r in rows:
        if r['mode'] == 'mpi' and r['processes'] == 1:
            observations.append(
                f"- MPI P=1 ({r['exchange']}) 为 {r['median_seconds']:.6f} 秒，"
                f"相对本次串行基准为 {r['speedup']:.3f} 倍；该差异不能归因于多进程并行。")
    for method in sorted({r['exchange'] for r in rows if r['mode'] == 'mpi'}):
        data = [r for r in rows if r['mode'] == 'mpi' and r['exchange'] == method
                and r['mpi_relative_speedup'] != '']
        if data:
            r = max(data, key=lambda item: item['processes'])
            observations.append(
                f"- {method} 在本次最大 P={r['processes']} 时，相对同策略 MPI P=1 "
                f"加速 {r['mpi_relative_speedup']:.3f} 倍，效率 "
                f"{100*r['mpi_relative_efficiency']:.1f}%。")
    widest = max(r['total_cores'] for r in rows)
    best = min((r for r in rows if r['total_cores'] == widest),
               key=lambda item: item['median_seconds'])
    observations.append(
        f"- 本次使用 {widest} 核的已测配置中，观测中位数最低的是 "
        f"{best['mode']} {best['processes']}x{best['threads']} {best['exchange']}，"
        f"为 {best['median_seconds']:.6f} 秒；此处不作统计显著性结论。")
    observations.append(f"- 本次串行基准中位数为 {serial['median_seconds']:.6f} 秒。"
                        '相对串行加速比包含实现和编译效果差异；不据此单独判断超线性扩展。')
    warning_text = '\n'.join('- ' + warning for warning in warnings) or '- 原始 stderr 未检出 libpbs.so.0 警告。'
    return f'''# A/B 集群实验核对

生成日期：{datetime.now(timezone.utc).date().isoformat()}（UTC）。此文件是当前作业的数据摘要，人工因果分析和阶段报告需另行审阅。

## 当前证据

集群：{b['cluster']}；作业：`{b['job_id']}`；记录主机：`{b['host']}`。
分配 CPU 数：{b['allocated_cpus']}；并行输出记录的节点数：{node_text}。
完整原始目录的 PBS 完成状态、退出码、源码/程序哈希及逐次 JSON 已核对。
硬件型号、内存、walltime、模块与 flags 以原始 metadata.txt、qstat_full.txt 和构建日志为准，本摘要不推断未采集的信息。

## 正确性记录

共 {len(v['runs'])} 次验证执行，其中 {len(numerical)} 次含数值结果，{invalid} 次为预期非法输入拒绝测试；网格规模 n 包括 {sizes}。
验证器状态为 PASS，逐次数值 JSON 已与汇总核对。执行次数不等于不同数学问题数；本审计不代替验证器中的数值验收。

## 性能口径

n={b['n']}，K={b['iterations']}，tolerance={b['tolerance']}；固定迭代工作量，不宣称收敛。
{len(rows)} 组配置，各预热 {b['warmups']} 次、测量 {b['repeats']} 次，共 {len(b['runs'])} 次执行。
串行基准源码：`{b.get('serial_source', 'jacobi.cpp')}`；运行顺序：`{b.get('order', 'grouped (historical)')}`。
显式CPU映射：`{b.get('pin_cpus', [])}`；空列表表示未由本脚本记录显式映射，需查原始绑定日志。
计时为迭代阶段，MPI 含必要通信/同步并取最慢 rank；初始化、最终检查与输出不计入。
报告中位数和 min/max，min/max 不是置信区间。运行顺序和绑定方式应结合逐次命令审阅。

| 版本 | PxT | 通信 | 中位秒数 | min-max 秒数 | 相对串行加速比 | 相对串行效率 |
|---|---|---|---:|---:|---:|---:|
{table}

## 同策略 MPI 单进程基准

S(P)=T_MPI(1)/T_MPI(P)，E(P)=S(P)/P。缺少对应 P=1 时不推算此指标。

| 进程数 | 通信 | 相对 MPI P=1 加速比 | 效率 |
|---:|---|---:|---:|
{normalized}

## 本次观测

{chr(10).join(observations)}

单个作业、单一规模不支持跨规模稳定性结论。非阻塞 API 的使用不证明通信已有效重叠；通信方案的优势与差异原因需结合重复实验分析。

## 环境警告

{warning_text}

完整原始目录须单独保留以供复核。当前摘要不自动确认线程 affinity、PBS 多节点集成、个人代码理解或组员接口确认。

AI 使用：Codex 协助编写核对工具和当前数据摘要；集群操作、源码修改、人工复核等实际贡献应在阶段报告中据实补充。
'''


def make_plots(b, rows, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    mpi = [r for r in rows if r['mode'] == 'mpi']
    links = []
    title = (f"{b['cluster']} {b['host']} | n={b['n']}, K={b['iterations']} | "
             f"{b['warmups']} warmups + {b['repeats']} measurements")
    if mpi:
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout='constrained')
        for method in sorted({r['exchange'] for r in mpi}):
            data = sorted((r for r in mpi if r['exchange'] == method), key=lambda r:r['processes'])
            axes[0].errorbar([r['processes'] for r in data], [r['median_seconds'] for r in data],
                            yerr=[[r['median_seconds']-r['min_seconds'] for r in data],
                                  [r['max_seconds']-r['median_seconds'] for r in data]],
                            marker='o', capsize=3, label=method)
            scaled = [r for r in data if r['mpi_relative_speedup'] != '']
            if scaled:
                axes[1].plot([r['processes'] for r in scaled],
                             [r['mpi_relative_speedup'] for r in scaled], marker='o', label=method)
        maximum = max(r['processes'] for r in mpi)
        axes[1].plot([1, maximum], [1, maximum], '--', color='#999999', label='Ideal linear')
        for ax in axes:
            ax.set_xlabel('MPI processes')
            ax.set_xticks(sorted({r['processes'] for r in mpi}))
            ax.grid(alpha=.2)
            ax.legend()
        axes[0].set_ylabel('Iteration time (seconds)')
        axes[1].set_ylabel('Speedup vs same-strategy MPI P=1')
        fig.suptitle(title)
        fig.savefig(out/'mpi_scaling.png', dpi=180)
        plt.close(fig)
        links.append('![MPI 扩展](mpi_scaling.png)')
    hybrid = [r for r in rows if r['mode'] == 'hybrid']
    for cores in sorted({r['total_cores'] for r in hybrid}):
        data = [r for r in hybrid if r['total_cores'] == cores]
        fig, ax = plt.subplots(figsize=(10, 4.6), layout='constrained')
        ax.bar(range(len(data)), [r['median_seconds'] for r in data],
               yerr=[[r['median_seconds']-r['min_seconds'] for r in data],
                     [r['max_seconds']-r['median_seconds'] for r in data]], capsize=3)
        ax.set_xticks(range(len(data)),
                      [f"{r['processes']}x{r['threads']}\n{r['exchange']}" for r in data], rotation=30)
        for r in rows:
            if r['mode'] == 'openmp' and r['total_cores'] == cores:
                ax.axhline(r['median_seconds'], linestyle='--', color='#555555',
                           label=f'OpenMP {cores} threads')
                ax.legend()
        ax.set_ylabel('Iteration time (seconds)')
        ax.set_ylim(bottom=0)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        ax.set_title(title + f' | hybrid, {cores} cores')
        name = f'hybrid_comparison_{cores}cores.png'
        fig.savefig(out/name, dpi=180)
        plt.close(fig)
        links.append(f'![Hybrid {cores} 核]({name})')
    return links


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--plots', action='store_true')
    args = ap.parse_args()
    root, out = args.results.resolve(), args.out_dir.resolve()
    b = json.loads((root/'benchmark/summary.json').read_text(encoding='utf-8'))
    v = json.loads((root/'validation/summary.json').read_text(encoding='utf-8'))
    require(b['status'] == v['status'] == 'PASS', 'Incomplete or failed run')
    log = (root/'run.log').read_text(encoding='utf-8')
    qstat = (root/'qstat_full.txt').read_text(encoding='utf-8')
    require('RUN_STATUS=PASSED' in log and 'JOB_EXIT_STATUS=0' in log, 'Failed run log')
    require('Exit_status = 0' in qstat and 'job_state = F' in qstat, 'Failed PBS status')
    for manifest, directory in [('source_sha256.txt', 'sources'), ('executable_sha256.txt', 'bin')]:
        for line in (root/manifest).read_text(encoding='utf-8').splitlines():
            digest, name = line.split(maxsplit=1)
            path = root/directory/name.strip().rsplit('/', 1)[-1]
            if not path.is_file():
                raise FileNotFoundError(f'Audit requires original archived file: {path}')
            require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Hash mismatch: {path}')
    for record in v['runs']:
        require(record['validation'] == 'PASS', f"Failed validation: {record['id']}")
        raw = (root/'validation'/(record['id']+'.stdout.json')).read_text(encoding='utf-8')
        if 'result' in record:
            require(json.loads(raw) == record['result'], f"Changed validation JSON: {record['id']}")
        else:
            require(record['exit_code'] != 0 and not raw.strip(),
                    f"Invalid-input test did not reject input: {record['id']}")
    for record in b['runs']:
        require(record['exit_code'] == 0, f"Failed benchmark: {record['id']}")
        raw = json.loads((root/'benchmark'/(record['id']+'.stdout.json')).read_text(encoding='utf-8'))
        require(raw == record['result'], f"Changed benchmark JSON: {record['id']}")
    rows = checked_rows(b)
    warnings = (['libpbs.so.0 unavailable; MPI PBS TM components were ignored']
                if any('libpbs.so.0' in p.read_text(encoding='utf-8')
                       for p in (root/'benchmark').glob('*.stderr.txt')) else [])
    out.mkdir(parents=True, exist_ok=False)
    with (out/'performance_audited.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    audit = dict(status='PASS', cluster=b['cluster'], job_id=b['job_id'],
                 validation_executions=len(v['runs']), benchmark_executions=len(b['runs']),
                 configurations=len(rows), warmups_per_configuration=b['warmups'],
                 measurements_per_configuration=b['repeats'],
                 original_source_and_binary_hashes_checked=True,
                 raw_results_and_statistics_checked=True, warnings=warnings)
    (out/'audit.json').write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
    report = make_report(b, v, rows, warnings)
    if args.plots:
        report += '\n## 图表\n\n' + '\n\n'.join(make_plots(b, rows, out)) + '\n'
    (out/'B_Vanda实验分析.md').write_text(report, encoding='utf-8')
    print(f"Audit PASS: {len(v['runs'])} validation executions, {len(b['runs'])} benchmark executions, {len(rows)} configurations; {out}")


if __name__ == '__main__':
    main()
