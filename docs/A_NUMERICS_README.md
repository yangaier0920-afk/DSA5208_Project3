# A 数值路线运行说明

更新：2026-11-03。A2 已在 Vanda 完成，见 [本批完成记录](A_PROGRESS_2026-11-03.md)；已有结果无需重跑。

2026-11-01 新增 jacobi_numerics.cpp，无 MPI/OpenMP 依赖。
详细数学、基准解释和本地结果见 [A 报告草稿](final_A_numerics.md)。

## 编译和本人基本检查

仓库根目录 Windows 命令：

~~~powershell
New-Item -ItemType Directory -Force build
g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic jacobi_numerics.cpp -o build/jacobi_numerics.exe
python run_a_numerics.py --binary build/jacobi_numerics.exe --suite smoke --out-dir results/final_202611/A_numerics/local_NEW
python analyze_a_numerics.py results/final_202611/A_numerics/local_NEW
~~~

输出目录必须是新目录。smoke 包含 n=7 固定1000轮、求解收敛、达到上限三例。
固定1000轮的离散误差阈值为1e−9，提前停止模式按其残差阈值判定。
无需任何其他成员输出。Python运行脚本只需标准库；绘图需要matplotlib。

Linux 使用 make numerics，输出 build/jacobi_numerics，不加.exe。
该目标独立于旧 all/check。

## 参数与单案例

~~~bash
build/jacobi_numerics --problem poisson3d_mms --nx 7 --mode fixed --max-iters 1000 --history history.csv
build/jacobi_numerics --problem poisson3d_mms --nx 15 --mode solve --max-iters 100000 --tol 1e-10 --check-every 10 --history history.csv
build/jacobi_numerics --problem laplace2d_legacy --nx 1024 --mode fixed --max-iters 1000
~~~

- --nx/--ny/--nz 是内部点数，ny默认nx，3D的nz默认nx；旧2D输出nz=0。
- --max-iters 是fixed确切轮数或solve上限；默认1000。
- --tol 必须为有限正数，默认1e−8；fixed不提前停止。
- --check-every 默认10，影响solve迭代内残差检查。
- --history 可选，输出iteration/residual_l2/residual_inf/relative_residual。
- --grid 可选，保存含边界的最终i,j,k,u，供小案例使用。
- stdout单行JSON；退出码0为fixed完成或solve收敛，2为solve到上限，
  1为输入/内存/文件/非有限数值错误。
- first_check_le_1e8 为已采样历史中首次R≤1e−8轮数，-1为未观测。
  fixed只有初始/最终点，不能据此判断中间首次收敛轮数。
- compute_seconds：fixed为迭代区间；solve还包括迭代内残差检查及历史入内存；
  不含初始化、初始/最终额外残差、误差计算及文件输出。
- continuous_error_inf和discrete_error_inf只计算内部点；
  boundary_error_inf单列物理边界。

## A2正式矩阵（11/3已完成；以下保留运行说明）

~~~bash
python3 run_a_numerics.py --binary build/jacobi_numerics --suite formal --out-dir results/final_202611/A_numerics/formal_NEW
python3 analyze_a_numerics.py results/final_202611/A_numerics/formal_NEW
~~~

共5例：3D n=15/31/63，solve、1e−10、每10轮检查、最多100000轮；
旧2D n=1024/2048，fixed K=1000。收敛与精度复用同一次运行。
退出码2保留为未收敛结果继续记录。检查各行status，不能仅凭脚本完成称收敛。

保存每例stdout/stderr/实际命令、历史、summary.csv、环境和程序/源码SHA256。
分析生成convergence.png、precision.csv；只有已收敛且h减半的相邻网格才计算阶数。
一个网格时阶数栏留空。已有数据可直接分析，无需重跑。

## 恢复后在Vanda运行

公告计划11/2 17:00恢复；实际以系统通知为准。11/3确认队列/模块后：

~~~bash
qsub vanda_a_numerics.pbs
~~~

PBS草稿使用项目已有auto_free队列、2 CPU/4GB；程序单线程。
恢复后仍需确认队列可用性。1小时walltime为预留预算，尚无此次集群试跑依据。
脚本保存编译器、flags和退出状态。集群只用标准库，下载后本地绘图即可。

11/3用户已完成集群提交与下载；本地已整理A2数据和图文。B/C各自按分工推进。
Canvas精确截止时间仍需本人登录确认。
