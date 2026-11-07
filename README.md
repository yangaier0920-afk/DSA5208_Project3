# DSA5208 Project 3 — Jacobi / 3D Poisson

**2026-11-07 技术收尾完成：**A/B/C 已合并为 [15 页英文审阅报告](output/pdf/DSA5208_Project3_Review_Report.pdf)，附 [独立源码/CSV/图表交付包](output/DSA5208_Project3_Review_Package.zip)。已补同内存容量族的扩展与 144 核独立复核；20 组扩展 + 8 组成对比较共 84 次正式观测。姓名、学号和个人贡献按用户要求暂不加入；432/720 可选点仍排队，未上传 Canvas。
**2026-11-07 B 更新：**新增笛卡尔 2D/3D MPI、混合并行及正式矩阵，已通过本地与 Vanda 真实两节点验证。当前运行状态和已验收数值见 [B 实测结果](docs/B_RESULTS_2026-11-07.md)，设计及章节见 [B 章节](docs/final_B_mpi.md)，编译/运行见 [B README](b_mpi/README.md)。未完成作业不计为已完成实验。

**更新日期：2026-11-05。A 的数值研究及 2D/3D 串行规模分析已完成；B/C 按最新评分分工推进。**

**所有成员先读 [最新任务清单与 A/B/C 分工](10.30会议讨论要点与ABC分工.md)。**
该文件给出了共同公式、参数、个人配置、交付日期及资源阻塞时的处理规则。
早期文档中的“多节点/弱扩展/C 暂缓”和“本轮不再追加实验”属于 10 月 28 日阶段，
当前按最新分工执行。

## 1. 目前做到哪里

| 内容 | 当前状态 | 入口 |
|---|---|---|
| 旧 2D 串行、MPI 与三项补充实验 | 已完成并保存审计材料，可直接用于历史结果和基准说明 | [A/B 结果](docs/AB_RESULTS_SUMMARY.md)、[原始证据入口](evidence/ab_final_2026-10-28/README.md) |
| A：新 3D 串行、残差及停止逻辑 | 已实现，本地基本检查通过 | [A 完成记录](docs/A_PROGRESS_2026-11-01.md)、[本地证据](evidence/a_local_2026-11-01/README.md) |
| A：数学说明、旧串行差距解释 | 英文草稿已完成 | [A 报告草稿](docs/final_A_numerics.md) |
| A：正式收敛/精度及旧 2D 终点诊断 | 已完成：三个 3D 网格收敛、二阶精度；旧 2D 的 1000 轮未达标 | [11/3 完成记录](docs/A_PROGRESS_2026-11-03.md)、[Vanda 证据](evidence/vanda_1512708_a_numerics/README.md) |
| A：2D 非零源项及固定 K 串行规模分析 | 已完成：10 配置、30 正式样本；2D/3D 指数约 2.066/2.995 | [11/5 完成记录](docs/A_PROGRESS_2026-11-05.md)、[规模分析](docs/A_SERIAL_SCALING_2026-11-05.md) |
| B：新 3D MPI、强扩展、弱扩展、有限混合 | 按最新分工推进；本仓库当前没有据此确认的新正式结果 | [B 执行卡](10.30会议讨论要点与ABC分工.md) |
| C：OpenMP CPU/GPU | 按最新分工推进；本仓库当前没有据此确认的真实 GPU 新结果 | [C 执行卡](10.30会议讨论要点与ABC分工.md) |

A 的正式 Vanda 数值数据已保存：作业 walltime 34 秒，五案例求解/迭代计时合计 23.453 秒。
3D 观察阶数为 2.0131、2.0032；旧 2D 两种规模在 1000 轮后相对残差约 0.005。
B/C 状态由各自负责人交付后更新，不根据任务已分配就标记为完成。

## 2. 每个人负责什么，现在先做什么

| 成员 | 独立负责的路线 | 维护期间先完成 | 恢复后的核心实验 | 交付 |
|---|---|---|---|---|
| **A** | 数学、数值研究、固定 K 串行规模分析；最终合稿 | 已完成2D补充和两批Vanda实验 | 核心实验及图文已就绪，等待B/C完整章节后整合 | [最新完成记录](docs/A_PROGRESS_2026-11-05.md) |
| **B** | 3D MPI、强扩展、弱扩展、有限 MPI+OpenMP | 三维块分区、halo、PBS、矩阵及统计脚本 | 强扩展 16 配置，含代表规模目标 720 核；64³/rank 弱扩展；256³ 固定 72 核混合配比 | 11/6 强扩展；11/7 弱扩展/混合 |
| **C** | 单机 OpenMP CPU 与单 GPU offload | CPU/target 内核、设备数据驻留、编译及计时脚本 | 64³/128³/256³；每规模 CPU T=1、T=Tc 与单 GPU，共 9 配置 | 11/6 GPU；11/7 CPU/GPU 对照 |

**B/C 可以立即独立开发，无需等待 A 的正式结果。**共同定义已写在分工文档中：
B 用自己的 MPI P1/72 核基准；C 测同一 GPU 节点上的 CPU 对照。

每个人负责自己模块的代码、脚本、原始输出、CSV、图、分析和 README。
弱扩展及 MPI+OpenMP 均归 B；C 专注 OpenMP CPU/GPU。
每人随运行做本人基本检查，通过后直接整理；不安排跨人结果复核、
交叉复现或额外独立性能复测。A 收各人成稿进行合并。

## 3. 维护窗口与交付日期

时间均为新加坡时间/北京时间（UTC+8），实际恢复以学校通知为准。

| 时间 | 安排 |
|---|---|
| 10/29 18:00 起 | 公告停止作业调度 |
| 10/31 06:00 起 | 公告停止访问，终止运行中的作业；维护期间本地开发与准备材料 |
| 11/2 17:00 | 计划恢复；各人检查自己路线的环境/队列 |
| **11/3–11/7** | 核心正式实验窗口 |
| 11/8–11/9 | 补缺失核心点或明确错误；11/9 交各人图文初稿 |
| **11/10** | 冻结数据、源码和章节 |
| 11/11 | 合稿、排版、本人文件完整性检查 |
| **11/12 18:00 前** | 内部提交目标；课程要求为 11/13 之前，Canvas 精确时刻仍需本人确认 |

CPU/GPU 申请由提交者登记，避免全组配额冲突。大核数和 GPU 资源恢复后的
实际可用性须各自确认；维护时间不是已完成恢复的保证。

## 4. 全组统一的数值与测量口径

- 新增主问题：**poisson3d_mms**，−Δu=f，Ω=(0,1)³；
  u*=x+2y+3z+sin(πx)sin(2πy)sin(3πz)，
  f=14π²sin(πx)sin(2πy)sin(3πz)，边界 u=x+2y+3z。
- double、内部零初值、七点差分、双缓冲；nx/ny/nz 是内部点数，
  各方向 h=1/(n+1)，RHS 预计算。长方体网格按各自方向步长计算。
- B/C 性能主线固定 **K=1000**，不提前停止；最终输出真实相对 L2 残差 R1000。
  固定工作量本身不表示已收敛。
- A 求解每 10 轮检查真实相对 L2 残差；主收敛标准 1e−8，
  精度实验继续到 1e−10，上限 100000 轮。
- B/C 每个性能配置 **1 次预热 + 3 次正式测量**，报告中位数及 min/max；
  保留有效负结果与波动。
- 完整数学、时间范围、本人基本检查和各人矩阵以
  [最新分工第 4–8 节](10.30会议讨论要点与ABC分工.md)为准。

## 5. A 新增文件与运行入口

| 文件 | 用途 |
|---|---|
| [jacobi_numerics.cpp](jacobi_numerics.cpp) | A 独立串行入口：新 3D Poisson、旧 2D 残差诊断、fixed/solve |
| [run_a_numerics.py](run_a_numerics.py) | 本人小案例 smoke / 正式 A2 五案例 formal；输出目录必须是新目录 |
| [analyze_a_numerics.py](analyze_a_numerics.py) | 读取已有结果，生成残差曲线与精度表 |
| [vanda_a_numerics.pbs](vanda_a_numerics.pbs) | 本次 Vanda 正式 A2 使用的作业脚本（已完成） |
| [A_NUMERICS_README.md](docs/A_NUMERICS_README.md) | Windows/Linux 编译、参数、运行、输出与恢复后步骤 |
| [final_A_numerics.md](docs/final_A_numerics.md) | 数学、算法、旧基准解释、本地检查及正式 Vanda 收敛/精度结果 |

A 的程序只需 C++17；运行脚本仅用 Python 标准库，绘图需要 matplotlib。
Linux 可用 make numerics 构建新入口，不触发旧 MPI/OpenMP 构建。

Windows 本人小案例示例（并非 B/C 开工步骤，已有结果无需重跑）：

~~~powershell
New-Item -ItemType Directory -Force build | Out-Null
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic jacobi_numerics.cpp -o build/jacobi_numerics.exe
python run_a_numerics.py --binary build/jacobi_numerics.exe --suite smoke --out-dir results/my_A_smoke
python analyze_a_numerics.py results/my_A_smoke
~~~

build/、results/ 为本地生成目录，已被 Git 忽略；供团队共享的精选证据放 evidence/。

## 6. 各人材料交到哪里

| 成员 | 结果目录 | 章节 |
|---|---|---|
| A | results/final_202611/A_numerics/ | docs/final_A_numerics.md |
| B | results/final_202611/B_mpi/ | docs/final_B_mpi.md（由 B 创建） |
| C | results/final_202611/C_openmp/ | docs/final_C_openmp.md（由 C 创建） |

各人将需要上传的原始记录、配置、汇总与图整理到 evidence/ 下自己的批次目录，
连同源码、运行说明和章节一起提交。不要把未运行的配置写成实验结果。
图表正文按问题、规模、实现和资源组织；job ID 放原始记录。

每位成员贡献和 AI 使用说明由本人填写。11/9 提交可直接进入报告的图文初稿，
11/10 定稿，不把全组绘图或原始数据调查集中给 A/C。

## 7. 历史材料与操作指南

以下用于旧 2D 实现、已有结果及集群操作参考。
其中旧任务分派、停止规则和“暂缓”安排不覆盖本页及最新分工。

| 入口 | 用途 |
|---|---|
| [MPI/HPC 操作指南](docs/MEMBER_B.md) | 早期 MPI 编译、上传、PBS、下载流程 |
| [Atlas 操作指南](docs/ATLAS.md) | 账号/网络、SSH/SCP、PBS 与下载 |
| [10/28 同步说明](docs/TEAM_SYNC_2026-10-28.md) | 旧原始包、离线统计和阶段材料 |
| [A/B 结果分析](docs/AB_RESULTS_SUMMARY.md) | 旧结果、基准诊断与波动解释 |
| [10/28 最终证据](evidence/ab_final_2026-10-28/README.md) | 历史归档、统计和原始包入口 |
| [旧团队参数合同](docs/TEAM_CONTRACT.zh-CN.md) | 旧 2D 接口与最大更新量停止规则 |
| [AI 使用记录](docs/AI_USAGE.md) | 早期 AI/人工工作记录；新工作各人补充 |

旧 jacobi.cpp 是历史串行/OpenMP 源码，jacobi_mpi.cpp 是历史 2D MPI/混合源码。
Makefile 的默认 all 仍构建这些旧程序。旧 A/B 修正后的串行基准为
jacobi_serial_row_update.cpp；新 A 数值入口是 jacobi_numerics.cpp。
这三者应按对应问题和实验区分，不能把旧默认构建当成新 3D 程序，
也不能把新基准计时拿去重算不同历史作业的加速比。
