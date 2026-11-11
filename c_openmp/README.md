# C 模块使用说明：OpenMP CPU 与单 GPU Jacobi

**本模块已完成正式实验，组员可以直接查看结果或复现图表，无需重新申请 GPU。** 实验范围为三维 Poisson、固定 1000 次 Jacobi 迭代，比较 CPU 单线程、CPU 12 线程与单块 NVIDIA A40。

更新日期：2026-11-11。此目录是当前版本；`reference/` 和结果中的源码快照用于历史追溯。桌面的 `03_C` 是指向项目 `c_openmp` 的快捷入口，两者是同一份文件。

## 1. 第一次打开：先看这三个入口

| 你的目的 | 打开哪里 |
|---|---|
| 理解方法、实验设置、验证与结论 | **[中文成果说明](docs/C_RESULTS_README_zh.md)** |
| 使用图、CSV 和图注 | [下方成果文件表](#3-正式成果文件在哪里) |
| 重新生成相同图表 | [第 4 节](#4-复现图表无需-vanda-或-gpu) |
| 从源码重新编译和运行 | [第 5、6 节](#5-可选本地-cpu-构建与正确性检查) |

GitHub 中 C 的文件统一放在 `c_openmp/`。克隆仓库后先 `cd c_openmp`；作者桌面的 `03_C` 只是本机快捷入口。

正式矩阵、CPU 单线程同机对照、GPU 分段计时和 CPU 线程扩展均已完成。四个有效作业的 PBS 退出码为 0。英文 C 章节已纳入补测和汇编证据。成员贡献与 AI 声明已有草稿，待本人补姓名、学号并核实内容。[英文 C 章节](docs/final_C_openmp.md) · [评语处理表](nov10_followup/final_results_20261110/REVIEW_RESPONSE_20261111.md) · [合稿包](nov10_followup/final_results_20261110/README.md)

## 2. 实验做了什么，得到什么结果

- 内部网格：64³、128³、256³；double 精度，每次固定 K=1000，不提前停止。
- 对照：CPU T=1、CPU T=12、单 A40 GPU；同一正式节点内依次运行。
- 每配置 1 次预热 + 3 次正式，共 36 次性能调用；正式统计只使用 27 次 measured。
- GPU 一次运行同时得到 resident（数据驻留后迭代）和 end-to-end（含设备数据区建立、传输及释放）两种时间，不是两套独立配置。
- 18 项小网格检查通过；6 组 CPU/GPU 全网格比较最大差均为 0。完整验证表见中文成果说明。

### 正式时间：三次测量的中位数，单位秒

| 内部网格 | CPU1 | CPU12 | GPU resident | GPU end-to-end |
|---|---:|---:|---:|---:|
| 64³ | 0.802221 | 0.124330 | 0.053188 | 0.156299 |
| 128³ | 6.330078 | 0.867985 | 0.204269 | 0.308162 |
| 256³ | 51.450687 | 4.783182 | 1.627774 | 1.779479 |

相对 CPU12，GPU end-to-end 速度比分别为 **0.80×、2.82×、2.69×**；大于 1 表示 GPU 更快。64³ 的 GPU 端到端仍慢于 CPU12，128³ 和 256³ 已更快。GPU resident 相对 CPU12 的速度比为 2.34×、4.25×、2.94×，不能写成随规模单调增加。

平台：Vanda 的 GN-A40-024，Intel Xeon Platinum 8452Y + NVIDIA A40（46068 MiB），驱动 575.57.08；NVHPC 24.7 / CUDA 12.3.0 / GCC 13.2.0。PBS 分配 36 个 CPU 核和 1 GPU，CPU 多线程基准按实验协议使用 **Tc=12**，不是 36 线程。

本结果是固定工作量比较，不代表三个规模均已收敛。resident 包括 kernel 启动和同步，end-to-end 与 resident 的差也不能解释成纯 PCIe 传输耗时。早期 pilot 来自另一节点，不参与当前图表。

## 3. 正式成果文件在哪里

**所有当前成果都在本目录中；`deliverables/` 是仓库内可直接使用的精简成果，完整原始证据仍在本机 `results/` 中。** 以下链接可以直接打开；表格与图的唯一正式来源是同一批次的 `deliverables/formal_20261106/analysis/`。

| 成果 | 文件 |
|---|---|
| 中文完整说明 | [C_RESULTS_README_zh.md](docs/C_RESULTS_README_zh.md) |
| 耗时图 | [runtime.png](deliverables/formal_20261106/analysis/runtime.png) · [矢量 PDF](deliverables/formal_20261106/analysis/runtime.pdf) |
| 速度比图 | [speedup.png](deliverables/formal_20261106/analysis/speedup.png) · [矢量 PDF](deliverables/formal_20261106/analysis/speedup.pdf) |
| 时间统计：中位数及 min/max | [summary.csv](deliverables/formal_20261106/analysis/summary.csv) |
| CPU 效率与四种 GPU 速度比 | [speedups.csv](deliverables/formal_20261106/analysis/speedups.csv) |
| 报告用验证简表 | [validation_summary.csv](deliverables/formal_20261106/analysis/validation_summary.csv) |
| 图注 | [figure_captions.md](deliverables/formal_20261106/analysis/figure_captions.md) |
| 原始 36 行性能样本 | [samples.csv](deliverables/formal_20261106/samples.csv) |
| 完成状态 | [run_status.json](deliverables/formal_20261106/run_status.json) |

runtime 图横纵轴均为对数，误差棒为三次真实样本 min/max，不是置信区间。speedup 图横轴为对数，纵轴为线性；左、右面板分别以 CPU1、CPU12 为分子，分母是图例标明的 GPU 时间，使用中位数之比。PNG 为 300 dpi，合稿时可优先使用矢量 PDF。

## 4. 复现图表：无需 Vanda 或 GPU

前提：Python 3.12 是本次使用的绘图环境版本；有完整的源码目录和 `deliverables/formal_20261106/`。组员在自己机器打开**本 README 所在目录**执行以下命令，不需要使用作者的绝对路径。完整仓库入口为 `c_openmp/`，所有命令均从该目录执行。

第一次准备环境（macOS / Linux）：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-plots.txt
```

生成统计表和两张图：

```bash
c_data='deliverables/formal_20261106'
.venv/bin/python analyze_c.py "$c_data"
```

只生成统计表时无需安装 matplotlib：

```bash
python3 analyze_c.py deliverables/formal_20261106 --tables-only
```

成功后显示 `Analysis saved: .../deliverables/formal_20261106/analysis`。输出为 `summary.csv`、`speedups.csv`、`summary.md`、`runtime.png/.pdf`、`speedup.png/.pdf`、`figure_captions.md`、`plot_metadata.json`。已有验证简表也在该目录中；它由本次验证记录整理，绘图脚本不会重做求解或重新生成验证数据。

Windows 可使用 `.venv\Scripts\python.exe` 替换 `.venv/bin/python`。整个分析过程读取已完成样本，只重写派生表图，不启动求解器。若只收到代码而没有 deliverables 数据，请先从组内获取该正式 data 目录。

## 5. 可选：本地 CPU 构建与正确性检查

这些步骤用于组员理解和核对实现，不能代替 Vanda 正式 GPU 数据。本次结果已经完成，无需为使用图表执行本节。

**作者的 Apple Silicon Mac** 已有 Homebrew LLVM 和 libomp，build.sh 使用 `/opt/homebrew/opt/` 路径：

```bash
bash build.sh mac
build/jacobi_c_cpu --backend cpu --dim 3 --nx 7 --iterations 1000 --threads 4
python3 run_c.py --binary build/jacobi_c_cpu --suite check --cpu-only --threads 4 --out "results/local_check_$(date +%Y%m%d_%H%M%S)"
```

若换成 Linux 且有支持 OpenMP 的 g++：

```bash
bash build.sh cpu
build/jacobi_c_cpu --backend cpu --dim 3 --nx 7 --iterations 1000 --threads 4
```

Mac 路径或 OpenMP 编译器不同时先按本机调整；macOS 自带的 clang 不应直接假定具备 libomp。输出为 JSON，三维 n=7 检查离散误差应≤1e−9、边界误差≤1e−12。CPU-only 版本不能请求 `--backend gpu`。

## 6. 可选：在 Vanda 重新运行实验

复现者需要自己的 HPC 账号、已授权项目、校园网络/VPN 和 GPU 资源。以下只说明如何重现，本文整理过程**未重新提交作业**。原始 v5 目录及结果保留，不覆盖它们。

### 6.1 上传完整源码文件集

先在 Vanda 建立自己的新目录，将以下文件一起上传：

```text
jacobi_c_openmp.cpp  jacobi_c_target.c  jacobi_c_target.h
build.sh  run_c.py  analyze_c.py  make_job.py
cluster_env.sh.example  README.md
```

例如，在本机本模块目录中，替换登录名并上传到一个新时间戳目录：

```bash
c_hpc_user='YOUR_HPC_ID'
c_remote_dir="dsa5208_project3/member_c_repro_$(date +%Y%m%d_%H%M%S)"
ssh "${c_hpc_user}@vanda.nus.edu.sg" "mkdir -p '$c_remote_dir'"
scp jacobi_c_openmp.cpp jacobi_c_target.c jacobi_c_target.h build.sh run_c.py analyze_c.py make_job.py cluster_env.sh.example README.md "${c_hpc_user}@vanda.nus.edu.sg:${c_remote_dir}/"
printf '远端目录：%s\n' "$c_remote_dir"
ssh "${c_hpc_user}@vanda.nus.edu.sg"
```

登录后进入刚才打印的新目录，再做后续操作。不要照抄作者账号或把计费项目名当成登录名。

### 6.2 GPU 构建路线

GPU 版本采用 **C++ host/CPU + 独立 C target 编译单元 + 最终链接**。唯一构建入口：

```bash
bash build.sh nvidia
```

build.sh 已包含成功的 `--gcc-toolchain` 修复。不要只编译 `jacobi_c_openmp.cpp`，也不要删除 `.c/.h` 文件。构建须在调度器获配计算节点进行，登录节点用于上传、编辑和提交。

如果已有有效的交互 GPU allocation，可在该计算节点检查小案例：

```bash
source /app1/ebenv
module load NVHPC/24.7-CUDA-12.3.0
export OMP_TARGET_OFFLOAD=MANDATORY
bash build.sh nvidia
build/jacobi_c_gpu --backend gpu --dim 3 --nx 7 --iterations 1000 --threads 1
```

应看到 `gpu_verified=true`、`target_is_initial_device=false`、设备数至少1，并满足 n=7 的误差标准。只看到 nvidia-smi 有 GPU 不等于求解器已卸载。已结束的交互会话不能继续使用。

### 6.3 批处理复现正式矩阵

在**新上传目录的 Vanda 登录节点**，先用 `hpc project` 确认自己的项目权限、`hpc gpu` 查看当前资源规则。下面资源是本次已成功的申请形式；其他账号需要改成自己有权使用的项目。

```bash
cp cluster_env.sh.example cluster_env.sh
python3 make_job.py \
  --queue auto \
  --project personal-yixu_zhu \
  --select '1:ncpus=36:ngpus=1' \
  --threads 12 \
  --suite formal \
  --walltime 01:00:00 \
  --confirmed-resources \
  --output c_formal_reproduce.pbs
cat c_formal_reproduce.pbs
```

核对脚本的 `#PBS -q auto`、项目、资源和 walltime 后，复现者确需新实验时再提交：

```bash
qsub c_formal_reproduce.pbs
qstat -u "$USER"
```

本机 make_job.py 可以直接生成 `--queue auto`，无需先生成 gpu 再手改。Vanda 的 gpu 为 from_route_only execution queue，已完成正式作业实际由 auto 路由到 batch_gpu；不要 `qsub -q gpu`。本次确认内存为240 GB，上述 select 未显式指定 mem，复现时以实际调度配置核实。

脚本会加载环境、保存源码快照、在获配节点编译、运行18项验证，然后运行36次正式性能调用。不要在登录节点直接 `bash c_formal_reproduce.pbs`。batch 提交后退出 SSH 不会取消作业；资源不足排队时不重复提交。

完成后在 `results/C_formal_实际作业ID/` 核对：

- run.log 有 `RUN_STATUS=COMPLETED` 和 `JOB_EXIT_STATUS=0`。
- data/run_status.json 为 `suite=formal`、`status=COMPLETED`、`cpu_only=false`。
- performance_samples=36、validation_cases=18；三规模和各配置3次正式样本齐全。
- GPU 实际执行、CPU实际线程数正确、数值检查通过。

partial formal 不用于完整三规模曲线。下载新作业的 data 目录后，把第4节 c_data 改为新路径即可分析；保留节点/驱动信息，区分复现实验与本次正式结果。

## 7. 源码与历史材料说明

| 路径 | 内容 |
|---|---|
| jacobi_c_openmp.cpp | 数学输入、CPU OpenMP、参数与诊断输出 |
| jacobi_c_target.c / .h | 独立 C GPU stencil 与接口 |
| build.sh / run_c.py | 构建及 check / pilot / formal 运行与验收 |
| analyze_c.py / requirements-plots.txt | 统计绘图与依赖版本 |
| make_job.py / cluster_env.sh.example | PBS 生成与环境配置 |
| docs/ | 当前中文成果、核验与实现说明 |
| deliverables/formal_20261106/ | 随仓库提供的正式数值数据、图表、验证简表和裁剪环境配置；[成果索引](deliverables/formal_20261106/README.md) |
| results/ | 仅作者本机保留的完整证据、旧 pilot、Mac 检查，不上传 GitHub |
| reference/ | 仅作者本机保留的历史版本、诊断和备份，不上传 GitHub |

results 中的 source/source_build 是执行当时的快照，其中旧 README 不代表最新状态。不要为了“更新版本”回写它们。求解器、构建与 runner 未因本次出图而更改；当前 analyze_c.py 已更新图注、坐标轴及完整 formal 矩阵验收，历史脚本仍保留。

**模块边界：**这里只提供 OpenMP CPU 与单 GPU 证据；不包含 MPI、weak scaling、MPI+OpenMP 或多 GPU 结论。组员合稿时可直接使用当前中文成果说明、正式图表和 CSV；最终报告不附 run.log、stdout/stderr、qstat 或完整证据包。
