> 2026-11-07：按 11 月最新分工的新 B 路线，见 [运行指南](../b_mpi/README.md)、[实测结果与作业状态](B_RESULTS_2026-11-07.md)及 [B 章节](final_B_mpi.md)。下面 10 月记录为历史路线，不替代新的 3D 强弱扩展要求。

> 最新共享状态（2026-10-28）：A/B及实验1、3、2均已完成并审计，阶段报告已校核，当前不追加实验。所有成员先读[同步说明](TEAM_SYNC_2026-10-28.md)、[英文报告](AB_STAGE_REPORT_DRAFT_2026-10-28.md)和[最终证据](../evidence/ab_final_2026-10-28/README.md)。七份完整原始包已纳入本次共享，原1498804完整包仍缺；下面早期“待运行/更多规模待补”属于历史状态。实际分工、姓名学号与个人理解仍需本人确认。

> 当前状态补充（2026-10-27）：A接手后的串行诊断及三轮纯MPI复测均已完成，见[阶段结果梳理](AB_RESULTS_SUMMARY.md)。原B作业1498804完整原始包仍未取得；下文“已审计”只对应既有精选记录的历史核对，不代表已完成完整原件审计。下文初始待运行步骤不构成追加实验计划；成员本人确认仍待据实完成。

> 状态更新：Vanda 作业 1498804.stdct-mgmt-02 已成功运行并完成审计。278 次验证通过，26 组各 1 次预热/5 次计时；分析见 evidence/vanda_1498804/B_Vanda实验分析.md。下文的“尚未运行”描述为首次接入时状态，后续以本更新及原始日志为准。

# 成员 B：MPI/HPC 交付与运行指南

更新：2026-10-27。MPI 与混合程序已实现并通过本地验证；Vanda/Atlas 新作业尚未运行。小组成员本人确认、集群资源/模块核对及正式性能结论仍待完成。

## 1. 已实现的内容

- `jacobi_mpi.cpp`：C++17，double，单位正方形离散 Laplace，边界/精确解 x+y，内部初值零，三参数接口与 A 的串行版一致。
- 一维按行分区：前 n%P 个进程多一行；首版明确拒绝 P>n。每个进程仅保存本地内部行及上下两个 halo，不复制整张网格。
- `--exchange sendrecv`：两次 MPI_Sendrecv，作为直接可核对的通信基准。
- `--exchange overlap`：先发起 Irecv/Isend，计算不依赖 halo 的内部行，Waitall 后计算首末行。只有一行时只更新一次；只有两行时不计算内部行。
- OpenMP 编译得到 `hybrid` 模式，静态分配本地行，使用 max reduction。所有 MPI 调用在初始化 MPI 的主线程进行，申请并检查 MPI_THREAD_FUNNELED；纯 MPI 申请 SINGLE。
- 每轮完成后交换 old/new；正容差每轮 Allreduce 全局更新量统一停止；固定轮数只在最后一轮归约更新量。两种通信策略使用相同的归约口径。
- 最终 halo 重新交换后才计算残差，避免用上一轮邻居值。误差、残差、边界误差均取全局最大值。
- rank 0 输出一条 JSON，n<=8 使用 Gatherv 收集完整网格；输出实际线程数、MPI 进程数、共享内存节点数和通信策略。
- 同步起点后用 MPI_Wtime 计迭代时间，含必要通信、归约和 OpenMP 同步，报告最慢 rank 耗时。初始化、最终验证、收集及打印不在迭代计时内。

局限：OpenMP 在每个更新阶段进入并行区域，尚未实现持久线程区域；非阻塞通信是否实现有效重叠取决于 MPI 的进度机制和工作量，不能根据代码就宣称提速。未实现二维分区、零内部行进程或自动优化绑定。

## 2. 编译与本地验证

Linux / 已加载 GNU + Open MPI 的计算节点：

```bash
make all
python3 verify_small.py build/jacobi_serial build/jacobi_omp
python3 verify_parallel.py --serial build/jacobi_serial --mpi build/jacobi_mpi \
  --hybrid build/jacobi_hybrid --launcher 'mpirun --bind-to none' \
  --out-dir results/my_parallel_validation
```

Mac（Apple Clang + Homebrew Open MPI + libomp，已在本次环境验证）：

```bash
make all OMPFLAGS="-Xpreprocessor -fopenmp -I$(brew --prefix libomp)/include -L$(brew --prefix libomp)/lib -lomp"
python3 verify_parallel.py --serial build/jacobi_serial --mpi build/jacobi_mpi \
  --hybrid build/jacobi_hybrid --launcher 'mpirun --oversubscribe --bind-to none' \
  --out-dir results/my_parallel_validation
```

oversubscribe 只用于本地正确性检查，正式性能实验不能超配。结果目录必须尚不存在。Python >=3.10，只需标准库。Windows 建议用 WSL，不能直接照搬 Mac 的 OpenMP 编译选项。

示例：

```bash
mpirun -np 4 build/jacobi_mpi 7 31 0 --exchange sendrecv
OMP_NUM_THREADS=2 mpirun -np 4 --bind-to none build/jacobi_hybrid 7 31 0 --exchange overlap
```

验证器会按公共约定对照串行/独立小网格，检查完整网格形状、边界、更新量、真误差、残差和停止状态。覆盖 1/2/3/4 进程、混合版 1/2 线程、两种通信方式、n=4 每进程一行、n=8 每进程两行、n=12 每进程三行及非法参数。正容差耗尽轮数返回 2 属于预期测试，MPI 启动器打印非零退出提示是正常现象。

## 3. Vanda 账号与首次连接（本机 Mac）

1. 用本人 NUS 账号访问 https://nusit.nus.edu.sg/hpc/get-an-hpc-account/，检查是否已开通 HPC。已有权限不必重复申请；未开通则按门户申请，教学项目/配额问题按课程安排或咨询老师。申请页对自动读取返回 403，字段、审批和配额以登录后的当前页面为准。
2. 校外访问按 https://nusit.nus.edu.sg/services/wifi_internet/nvpn/ 配置 nVPN。官方将 Cisco Secure Client 安装包和配置教程放在 A.S.K.；在客户端自行完成学校登录与认证。
3. 连通网络后在 Mac Terminal 执行 `ssh YOUR_HPC_ID@vanda.nus.edu.sg`。YOUR_HPC_ID 以开通邮件为准；不要仅凭学号猜测。首次核对主机指纹；密码在终端输入，不要发给 AI 或写入仓库。
4. 成功后运行以下只读检查，把当前环境信息用于配置脚本：

```bash
hostname
whoami
hpc cpu
hpc project
qstat -Q
module avail
```

需要时按现场指引运行 `amgr login` 并自行认证。`hpc project` 用于检查可用项目/配额；不要套用其他课程的 GPU 配额。官方 Vanda 指南入口：https://tinyurl.com/596ascu3 （学校 SharePoint，可能要求学校登录）。

错误定位：无法解析域名通常先查 VPN/DNS；超时查网络；Permission denied 查本人 HPC 用户名、权限和密码；首次主机确认失败需先核对指纹。不要通过关闭 SSH 主机验证解决登录问题。

## 4. 上传与准备（本机 → Vanda 登录节点）

在仓库根目录的本机终端执行，替换本人用户名：

```bash
ssh YOUR_HPC_ID@vanda.nus.edu.sg 'mkdir -p dsa5208_project3/member_b'
scp jacobi.cpp jacobi_mpi.cpp Makefile verify_small.py verify_parallel.py \
  prepare_team_references.py team_contract_v0.1.json benchmark_parallel.py \
  run_cluster.sh atlas_jacobi.pbs vanda_jacobi.pbs vanda_modules.example.sh \
  YOUR_HPC_ID@vanda.nus.edu.sg:dsa5208_project3/member_b/
```

在 Vanda 登录节点：

```bash
cd ~/dsa5208_project3/member_b
hpc cpu
```

根据当前 `hpc cpu` 模板和项目要求调整 `vanda_jacobi.pbs` 的资源/队列/项目行。默认提出单节点 12 CPU、12 MPI slots、4GB、30 分钟；这不是已核实可用的 Vanda 配额。多节点实验需另行设计资源申请和每节点绑定。

已提供 `vanda_modules.example.sh`，默认加载现场列表中匹配的 GCC/12.2.0、OpenMPI/4.1.5-GCC-12.2.0、Python/3.10.8-GCCcore-12.2.0；仍需在计算节点验证加载和运行。需要修改时创建 `vanda_modules.sh` 覆盖默认配置。不要把 Atlas 的 module 名称直接复制到 Vanda。不知道模块时先取得 `module avail` 和课程环境说明，再确定组合；C++ 编译器和 mpicxx 底层编译器应匹配。

本项目所有编译/计算由 PBS 作业在计算节点执行。登录节点只用于文件、环境查询和提交。可先按学校当前模板申请小型交互计算作业，加载模块并检查 `g++ --version`、`mpicxx --showme`、`mpirun --version`、`python3 --version`。

## 5. 提交、验收与下载

配置核对后，在 Vanda 仓库目录：

```bash
qsub vanda_jacobi.pbs
qstat -u "$(whoami)"
```

记下真实作业 ID。将下面 JOB_ID 替换成返回值：

```bash
qstat -xf JOB_ID
cat results/Vanda_parallel_JOB_ID/run.log
cat results/Vanda_parallel_JOB_ID/validation/summary.json
cat results/Vanda_parallel_JOB_ID/benchmark/summary.json
qstat -xf JOB_ID > results/Vanda_parallel_JOB_ID/qstat_full.txt
```

只有 validation、benchmark 的 status 均为 PASS，且 PBS 退出 0 / 日志 RUN_STATUS=PASSED，才视为整套作业通过。缺少结果时先查作业和日志；不要仅看 qsub 成功。

回到本机下载：

```bash
scp -r YOUR_HPC_ID@vanda.nus.edu.sg:dsa5208_project3/member_b/results/Vanda_parallel_JOB_ID ./results/
```

默认实验：1024×1024 内部点、固定 1000 轮；预热 1 次，记录 5 次，比较纯 MPI 核数和总计 12 核的 P×T 配比，分别跑 sendrecv/overlap。脚本保存每次原始 JSON、stderr（含 MPI 绑定）、命令、OMP 环境、源码快照、哈希、编译环境和中位数/min/max/加速比/效率。固定轮数不声称收敛。

首个规模通过后，可以按同样流程另提交 n=512/2048，观察问题规模对强扩展的影响：

```bash
qsub -v JACOBI_N=512 vanda_jacobi.pbs
qsub -v JACOBI_N=2048 vanda_jacobi.pbs
```

如需 K=5000，使用 `-v JACOBI_K=5000` 并先估计 walltime/配额。benchmark 脚本也可单独调用：

```bash
python3 benchmark_parallel.py --build-dir build --out-dir results/my_benchmark \
  --cluster local --allocated-cpus 4 --n 64 --iterations 50 --repeats 2 \
  --configs 'mpi:1:1,mpi:2:1,hybrid:2:2' --launcher 'mpirun --bind-to none'
```

上面最后一条是本地流程检查示例。正式报告只使用在学校集群生成的记录，并明确硬件、核心数、绑定、问题规模、重复次数及计时范围。当前脚本没有自动生成弱扩展实验，不能把固定 12 核配比比较称为多节点扩展。

## 6. B 的交付边界

代码、验证、通信策略比较入口、计时工具、PBS 模板与操作说明已提供。本机 278 次执行已通过，另完成 24 次重复计时流程检查。现有本地计时规模很小，不作为正式性能结论。

仍需本人/小组完成：HPC 身份与接口确认、Vanda 当前配置、实际提交与完整集群原始结果、报告性能分析、与 C 的代码审阅。AI 编写和本机通过不替代个人理解或组员确认。

MPI 线程级别参考：https://docs.open-mpi.org/en/v5.0.0/man-openmpi/man3/MPI_Init_thread.3.html

## Vanda 提交模板现场信息更新

用户已提供 `hpc cpu` 输出：使用项目时指定 `#PBS -P 项目名`；使用 `auto_free` 时删除项目行并启用 `#PBS -q auto_free`。作业模板已选择 auto_free，不填写虚构项目名。示例中的 36/72 核是示例申请值，不能据此认定 12 核申请一定有效，仍需 `qstat -Qf auto_free` 核对。HPL/2.3-intel-2023b 是 HPL 算例环境，未作为本项目 GNU/Open MPI 编译环境使用。

PBS 的 ompthreads=1 为默认设置，实验驱动会为每次运行显式设置 OMP_NUM_THREADS，并用 Open MPI 的 PE 和核心绑定选项匹配实际线程数。每个并行配置 P×T<=12；以程序输出和绑定日志验收。

## 模块列表与路由队列核对（2026-10-27）

用户提供的模块列表包含 GCC/12.2.0、OpenMPI/4.1.5-GCC-12.2.0、Python/3.10.8-GCCcore-12.2.0，默认模块文件已使用该匹配组合；未将“列出可用”记为“已成功加载/运行”。`auto_free` 的 queue_type=Route，route_destinations=cpu_serial,cpu_parallel,gpu。路由队列输出没有证明 12 CPU/4GB 申请可用，提交前还需检查 `qstat -Qf cpu_parallel` 的资源上下限和启用状态。用户已在自己的终端完成认证；AI 的独立 SSH 连接没有免密凭据，因此尚未远程上传或提交。
