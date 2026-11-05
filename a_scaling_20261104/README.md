# A：固定工作量串行规模实验

准备日期：2026-11-04。更新：11/5正式Vanda作业1522376已完成、下载并整理；[结果入口](../evidence/vanda_1522376_a_scaling/README.md)。下方操作保留作复现说明，已有结果无需重跑。
本目录是已有 jacobi_numerics.cpp 的独立扩展，增加 poisson2d_mms；历史文件与结果保留。

## 实验目的

补 Lecture 12 串行规模分析：2D n=256/512/1024/2048/4096；3D n=16/32/64/128/256。
K=1000，单线程，同一获配 CPU 绑定。每配置一次预热、三次正式，合计40次性能运行。
正式前自动做2D/3D n=7小检查。预热不参与统计。每次进程重新初始化。
串行采用 -O2；只计迭代，残差/误差/输出在计时外。
一小时是PBS上限，实际时间待测；分配两CPU槽但程序只绑定其中一个计算。

## 数学定义

2D：单位正方形，u*=x+2y+sin(pi*x)sin(2*pi*y)，f=5*pi^2*sin(pi*x)sin(2*pi*y)，边界x+2y。
3D沿用已有制造解和七点差分。两者内部初值零、double、双缓冲、RHS预计算。
小案例对比精确离散解，误差<=1e-9、边界<=1e-12；正式大网格仅完成固定K，不要求收敛。

## 操作

1. 上传本目录四个文件至Vanda新目录 ~/dsa5208_project3/a_scaling_20261104/。
2. 在远端该目录运行 qsub vanda_a_scaling.pbs，保存返回的job ID。
3. 用 qstat -u yangaier 查看状态。通过PBS计算，不在登录节点直接运行正式矩阵。
4. 完成后检查 results/Vanda_JOBID/run.log 的 RUN_STATUS=COMPLETED 与 JOB_EXIT_STATUS=0。
5. 下载整个 results/Vanda_JOBID/ 到本机，然后绘图与补报告。

PBS使用11/3已使用的auto_free与GCC12.2.0/Python3.10.8模块；可用性仍以本次执行为准。
输出目录必须是新的；失败后保留记录，修正再提交新作业，勿覆盖原结果。

## 文件与后续交付

- data/validation.json：两个小案例的误差。
- data/environment.json：主机、CPU绑定、源码及程序hash。
- data/samples.csv：40次性能样本（warmup=1不入统计）。
- data/summary.csv：10配置中位数、min/max、每点每轮成本、相邻规模斜率。
- data/run_status.json：完成状态；缺失时不能认定整批完成。
- source/ 和 run.log：内部复核材料，最终课程提交不附日志。

下载后画2D/3D耗时双对数图（横轴n、理论斜率2/3）、每点更新成本图；
补算法/输入生成、串行规模分析，合并已有A2收敛/精度和基准说明。
收到B/C成稿后统一术语/图/编号，再按白名单打包PDF、代码、README和必要脚本/数值CSV。
现有A2不重跑。本机smoke仅验证实现，不作为Vanda性能证据。

AI使用：ChatGPT/Codex辅助新增2D路径、运行/PBS脚本及操作说明；正式作业由用户提交。

## 本地检查记录（2026-11-04）

使用 g++ -std=c++17 -O2 -Wall -Wextra -Wpedantic 编译通过。
2D/3D n=7、K=1000 的精确离散解检查通过。
新增2D的3×5矩形网格单步输出与独立Python公式逐点比较，最大误差1.67e-16。
原3D和旧2D n=7、K=1000与原程序全部非计时输出一致。
上传四文件均为LF换行；本机检查不计作正式集群性能结果。
