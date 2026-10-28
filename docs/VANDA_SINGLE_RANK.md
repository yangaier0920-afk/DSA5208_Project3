# Vanda：A/B 单进程基准诊断

当前状态（2026-10-27）：1499802及1499842两轮诊断均已完成，后续三轮纯MPI复测也已完成。按行串行基准决定及受控证据见[1499842分析](../evidence/vanda_1499842_local_reduction/analysis.md)；当前汇总见[阶段结果材料](AB_RESULTS_SUMMARY.md)。下文为历史诊断操作记录，不代表还需提交候选实验。

状态：2026-10-27，首轮作业1499802已完成并审计；结果见 evidence/vanda_1499802_single_rank/analysis.md。以下首轮步骤保留用于复现，候选验证见文末。
本人账号 yangaier 已成功登录 stdct-login-01 并完成 amgr 认证。可用项目 personal-yangaier 显示 10000 CPU-hours。auto_free 已启用，为路由队列；cpu_parallel 已启用且只接收路由，最少 2 CPU。以下作业使用 auto_free，不使用项目额度行。

## 目的与边界

现有 Vanda 串行中位时间为 2.653333 秒，MPI P=1/sendrecv 为 1.293866 秒。当前诊断控制同一作业、同一 Linux 逻辑 CPU、相同 -O2 flags、相同 n/K，并交错运行：

1. serial_gpp：原 jacobi.cpp 经 g++ 编译。
2. serial_mpicxx：相同原 jacobi.cpp 经 mpicxx 编译，用于检查编译入口差异。
3. mpi_sendrecv：原 jacobi_mpi.cpp，P=1，sendrecv。
4. mpi_overlap：同一 MPI 可执行文件，P=1，overlap。

没有修改 Jacobi 算法，没有启用 OpenMP。MPI P=1 的通信邻居为空，本实验不能评价实际跨进程通信重叠。

## 作业设置

- 单节点，2 CPU、1 MPI slot、4GB、15 分钟上限。每次只运行一个单进程求解器。
- n=1024、K=1000、tolerance=0。
- 正确性先检查 n=7/K=31 全网格和 n=32/tol=1e-12 收敛，两案例各 4 配置，共 8 次。
- 各配置预热 1 次，正式测量 8 次，共 36 次计时执行。四配置按旋转/反序交错，每配置在每个位置出现两次。
- 串行和 MPI rank 内均由同一 Python 包装器固定 Linux CPU；MPI 启动器不另作绑定。包装器在 exec 前记录实际 mask，exec 保留该亲和性。
- 若继承的 CPU mask 比申请的 2 CPU 更宽，脚本保存元数据后停止，等待检查 PBS/cpuset，避免把“系统可见 CPU”直接当作已分配 CPU。
- 保存编译命令、源码及程序哈希、GCC 向量化报告、lscpu、进程状态、PBS 信息和每次 stdout/stderr。libpbs.so.0 警告不隐藏。

## 1. 本机 Windows PowerShell：上传

当前 SSH 窗口保持打开，另开一个本机 PowerShell。以下是本机命令，不要输入 Vanda 终端。

```powershell
Set-Location 'D:\桌面文件\NUS_sem1\DSA5208\Project3\github_ready\DSA5208_Project3'
ssh yangaier@vanda.nus.edu.sg 'mkdir -p dsa5208_project3/ab_diagnostic'
$abFiles = @('jacobi.cpp', 'jacobi_mpi.cpp', 'diagnose_single_rank.py', 'prepare_team_references.py', 'vanda_single_rank.pbs', 'vanda_modules.example.sh')
scp $abFiles yangaier@vanda.nus.edu.sg:dsa5208_project3/ab_diagnostic/
```

脚本和源码直接来自当前本地工作副本，不依赖先推送 GitHub。本次源文件有运行时哈希，不把旧 commit 误记成未提交修改后的完整身份。

## 2. Vanda 终端：核对语法并提交

```bash
cd ~/dsa5208_project3/ab_diagnostic
bash -n vanda_single_rank.pbs
bash -n vanda_modules.example.sh
qsub vanda_single_rank.pbs
qstat -u yangaier
```

仅当两个 bash -n 没有报错才提交。qsub 返回的完整作业 ID 要保留；排队状态 Q 是等待资源，R 是运行。
不要在登录节点直接执行 diagnose_single_rank.py 或编译/运行求解器。

## 3. Vanda：结束后验收

将 JOB_ID 换成实际完整 ID，保留后缀。

```bash
qstat -xf JOB_ID
cat ~/dsa5208_project3/ab_diagnostic/results/Vanda_single_rank_JOB_ID/run.log
```

若该目录尚不存在，作业可能未开始；若作业已失败且仍没有目录，查看 qstat 中 Output_Path 指向的 PBS 输出文件。
成功应有：PBS Exit_status=0，run.log 中 DIAGNOSTIC_STATUS=PASSED、RUN_STATUS=PASSED、JOB_EXIT_STATUS=0，以及 diagnostic/summary.json 中 status=PASS。

```bash
qstat -xf JOB_ID > ~/dsa5208_project3/ab_diagnostic/results/Vanda_single_rank_JOB_ID/qstat_full.txt
```

如失败，保留原目录与日志并交回分析，先不重复提交。

## 4. 本机：下载完整结果

```powershell
scp -r yangaier@vanda.nus.edu.sg:dsa5208_project3/ab_diagnostic/results/Vanda_single_rank_JOB_ID ./results/
```

执行前确认本机当前目录仍是仓库根目录，且同名本地作业目录不存在。结果入口为 diagnostic/summary.json。
这是专用单进程诊断格式，与原 benchmark_parallel.py 的 summary 格式不同，不直接传给 analyze_results.py。

## 如何解释

- serial_gpp 与 serial_mpicxx 接近，可降低“编译包装器本身造成差异”的可能性；不单凭它们相等解释 MPI 实现差距。
- 串行与 MPI 差距仍存在时，结合向量化报告和循环结构继续分析，不能归因为进程并行。
- 若差距缩小，说明旧比较受本次控制条件中的某些因素影响；本次同时改变多个环境因素，不能单独断言是哪一个。
- 该实验没有测试 P=2 的波动，不替代下一项通信方案复测。

AI 使用：Codex 根据本人实时终端信息准备 Python/PBS 与本指引；本地检查仅验证调度顺序、命令构造和数值验收逻辑。实际提交、集群结果与 CPU 绑定验收待用户执行；没有将模拟/历史结果当作新作业。


## 第二轮：验证最大更新量变量的代码生成影响

本轮仅新增独立候选，原版生产源码不变。四配置为原串行、每轮局部累积候选、每行局部累积候选和MPI P=1/sendrecv，均固定同一逻辑CPU，预热1次、各测8次。此轮不测试MPI多进程通信性能。

在本机PowerShell、仓库根目录上传4个新/更新文件：

```powershell
scp diagnose_single_rank.py vanda_single_rank.pbs jacobi_serial_local_update.cpp jacobi_serial_row_update.cpp yangaier@vanda.nus.edu.sg:dsa5208_project3/ab_diagnostic/
```

在Vanda终端检查并提交新作业：

```bash
cd ~/dsa5208_project3/ab_diagnostic
bash -n vanda_single_rank.pbs
qsub -v JACOBI_EXPERIMENT=local-reduction,JACOBI_REPEATS=8 vanda_single_rank.pbs
qstat -u yangaier
```

语法检查报错时先不要提交。记录新的完整作业ID，验收/下载方式同首轮，将旧ID替换成新ID。日志与归档使用新作业ID，不覆盖1499802的结果。比较以新作业内四配置为准，不将不同节点的绝对耗时混为一组。

源码差异：每轮候选只在迭代内部累积iteration_update，然后赋给max_update；每行候选进一步在行内累积row_update，再汇总到iteration_update。输入、边界、浮点精度、Jacobi值计算、计时范围、停止和输出规则一致。是否改善性能以及是否减少栈访问，都以新作业数据和机器码为准。
