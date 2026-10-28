# Vanda：MPI通信与强扩展复测

状态：2026-10-27，1499881（1024）、1500222（2048）及最后独立重复1500271（1024）全部完成并审计，各92次验证、90次性能执行及390条执行前rank绑定通过。原定正常实验计划结束，进入阶段报告整理。
综合结果见[中文材料](AB_RESULTS_SUMMARY.md)，新作业见[1500271审计](../evidence/vanda_1500271_mpi_recheck/analysis.md)。以下上传、提交与“待运行”描述保留作历史复现步骤，不是当前追加作业指令。本轮仅串行与纯MPI。

## 为什么现在可以重测

1499802确认原串行与MPI P=1的约两倍差距在同CPU下仍存在；1499842的受控候选实验确认按行局部最大更新量消除了串行内层循环的每点栈读写，原串行3.496400秒、按行串行1.723135秒、MPI P=1为1.746897秒。
后续A/B串行基准明确采用jacobi_serial_row_update.cpp。历史jacobi.cpp、OpenMP/混合源码及旧实验数据保留，不将新串行时间和旧节点的并行时间混算加速比。

## 本轮设计

- auto_free，单节点12CPU/12MPI slots、4GB、20分钟上限。
- n=1024、固定K=1000、tolerance=0，不宣称收敛。
- 9组：按行串行1组；MPI P=1/2/4/12分别sendrecv、overlap，共8组。
- 预热各1次，正式各9次，共90次计时执行。九种配置旋转交错，正式测量时每配置在每个顺序位置出现一次。
- 固定每个rank到不同已分配Linux CPU；串行和MPI rank0均用列表第一个CPU。记录exec前mask并验收，MPI不额外覆盖绑定。
- 先对新基准与MPI执行正确性验收，包括不整除分区和12进程收敛案例。
- 保存源码/程序哈希、原始逐次JSON/stderr、完整命令、元数据、硬件、PBS初始状态和派生统计。
- 同时支持相对按行串行的总加速比，以及相同通信策略MPI P=1的强扩展；P=2波动与overlap优势依据新记录分析。
- 只有一次PBS分配时仍不作跨作业稳定性结论；独立复测和n=2048留作后续。

## 本机PowerShell：上传新增/更新文件

当前目录应为D:\桌面文件\NUS_sem1\DSA5208\Project3\github_ready\DSA5208_Project3。
前两轮已上传的jacobi.cpp、jacobi_serial_row_update.cpp、jacobi_mpi.cpp、prepare_team_references.py、vanda_modules.example.sh继续使用。

```powershell
scp benchmark_parallel.py pin_cpu.py verify_small.py verify_parallel.py team_contract_v0.1.json vanda_mpi_recheck.pbs yangaier@vanda.nus.edu.sg:dsa5208_project3/ab_diagnostic/
```

## Vanda：检查并提交

```bash
cd ~/dsa5208_project3/ab_diagnostic
bash -n vanda_mpi_recheck.pbs
qsub vanda_mpi_recheck.pbs
qstat -u yangaier
```

bash检查报错时先不要提交。记录qsub返回的新作业ID，以下将JOB_ID替换为完整ID。

```bash
tail -n 30 results/Vanda_mpi_recheck_JOB_ID/run.log
qstat -xf JOB_ID
```

成功条件：PBS Exit_status=0、最终job_state=F，日志RUN_STATUS=PASSED/JOB_EXIT_STATUS=0，validation和benchmark的summary均PASS。默认qstat列表空不代表丢失，用qstat -xf查历史。
如果CPU mask不是12个，作业会在计时前停止，保留process_status/lscpu/PBS信息，先核对再调整，不擅自选系统可见的其他CPU。

结束后在Vanda保存最终状态：

```bash
qstat -xf JOB_ID > results/Vanda_mpi_recheck_JOB_ID/qstat_full.txt
```

## 本机：下载与分析

```powershell
scp -r yangaier@vanda.nus.edu.sg:dsa5208_project3/ab_diagnostic/results/Vanda_mpi_recheck_JOB_ID ./results/
```

确保同名本地作业目录不存在，再下载，避免合并旧结果。
可用本地analyze_results.py审计完整包；图表可选且需要matplotlib。生成报告将记录实际串行源码、执行顺序和CPU映射。

```text
python analyze_results.py --results results/Vanda_mpi_recheck_JOB_ID --out-dir results/analysis_JOB_ID --plots
```

## 验证边界

本地已检查90次执行计划、顺序平衡、命令构造、错误绑定拒绝，并实际运行grouped/interleaved两种串行CLI；这些不是新MPI实验。
目标Vanda的bash语法、多rank绑定、编译和计时待实际作业确认。libpbs.so.0警告保留并结合单节点限制说明，不推断多节点集成完整。


## 补充n=2048，无需上传新文件

在Vanda、相同工作目录提交，脚本和工作量口径保持一致，只将n改为2048，并增加最长时间上限：

```bash
cd ~/dsa5208_project3/ab_diagnostic
qsub -l walltime=00:30:00 -v JACOBI_N=2048 vanda_mpi_recheck.pbs
qstat -u yangaier
```

n=2048在现有实现支持范围内；每边内部点数翻倍，总内部点数变为4倍。30分钟是运行上限，不是预计必须运行30分钟。计算时长随节点和缓存/带宽等变化，优先以日志为准。
结果仍在results/Vanda_mpi_recheck_新作业ID，结束后保存qstat_full并按相同方法下载。基准全部在新作业内取得，勿直接用旧串行秒数配新并行秒数。

独立重复n=1024留作最后一轮，提交时显式使用 `qsub -v JACOBI_N=1024 vanda_mpi_recheck.pbs`，避免混淆规模。


## n=2048验收完成

作业1500222.stdct-mgmt-02，IN-003，实际10分11秒，验证、计时、绑定和哈希均通过。分析见[1500222审计](../evidence/vanda_1500222_mpi_recheck/analysis.md)。12进程相对本次串行加速约5.86倍，不能因低于1024首轮就判定实现错误；规模与节点分配一起变化，原因尚待解释。
正常计划仅剩独立1024复测：

```bash
cd ~/dsa5208_project3/ab_diagnostic
qsub -v JACOBI_N=1024 vanda_mpi_recheck.pbs
qstat -u yangaier
```

记录新的完整作业ID，结束后保存qstat_full.txt并下载对应新目录。该作业完成后优先汇总阶段报告。


## 最后一轮1500271验收完成

2026-10-27：n=1024，IN-003，walltime00:05:23，最终PBS状态F、退出0。基础分析与补充数值/绑定/顺序复核全部通过；完整包已保存于results/raw_archives/，逐文件比对通过。
串行中位数1.527579秒；MPI P=1 sendrecv/overlap为1.543310/1.529819秒；P=12为0.217869/0.217064秒。相对本次串行加速7.011/7.037倍，以同策略MPI P=1为基准约7.084/7.048倍。
与1499881相比，12进程耗时接近但串行基准更快，故归一化加速比降低；差异原因未确定。overlap的中位优势没有稳定复现首轮幅度。
本轮不要求再操作Vanda。接下来只整理报告、人工核对与交接，不默认增加实验。
