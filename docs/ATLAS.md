# Atlas 学校集群完整操作指南

更新日期：2026-10-26。面向第一次接手本仓库、需要在 NUS Atlas 上运行的组员。路线为：**本机取得代码 → SSH 登录 → 创建远程目录 → 本机 SCP 上传 → Atlas 提交 PBS 作业 → 查询与验收 → 本机 SCP 下载结果**。

当前 A 的串行与环境小作业已有 2026-10-23 的成功证据；本指南供组员接入、复现和后续运行使用，不要求 A 为补文档重复提交已有实验。本轮只完善文档，没有重新登录 Atlas 或提交作业。

## 0. 先分清三个位置

| 位置 | 在这里做什么 | 识别方式 |
|---|---|---|
| 自己电脑 | Git clone/pull、编辑、SCP 上传和下载 | Windows 为 PowerShell，Mac 为 Terminal；尚未 SSH 登录 |
| Atlas 登录节点 | 创建目录、查看模块/队列、qsub 提交、qstat 查询 | SSH 后看到 Atlas 公告及远程提示符 |
| Atlas 计算节点 | 编译和运行 Jacobi、MPI、OpenMP | 本仓库的 PBS 脚本获分配后自动执行 |

每节注明命令执行位置。代码框不含命令提示符，逐条执行即可；`YOUR_HPC_ID` 要替换成执行者本人开通邮件中的 HPC 用户名。HPC 用户名与 GitHub 用户名分别使用。实际操作的成员用本人账号，不要求三人都重复相同的集群实验。

## 1. 本机：账号、网络与 SSH 登录

实际运行的成员先确认本人 HPC 账号已开通。申请入口见 [NUS HPC account](https://nusit.nus.edu.sg/hpc/get-an-hpc-account/)，具体表单和审批状态以校方页面或开通邮件为准。

校外访问学校受限资源时，按 [NUS nVPN 指南](https://nusit.nus.edu.sg/services/wifi_internet/nvpn/) 配置校园 VPN；官方页面将客户端安装及配置指引放在 A.S.K.。本指南不代填 VPN 配置，也不推断个人账号审批状态。

**执行位置：本机 PowerShell 或 Mac Terminal。**

```bash
ssh -p 22 YOUR_HPC_ID@atlas8.nus.edu.sg
```

`atlas8.nus.edu.sg` 来自已跑通的 2026-10-23 登录记录；当前可用节点及维护安排以开通信息、校方指引和最新登录公告为准。首次连接先按校方资料核对主机指纹，再接受主机密钥。输入密码时不显示字符或星号，输入后按回车即可。

登录成功后，**以下命令在 Atlas 远程终端执行**：

```bash
hostname
whoami
cd "$HOME"
pwd
mkdir -p "$HOME/dsa5208_project3/github_baseline"
```

保存 `pwd` 显示的实际 home 路径；组员不要照抄他人的 `/home/...` 目录。阅读最新登录公告，留意调度、维护和存储清理安排。

创建好目录后输入 `exit` 返回本机，或另开一个本机终端用于上传。

## 2. 本机：确认仓库版本并上传

先在自己电脑 clone/pull 小组私有仓库；需要访问 GitHub 的认证在本机完成。这里采用 SCP 传源码，Atlas 不需要为本步骤配置 GitHub 私有仓库凭证。

### Windows PowerShell

**执行位置：本机 PowerShell，当前目录为本仓库根目录。** 从 GitHub 克隆的成员进入自己的 clone 路径；不能把本机路径输入 Atlas 终端。仓库根目录应能看到 `jacobi.cpp` 和两个 `.pbs` 文件。

```powershell
Get-Location
Get-ChildItem jacobi.cpp, mpi_hello.cpp, omp_hello.cpp, atlas_serial.pbs, atlas_parallel_smoke.pbs
git rev-parse HEAD
$atlasUser = 'YOUR_HPC_ID'
scp jacobi.cpp mpi_hello.cpp omp_hello.cpp atlas_serial.pbs atlas_parallel_smoke.pbs "${atlasUser}@atlas8.nus.edu.sg:dsa5208_project3/github_baseline/"
```

把赋值行的 `YOUR_HPC_ID` 换成自己的用户名。`$atlasUser = '...'` 是直接赋值，不会等待额外输入。记下当前 commit；若源码有未提交修改，还要如实记录。PBS 脚本将另保存运行时源码 SHA-256。

### Mac / Linux Terminal

**执行位置：本机 Terminal，当前目录为本仓库根目录。**

```bash
pwd
ls jacobi.cpp mpi_hello.cpp omp_hello.cpp atlas_serial.pbs atlas_parallel_smoke.pbs
git rev-parse HEAD
atlas_user='YOUR_HPC_ID'
scp jacobi.cpp mpi_hello.cpp omp_hello.cpp atlas_serial.pbs atlas_parallel_smoke.pbs "${atlas_user}@atlas8.nus.edu.sg:dsa5208_project3/github_baseline/"
```

远程冒号后未以 `/` 开头的路径相对于该账号的 home，正好对应第 1 节创建的目录。只需上传这五个源码/脚本文件来运行现有两次小作业，脚本不依赖集群 Python。Windows 的 exe 不上传用于集群运行，Atlas 会重新编译。

## 3. Atlas：核对文件、模块和队列

**先在本机重新 SSH 登录**，仍用第 1 节的连接命令。下面各行在 **Atlas 远程终端**执行：

```bash
cd "$HOME/dsa5208_project3/github_baseline"
ls -l jacobi.cpp mpi_hello.cpp omp_hello.cpp atlas_serial.pbs atlas_parallel_smoke.pbs
source /app1/ebenv
module avail GCC
module avail OpenMPI
qstat -Q
qstat -Qf serial
qstat -Qf parallel
```

这一步只核对环境，不在登录节点编译或运行 Jacobi。两个 PBS 脚本内部会加载编译模块并在计算节点编译。若 `qstat`/`qsub` 找不到，按学校环境帮助尝试 `module load pbs`，再检查；保留实际错误输出，不继续盲目提交。

现有脚本使用以下**历史已成功配置**：

| 脚本 | 队列与申请 | 计算节点内自动完成的操作 |
|---|---|---|
| `atlas_serial.pbs` | serial；1 CPU；2GB；5 分钟上限 | GCC 12.2.0 编译串行 Jacobi，运行 n=1/2/16/32 |
| `atlas_parallel_smoke.pbs` | parallel；12 CPU/12 MPI slots；2GB；5 分钟上限 | GCC 12.2.0 / Open MPI 4.1.5；检查 MPI 2/4/12 与 OpenMP 4/12 |

这些配置在 2026-10-23 已运行成功，本轮未重新查询 Atlas。若当前模块或资源限制变化，由运行负责人按实际返回调整脚本并记录版本。曾经使用 1GB 被拒，后改为 2GB；不能只凭旧说明忽略本次队列限制。

## 4. Atlas：提交串行作业

**执行位置：Atlas 远程终端，必须处于上传源码的目录。**

```bash
pwd
serial_job=$(qsub atlas_serial.pbs)
printf 'SERIAL_JOB=%s\n' "$serial_job"
qstat -u "$(whoami)"
```

`qsub` 成功后，变量应包含类似 `1234567.venus01` 的完整作业 ID；请记录自己的返回值，不要沿用历史作业号。如果没有返回有效 ID 或出现报错，先处理该错误，不继续后面的验收步骤。

脚本通过 `PBS_O_WORKDIR` 读取**提交目录**的源码，输出到 `results/atlas_serial_<完整作业ID>/`。因此不要把 `.pbs` 单独移到别的目录再提交。作业排队或运行期间保持该版本源码可追溯；后续代码版本可另建实验目录，避免覆盖正在等待编译的源码。

## 5. Atlas：查看状态、日志和串行数值

**执行位置：同一个 Atlas 远程会话。**

```bash
qstat -f "$serial_job"
```

常见状态：Q 为排队，R 为运行，F 为完成，H 为 hold。处于 Q 时结果目录尚未生成是正常现象。作业退出普通列表后，使用历史查询：

```bash
qstat -xf "$serial_job"
tail -n 40 "results/atlas_serial_${serial_job}/run.log"
```

完成并生成结果目录后，保存完整状态并查看数值：

```bash
qstat -xf "$serial_job" > "results/atlas_serial_${serial_job}/qstat_full.txt"
cat "results/atlas_serial_${serial_job}/n1_one_step.json"
cat "results/atlas_serial_${serial_job}/n2_one_step.json"
cat "results/atlas_serial_${serial_job}/n16.json"
cat "results/atlas_serial_${serial_job}/n32.json"
```

`qstat -x` 只能在学校仍保留该作业历史时查询，因此应及时保存。若退出并重新登录，shell 中的 `serial_job` 变量不会保留；先用自己的记录恢复，例如 `serial_job='1234567.venus01'`，再执行相应命令。

串行验收分三层：

| 检查 | 应有结果 |
|---|---|
| PBS 状态 | F，`Exit_status = 0` |
| 脚本结束 | `RUN_STATUS=COMPLETED`、`JOB_EXIT_STATUS=0` |
| 数值正确性 | n=1 中心为 1；n=2 内部为 `[[1/6,1/2],[1/2,5/6]]`；n=16/32 达到更新量容差，真误差≤1e-8，残差≤1e-7，边界误差为 0 |

n=16/32 的历史参考轮数分别为 1401/5006；跨平台以状态和数值门槛验收，不强求末位浮点数一致。n=2 只运行一轮，误差 0.5、残差 9 是预期的未收敛状态，按手算网格验收。PBS 成功退出或脚本完成本身不等于所有数值已经正确。

## 6. Atlas：提交 MPI/OpenMP 环境检查

串行结果验收通过后，**在 Atlas 远程终端的同一源码目录**执行：

```bash
smoke_job=$(qsub atlas_parallel_smoke.pbs)
printf 'SMOKE_JOB=%s\n' "$smoke_job"
qstat -u "$(whoami)"
```

记录有效 ID，等待完成后再执行：

```bash
qstat -xf "$smoke_job"
tail -n 40 "results/atlas_smoke_${smoke_job}/run.log"
qstat -xf "$smoke_job" > "results/atlas_smoke_${smoke_job}/qstat_full.txt"
cat "results/atlas_smoke_${smoke_job}/mpi_np2.txt"
cat "results/atlas_smoke_${smoke_job}/mpi_np4.txt"
cat "results/atlas_smoke_${smoke_job}/mpi_np12.txt"
cat "results/atlas_smoke_${smoke_job}/openmp_threads4.txt"
cat "results/atlas_smoke_${smoke_job}/openmp_threads12.txt"
```

预期：PBS `Exit_status=0`、日志 `SMOKE_STATUS=PASSED` 和 `JOB_EXIT_STATUS=0`；MPI 各 rank 完整且不重复，2/4/12 进程的 sum 分别为 3/10/78；OpenMP 输出 `threads=4 sum=5050` 和 `threads=12 sum=5050`。输出行的 rank 顺序可以不同。

这一步检查环境。当前脚本没有 MPI/混合 Jacobi；也没有执行建议的 4 进程×3 线程混合配置。混合算法、相应 PBS 申请及正式性能实验仍由 B/C 后续接入。

## 7. 本机：下载原始目录

两次作业完成且状态文件保存后，在 Atlas 输入 `exit` 返回本机，或另开本机终端。**以下 SCP 下载命令必须在本机执行。**

Windows PowerShell，在本仓库根目录：

```powershell
$atlasUser = 'YOUR_HPC_ID'
New-Item -ItemType Directory -Force results/atlas_download | Out-Null
scp -r "${atlasUser}@atlas8.nus.edu.sg:dsa5208_project3/github_baseline" .\results\atlas_download\
```

Mac/Linux Terminal，在本仓库根目录：

```bash
atlas_user='YOUR_HPC_ID'
mkdir -p results/atlas_download
scp -r "${atlas_user}@atlas8.nus.edu.sg:dsa5208_project3/github_baseline" results/atlas_download/
```

首次下载后，应出现 `results/atlas_download/github_baseline/`，内含上传的源码/PBS、作业输出和 `results/atlas_serial_<ID>/`、`results/atlas_smoke_<ID>/`。下载完成后检查目录和文件是否齐全；不能仅凭 SCP 结束就记为数值验证通过。后续新实验使用新的本地下载位置，保留已有归档。

`results/` 已被 Git 忽略。完整原件保留在本地；要共享时把经核对、去除个人登录信息的结果整理到 `evidence/`，同时记录来源、配置、代码版本与校验值。

## 8. 组员应回传的交接证据

- 运行使用的仓库 commit、源码 SHA-256、完整命令、模块/编译器版本。
- 两个实际作业 ID、申请 CPU/内存、PBS 完整状态及退出码。
- 串行四个 JSON 和 MPI/OpenMP 数值输出，数值验收结论。
- 完整原始下载的位置；共享仓库中整理后的证据位置。

这两次作业是首次接入模板。现有串行脚本运行 n=1/2/16/32，并不自动运行公共约定中的 `7 31 0`、n=31 或 `1024 1000 0`。要在学校运行这些新增案例，应另建/修改并命名对应 PBS 脚本，沿用计时和参数约定，不能把这里的环境检查说成正式性能实验。

## 9. 常见问题

| 现象 | 处理方向 |
|---|---|
| SSH 超时 | 核对网络/VPN、主机地址及最新维护公告 |
| `Permission denied` | 核对本人 HPC ID、密码和开通状态 |
| 密码输入时没有字符 | 正常输入行为，输完按回车 |
| SCP 找不到本地源码 | 回到本机仓库根目录再运行上传命令 |
| `qsub: command not found` | 按学校环境帮助加载 PBS，核对当前是否在 Atlas |
| 资源请求被拒 | 保存错误与 `qstat -Qf`，按当前下限和账号限制调整 |
| Q 状态下没有 run.log | 尚未开始执行，继续按需要查询作业状态 |
| `Unknown Job Id` | 核对 ID、服务器后缀和历史保留期；查已保存的状态/日志 |
| 手工 bash 执行 PBS 报缺少变量 | 回到正确目录用 qsub 提交，由 PBS 建立运行环境 |
| 缺少 Python | 现有两个 PBS 不需要 Python；本机 Python 用于验证辅助 |

## 10. 依据与核对范围

- 2026-10-23 保存的学校培训资料、Atlas 登录/队列/模块输出、两个已完成作业及完整下载原件。
- 本仓库实际 `atlas_serial.pbs`、`atlas_parallel_smoke.pbs` 和精选证据。
- [NUS Atlas Onboarding](https://nusit.nus.edu.sg/hpc/atlas-onboarding/) 与 [HPC account](https://nusit.nus.edu.sg/hpc/get-an-hpc-account/)：入口供成员查看最新说明；本轮自动访问未成功，未据此推断当前页面内容。
- [NUS nVPN](https://nusit.nus.edu.sg/services/wifi_internet/nvpn/)：本轮核对到官方网络访问和 A.S.K. 指引。
- [PBS Professional User Guide](https://help.altair.com/2024.1.0/PBS%20Professional/PBSUserGuide2024.1.pdf)：提交、状态及历史查询的通用说明；学校实际 PBS 配置仍以当前返回为准。

本轮验证限于文档链接、代码框语法及与现有脚本/结果的对应关系；未新增 Atlas 登录、作业或实验结果。
