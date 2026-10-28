# 2026-10-28：A/B 有限补充实验（实验1优先，实验3随后）

## 当前状态更新：1501884已完成并完整审计

2026-10-28：1501884.stdct-mgmt-02在IN-005完成，PBS F/退出0；180次性能执行、一次92条结构化验证和31次非对称逐点验证均已复核。完整原始包646文件逐成员校验通过。当前请看[经复核分析](../evidence/vanda_1501884_ab_supplement/analysis_reviewed.md)和[阶段报告草稿](AB_STAGE_REPORT_DRAFT_2026-10-28.md)。本页下方为原提交前设计与复现操作，保留原文；当前不需要再按它提交新作业。源码上传包和集群快照保留原始版本。

当前：实验1/3的代码、PBS脚本和本地工具检查已准备，尚未提交新Vanda作业。历史源代码、原始结果和未提交修改保留。实验2暂缓，收到本轮数据后按半天预算决定；不因差异不显著而无限追加实验。目标仍为10月29日完成阶段报告整理，不发送邮件、不提交或推送Git。

## 实际新增文件

- `benchmark_dual_scale.py`：复用原 `benchmark_parallel.py` 的命令构造与绑定检查。单次入口，不重复启动验证或预热。
- `vanda_ab_dual_scale.pbs`：单节点12 CPU/4GB、30分钟上限；冻结源码快照、各性能程序编译一次；原验证套件一次；双规模计时；独立非对称验证。
- `jacobi_serial_asymmetric.cpp`、`jacobi_mpi_asymmetric.cpp`、`verify_asymmetric.py`：独立正确性副本。旧性能源码不改。
- `audit_ab_supplement.py`：新目录结构专用审计；复用原统计/绘图和小网格验收，但另外核对双规模顺序、绑定、数值、工作量、原始清单及归档。
- `check_ab_supplement_local.py`：合成夹具和失败路径检查；不是HPC实验。

原 `analyze_results.py` 假定单个 `benchmark/summary.json` 包含一个规模的groups，不能直接用于新顶层结构。请使用新审计入口，不将两个规模合并后计算基准。

## 实验1精确设计

n=1024、2048；各K=1000、tol=0；串行及MPI P=1/2/4/12 × sendrecv/overlap，每规模九配置。
各配置预热一次、正式九次：总180次性能执行，含18次预热和162次正式计时。每规模90次。性能执行产生780条exec前rank绑定；验证运行不计入这780条。
两规模共享同一性能程序、同一CPU列表；rank r固定列表第r项，串行与rank0用同一CPU。继承mask必须恰好12 CPU，否则停止，不猜CPU编号。

预热两个规模各一个九配置块；正式轮0、2、4、6、8先1024再2048，轮1、3、5、7先2048再1024。每轮每规模的九配置循环左移轮号位。保存完整global sequence、scale_block、within_scale_position、repeat_index、命令和起止时间。
每规模每配置在内部九个位置各出现一次；跨规模十八个位置未完全平衡（规模先后为5/4），不作相反声明。
每规模分别使用本作业串行中位数和同策略MPI P=1中位数，不与历史作业混算。原始异常值全部保留。

源码快照、构建命令、源/程序SHA-256、模块/运行环境、CPU mask、节点文件、PBS初始状态和逐次stdout/stderr均保留。最终qstat需作业结束后手工保存。同次分配仍不能排除共享节点干扰、频率或随时间变化。

## 实验3案例与覆盖

坐标约定：x=列/(n+1)，y=行/(n+1)，解析函数u=x+2y+xy；二阶纯偏导均为0。上下/左右物理边界不同，可辨别x/y交换。串行/MPI边界、最终解析误差、MPI收集后的物理边界和Python参考同步调整。完整网格输出仅在独立副本中放宽到n≤32，未改变性能程序。

| 案例 | n / K / tol | MPI P | 主要覆盖 |
|---|---|---|---|
| single_cell | 1 / 1 / 0 | 1 | 单格、物理边界、奇数swap |
| two_rows | 2 / 2 / 0 | 1,2 | 每rank一行/两行、偶数swap |
| uneven | 7 / 31 / 0 | 1,2,4 | 4+3及2+2+2+1分区、内部行、halo |
| two_per_rank | 8 / 2 / 0 | 4 | 每rank两行、没有内部行 |
| twelve_single | 12 / 3 / 0 | 12 | 12个rank各一行 |
| twelve_double | 24 / 4 / 0 | 12 | 12个rank各两行 |
| converged | 7 / 10000 / 1e-12 | 1,2,4 | 独立停止轮数、全局停止、残差halo刷新 |

共7次串行、24次MPI（两策略），31次完整小网格验证。每个输出均比完整网格、独立迭代轮数及四项数值指标；正容差例另要求max_error≤1e-8、residual_inf≤1e-7。这些是小规模验收阈值，不推广到1024/2048；固定轮数例不要求收敛。未新增非对称大规模性能矩阵。

## 本地检查及边界

真实本地：g++串行编译；上述7个非对称串行案例全部完整逐点通过，收敛例330轮，误差约1.25e-11、残差约2.52e-10。
工具检查：模拟执行完整180条计划、780条绑定、新审计全流程和归档逐成员往返；7种破坏夹具均拒绝，包括坐标转置。合成秒数无性能意义。
Python语法检查、脚本LF及内嵌Python语法检查与Git diff空白检查在本机完成。原三份性能C++源码逐字节匹配1500271归档。
本机没有可用mpicxx/mpirun；WindowsApps Bash启动失败，w64devkit Bash alias也失败。因此没有将MPI编译/运行或bash -n写成通过。请在远端做下列语法检查；计算只通过PBS进行。

## 本地 Windows PowerShell：上传源码包

操作目录为本仓库。只需上传生成的源码包，不依赖Git提交。新远端目录与旧ab_diagnostic分开。

```powershell
Set-Location 'D:\桌面文件\NUS_sem1\DSA5208\Project3\github_ready\DSA5208_Project3'
scp .\results\ab_supplement_upload_20261028_v1.tar.gz yangaier@vanda.nus.edu.sg:dsa5208_project3/
```

## 远端 Vanda bash：解包、校验、提交

先保持学校VPN/amgr认证可用。不在登录节点运行求解器或计时Python脚本。
新目录必须不存在；mkdir报错时停止，不覆盖已有实验目录。SHA校验或bash检查失败时停止并保留输出。

```bash
cd ~/dsa5208_project3
mkdir ab_supplement_20261028_v1 && tar -xzf ab_supplement_upload_20261028_v1.tar.gz -C ab_supplement_20261028_v1
cd ~/dsa5208_project3/ab_supplement_20261028_v1
sha256sum -c upload_sha256.txt && bash -n vanda_ab_dual_scale.pbs && bash -n vanda_modules.example.sh && qsub vanda_ab_dual_scale.pbs
qstat -u yangaier
```

保留qsub返回的完整ID（含后缀），下面所有JOB_ID都替换成真实ID。不猜新ID、节点或CPU。
若语法检查失败不要提交；若作业失败，保留全部目录，先交回分析，不直接重复提交。

## 远端 Vanda bash：结束后保存最终状态

```bash
tail -n 30 ~/dsa5208_project3/ab_supplement_20261028_v1/results/Vanda_ab_dual_JOB_ID/run.log
qstat -xf JOB_ID
```

看到job_state=F后再保存最终状态；成功还需Exit_status=0及日志末尾RUN_STATUS=PASSED/JOB_EXIT_STATUS=0。即使失败也保存最终qstat与完整原始目录。

```bash
qstat -xf JOB_ID > ~/dsa5208_project3/ab_supplement_20261028_v1/results/Vanda_ab_dual_JOB_ID/qstat_full.txt
```

## 本地 Windows PowerShell：下载完整目录

把下行变量替换为真实完整ID。不将新下载目录合并到已有同名目录；若已存在，先核对状态，勿覆盖。

```powershell
$abJobId = 'JOB_ID'
if (Test-Path -LiteralPath ".\results\Vanda_ab_dual_$abJobId") { throw '同名结果已存在，请先核对，不要覆盖' }
scp -r "yangaier@vanda.nus.edu.sg:dsa5208_project3/ab_supplement_20261028_v1/results/Vanda_ab_dual_$abJobId" .\results\
```

下载结束后告知目录/真实ID，由Codex核对原件、统计、归档并更新中文分析和历史比较。可手动调用：

```powershell
python audit_ab_supplement.py --results "results/Vanda_ab_dual_$abJobId" --out-dir "evidence/vanda_${abJobId}_ab_supplement" --plots
```

审计输出目录必须不存在；归档默认位于results/raw_archives，已存在时只验证逐文件内容，不覆盖。
新输出包括audit.json、performance_audited.csv、communication_audited.csv、中文analysis.md和分规模图。审计成功仍需人工对照历史三轮并目视复核图表，更新AB_RESULTS_SUMMARY、进度和AI记录，不能只看PASS。

## 本轮停止点与实验2

实验1/3取得完整原始结果后优先汇总：同分配控制规模比较及非对称正确性可加强；共享节点干扰、缓存/带宽/NUMA根因和底层有效通信重叠仍不能仅由这些数据证明。
实验2若剩余时间允许，再用独立诊断程序仅测2048/P2、2048/P12、1024/P12，各三策略1预热+5正式，先正确性后性能。不将诊断结果混入正式矩阵，不默认开展内部计时。当前未实现/提交实验2，不把它标为完成。
