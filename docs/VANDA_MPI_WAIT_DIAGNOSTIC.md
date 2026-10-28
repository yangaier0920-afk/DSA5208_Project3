# 实验2：等待位置诊断（2026-10-28）

## 当前完成状态：1502229已完整审计，停止追加

2026-10-28，1502229.stdct-mgmt-02在IN-006成功完成（PBS F/退出0，walltime4分45秒），45次正确性、54次性能、673条绑定及222文件原始归档核验通过。本页下方为原设计和提交前说明，保留原文；不需要再次提交。

2048/P2未观察到清楚的等待位置收益；两个P12仅约1%的中位耗时降低，不能据此宣称底层重叠机制已证明。详见[经复核分析](../evidence/vanda_1502229_mpi_wait/analysis_reviewed.md)和[最终汇总入口](../evidence/ab_final_2026-10-28/README.md)。本地审计仅修复CV跨Python舍入兼容，原集群源码和原始结果不变。

判断：还有时间时，值得做一次原定实验2；不需要新增实验类型或重跑完整扩展矩阵。
1500222与1501884的2048/P2分别出现16.61%和14.01%的overlap中位耗时降低，有值得分解的重复方向。
1501884的P12出现巨大中位差异和明显时间变化，适合作为对照，不能直接解释为底层有效通信重叠。
实验1/3已完成，当前没有实质数值错误；实验2用于解释，不是修复正确性或阶段报告的硬性前置。

## 具体范围与代码

新增独立jacobi_mpi_wait_diagnostic.cpp，保留原jacobi_mpi.cpp及全部历史程序/数据。
同一未插桩诊断可执行文件支持：

| 参数 | 迭代顺序 |
|---|---|
| sendrecv | 两次阻塞交换 → 按行更新 |
| immediate | Irecv/Isend → Waitall → 内部行 → 首末边界行 |
| overlap | Irecv/Isend → 内部行 → Waitall → 首末边界行 |

后两方案使用同一个update函数、相同内部/边界划分和计算顺序，只有等待位置变化。单行/双行继续采用原来的去重边界更新。新增diagnostic标签防止混入正式性能矩阵。
诊断路径新增模式分支，因此所有三方案都在本次同一诊断程序内比较；不将它们的绝对时间与旧正式作业混算基准。

关键限制：sendrecv与immediate还改变更新顺序/划分，可能改变代码生成，不能称为纯API成本。
immediate与overlap更接近等待/计算调度对照；即使后者较快，仍先报告调度收益，不能只凭总时间证明底层有效通信重叠。

## 有限执行设计

单节点12 CPU/4GB，同一次PBS分配、固定CPU列表与rank映射；30分钟上限。编译原MPI与诊断MPI各一次。
只测n=2048/P2、n=2048/P12、n=1024/P12，均K=1000/tol=0，不宣称收敛。
每个组合每方案1预热+5正式：9次预热+45次正式，共54次性能执行。不重跑串行扩展基准，不重复原92次套件。

每个组合的三种方案紧邻运行，缩短时间间隔；五轮轮换方案排列，也轮换组合块顺序。方案使用六种排列中的五种，各方案在三个位置出现1或2次；五轮不可能做到完全均衡，不声称已覆盖/平衡全部顺序。
保留预热/正式全部stdout/stderr、时间戳、完整实际顺序及计时。
不在每轮Jacobi中添加barrier或打印，不进行内部分阶段插桩。

计时前必须完成45次正确性：9个小规模案例，每例原MPI sendrecv/overlap两次、诊断三方案三次（18原+27诊断）。
案例覆盖n1单格、n2/P2每rank一行、n4/P2两行、n7/P2内部行且非整除、n7/P4单行邻居、n8/P4两行、n7/P2正容差、n12/P12单行和n24/P12双行。
n≤8比较完整网格；n12/24不修改生产输出阈值，比较由独立Python完整参考导出的全局指标，不冒充逐点输出验证。
三方案先全部通过独立参考及原生产版本对照，才进入性能阶段。

全部计划99次求解器执行，执行前rank绑定共673条（验证205、性能468）；不另外启动verify_small或其他隐藏前检。
大网格性能仅复核固定工作量和已审计的全局数值参考；mpi_wait_reference.json只含数值指标，不含或混用任何历史耗时基准。

## 本地检查状态

真实本地g++编译串行参考，8个不同工作量对照独立Python参考通过；原x+y问题的n7正容差参考324轮停止，不混用非对称问题的330轮。
源码逆向还原检查确认诊断版本除明确模式/等待位置/输出标签变化外与原MPI源码一致。
99次模拟执行、673条模拟绑定、审计与归档往返及7类损坏夹具拒绝通过；正确性超时会保留部分stdout/stderr并阻止全部性能执行。
这些模拟秒数无性能意义，不是MPI实测。本机没有可用MPI编译器/启动器，MPI构建和运行仍需PBS完成；本地没有将Bash语法写成通过，上传后必须远端bash -n。

## 本地 Windows PowerShell：上传

```powershell
Set-Location 'D:\桌面文件\NUS_sem1\DSA5208\Project3\github_ready\DSA5208_Project3'
scp .\results\mpi_wait_upload_20261028_v1.tar.gz yangaier@vanda.nus.edu.sg:dsa5208_project3/
```

## 远端 Vanda bash：解包、核验、提交一次

新目录必须不存在；mkdir或校验失败时停止，不覆盖旧目录，不在登录节点运行求解器。

```bash
cd ~/dsa5208_project3
mkdir ab_wait_20261028_v1 && tar -xzf mpi_wait_upload_20261028_v1.tar.gz -C ab_wait_20261028_v1
cd ~/dsa5208_project3/ab_wait_20261028_v1
sha256sum -c upload_sha256.txt && bash -n vanda_mpi_wait_diagnostic.pbs && bash -n vanda_modules.example.sh && qsub vanda_mpi_wait_diagnostic.pbs
qstat -u yangaier
```

记录qsub返回的真实完整ID。JOB_ID替换成该ID，不猜新ID/节点/CPU。
日志每行PASS correctness为验证进展；性能seq从0到53。不能把seq=53当作PBS最终状态。

```bash
tail -n 30 results/Vanda_mpi_wait_JOB_ID/run.log
qstat -xf JOB_ID
```

## 结束后：远端保存最终qstat，再本地完整下载

看到job_state=F后，无论成功失败都保留最终状态。成功还需Exit_status=0、RUN_STATUS=PASSED/JOB_EXIT_STATUS=0。
若失败，先保留原件分析，不自动重提。

远端Vanda bash：

```bash
qstat -xf JOB_ID > ~/dsa5208_project3/ab_wait_20261028_v1/results/Vanda_mpi_wait_JOB_ID/qstat_full.txt
```

本地Windows PowerShell：

```powershell
$waitJobId = 'JOB_ID'
if (Test-Path -LiteralPath ".\results\Vanda_mpi_wait_$waitJobId") { throw '同名结果已存在，请勿覆盖' }
scp -r "yangaier@vanda.nus.edu.sg:dsa5208_project3/ab_wait_20261028_v1/results/Vanda_mpi_wait_$waitJobId" .\results\
```

下载完成后由Codex完整审计、逐文件归档，生成三方案逐轮图和中文解释，并合入阶段报告。也可手动调用（输出目录必须不存在）：

```powershell
python mpi_wait_diagnostic.py audit --results "results/Vanda_mpi_wait_$waitJobId" --out-dir "evidence/vanda_${waitJobId}_mpi_wait" --plots
```

## 预先约定的结论与停止边界

| 观察 | 可以报告 | 不能据此报告 |
|---|---|---|
| overlap与immediate接近 | 未观察到清楚的等待位置收益 | 非阻塞方案普遍没有价值 |
| overlap持续较快 | 本次配置存在等待/计算调度收益 | 已完整证明底层通信重叠机制 |
| immediate与sendrecv不同 | 接口、更新顺序/划分等综合差异 | 纯API成本已被隔离 |
| 三方案再次随轮次大变或方向不稳 | 诊断受时间变化影响，解释不确定，保留全样本 | 删除慢段、挑好节点或反复提交直到变好 |

不设置按性能快慢剔样本的规则。不增加新的CPU分配、节点诊断、规模、进程矩阵或插桩作业。
完成这一项即回到汇总与报告；没有稳定收益也是有效结果，不再因此追加同类实验。
