# DSA5208 Project 3 — Jacobi MPI + OpenMP

## 最新共享状态：2026-10-28

A的串行基准/正确性、B的纯MPI及三项补充实验均已完成并审计。本轮不再追加实验，进入10月29日阶段报告的人工确认；C/OpenMP/混合新实验、多节点、弱扩展、二维分区与内部插桩均不开展。

**所有成员先读[本次同步说明](docs/TEAM_SYNC_2026-10-28.md)**：包括拉取步骤、阅读顺序、七份完整原始包的校验/解包、离线统计重建，以及尚需本人确认的信息。

| 入口 | 当前用途 |
|---|---|
| [英文阶段报告](docs/AB_STAGE_REPORT_DRAFT_2026-10-28.md) | 已校核精简，未获成员最终确认，未发送 |
| [中文结果梳理](docs/AB_RESULTS_SUMMARY.md) | 历史与本轮结果、解释及边界；顶部最新状态优先 |
| [最终证据入口](evidence/ab_final_2026-10-28/README.md) | 四作业五扩展数据集与独立等待诊断，始终分开统计 |
| [报告校核/人工确认](docs/AB_REPORT_REVIEW_2026-10-28.md) | 数值、计时、双基准、图表检查及成员待填项 |
| [进度清单](docs/AB_PROGRESS_CHECKLIST.md) | 三项补充完成；下方过程记录保留为历史 |
| [原始包清单](evidence/ab_final_2026-10-28/raw_archives_manifest.json) | 七份完整包、2271文件的既有审计记录及SHA-256 |

后续A/B正式串行基准是 jacobi_serial_row_update.cpp。现有Makefile默认串行目标仍保留历史 jacobi.cpp，不能将默认构建误当新A/B基准。原源码和原始数据均保留，没有用新基准重算旧作业加速比。

主要结论：同分配、固定绑定仍可能出现大幅时间变化与非单调扩展；2048/P2等待位置诊断未见明确收益，P12仅约1%的小幅观测，不证明统计显著或底层有效通信重叠。全部性能固定1000轮，不宣称收敛。原1498804完整原始包仍未取得；以下相关早期描述不代表已完成它的完整原件审计。

## 既有实现与操作指南

下列通用编译、Atlas/Vanda接入步骤作为参考保留，不构成本轮新增实验任务。个人代码理解、真实贡献和姓名学号须成员本人确认。

**成员 B 从 [MPI/HPC 交付与运行指南](docs/MEMBER_B.md) 开始**，包含 Mac 编译、验证、HPC 账号/VPN、Vanda 上传、作业配置、提交和验收。

**第一次在学校 Atlas 系统操作，请先看 [Atlas 完整操作指南](docs/ATLAS.md)**：包含账号/网络、SSH 登录、Windows/Mac 上传源码、PBS 提交与状态查询、结果验收和下载，每一步标明在本机还是 Atlas 执行。

## 文件入口

| 文件/目录 | 用途 |
|---|---|
| `jacobi_mpi.cpp` | MPI/混合 Jacobi；sendrecv 与 overlap 两种通信策略 |
| `Makefile` | 编译 serial/openmp/mpi/hybrid 四种程序 |
| `verify_parallel.py` | MPI/混合版对照串行及独立小网格验证 |
| `analyze_results.py` | 审计下载的完整集群结果，生成表格、分析和可选图表 |
| `benchmark_parallel.py` | 重复计时、原始输出、加速比和效率汇总 |
| `atlas_jacobi.pbs` / `vanda_jacobi.pbs` | 正式算法作业模板（Vanda 模块/资源待现场核对） |
| `jacobi.cpp` | 同一源码分别编译串行和 OpenMP Jacobi |
| `verify_small.py` | 手算、精确解、残差、边界及线程一致性验证 |
| `prepare_team_references.py` | 生成 10 个经检查的串行参考；可选本机规模试跑 |
| `team_contract_v0.1.json` | 机器可读的参数与输出约定 |
| [团队参数约定](docs/TEAM_CONTRACT.zh-CN.md) | 推荐数值、MPI 对接约定、计时与验收口径 |
| [协作与交接](docs/HANDOFF.md) | A/B/C 分工、接收验收及下一步 |
| [学校 Atlas 完整操作指南](docs/ATLAS.md) | SSH → SCP 上传 → qsub → qstat → 验收 → SCP 下载，含 Windows/Mac 命令 |
| `reference/` | 已有本机串行数值参考与单次性能试跑 |
| `evidence/` | 已有 Atlas 串行小样本及 MPI/OpenMP 环境检查结果 |
| [AI 使用记录](docs/AI_USAGE.md) | AI 贡献与已有人工操作/验证边界 |
| [整理说明](docs/FILES.md) | 共享文件、保留在原工作区的材料及完整性说明 |

## 依赖

- 支持 C++17 的编译器；OpenMP 构建还需编译器支持 `-fopenmp`。
- Python 3.10 或更新版本用于验证，脚本只使用标准库，无需 pip 安装包。
- MPI/混合版需要 MPI-3 或更新版本；OpenMP 混合版需要 MPI_THREAD_FUNNELED。串行程序和参考生成不需要 MPI。

已验证环境包括 Windows GCC 12.2、WSL GCC 11.4/Open MPI 4.1.2、Atlas GCC 12.2/Open MPI 4.1.5。这里列的是已保存的历史验证环境，不保证集群当前模块配置不变。

## Windows 快速开始

在本仓库根目录打开 PowerShell，先编译再验证：

```powershell
New-Item -ItemType Directory -Force build | Out-Null
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic jacobi.cpp -o build/jacobi_serial.exe
if ($LASTEXITCODE -ne 0) { throw 'Serial build failed' }
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp jacobi.cpp -o build/jacobi_omp.exe
if ($LASTEXITCODE -ne 0) { throw 'OpenMP build failed' }
python verify_small.py build/jacobi_serial.exe build/jacobi_omp.exe
if ($LASTEXITCODE -ne 0) { throw 'Validation failed' }
```

生成新参考时使用一个尚不存在的输出目录：

```powershell
python prepare_team_references.py --executable build/jacobi_serial.exe --out-dir results/my_reference_run
```

`--pilot` 会额外运行 n=256/512/1024/2048 的固定 1000 轮试跑。日常生成的 `build/`、`results/` 已加入 `.gitignore`；经审查的共享结果放在 `reference/` 或 `evidence/`。

## Linux / WSL 快速开始

```bash
mkdir -p build
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic jacobi.cpp -o build/jacobi_serial &&
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic -fopenmp jacobi.cpp -o build/jacobi_omp &&
python3 verify_small.py build/jacobi_serial build/jacobi_omp
```

Mac 可以先用支持 C++17 的 `c++` 编译串行版；OpenMP 编译器与运行库由 C 确认，不能假定系统默认编译器支持 `-fopenmp`。Python 验证方式相同。

## 统一参数和结果

调用形式：`executable n max_iters tolerance`。n 是每边内部点数，完整网格为 `(n+2)×(n+2)`。固定边界为 u=x+y，内部初值为零，使用 double。

| 用途 | n | max_iters | tolerance |
|---|---:|---:|---:|
| 开发默认 | 16 | 100000 | 1e-12 |
| 共同收敛验收 | 32 | 100000 | 1e-12 |
| MPI 不整除分区对接 | 7 | 31 | 0 |
| MPI 全局收敛检查 | 31 | 100000 | 1e-12 |
| 性能试跑起点 | 1024 | 1000 | 0 |

正容差根据最大更新量停止；容差 0 表示严格运行指定轮数，不声称已经收敛。收敛状态、更新量、真误差和残差分别检查。

n=32 的本机串行参考为 5006 轮，最大误差约 2.195e-10，残差约 4.330e-9，边界误差 0。n=7、固定 31 轮时 `grid[4][4]=0.8644978247466497`。小规模收敛验收建议真误差≤1e-8、残差≤1e-7；固定轮数不使用这些收敛门槛。

## 验证证据的范围

- `reference/reference_results.json`：10 个串行案例通过；小网格另与独立 Python 二维实现核对。
- `reference/local_pilot.json`：本机单次规模试跑，不能当作 Atlas 性能结果或重复实验中位数。
- `evidence/atlas_serial/`：2026-10-23 的 n=1/2/16/32 原始数值输出。
- `evidence/atlas_smoke/`：MPI 2/4/12 进程、OpenMP 4/12 线程环境检查。

共享参考汇总中的命令路径已改为相对路径，数值对象保持原样；原件校验值和变化说明保存在汇总文件中。完整原始日志在原工作区保留。历史参考使用的参数状态快照与当前 A 已采纳状态不同，数值参数一致。

MPI/混合本地验证的历史记录见 evidence/member_b_local/。当前A/B已覆盖1024/2048、串行诊断和全部三项补充；以顶部及[同步说明](docs/TEAM_SYNC_2026-10-28.md)为准。本轮只做成员审阅，不要求重新运行集群作业。
