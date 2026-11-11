# C 模块 · 11 月 10 日补测与合稿

正式矩阵和三项补测都已完成。四个有效作业的 PBS 退出码均为 0，共有 81 次正式测量。最新英文 C 章节已纳入三项补测和 CPU 汇编证据。[合稿入口](final_results_20261110/README.md) · [英文 C 章节](final_results_20261110/final_C_openmp.md) · [PBS 作业索引](final_results_20261110/PBS_status.csv) · [11 月 9 日评语处理表](final_results_20261110/REVIEW_RESPONSE_20261111.md)

| 项目 | 结果 |
|---|---|
| 正式 CPU/GPU 矩阵 | 作业 `1525886.stdct-mgmt-02`，GN-A40-024，实耗时 5 分 29 秒。64³、128³、256³ 各测 CPU1、CPU12 和单 GPU。相对 CPU12，GPU resident 加速比为 **2.34× / 4.25× / 2.94×**。[正式中文说明](../docs/FORMAL_RESULTS_20261106.md) · [PBS 历史摘录](evidence/README.md) |
| CPU1 与 A 串行 | 同机同核下，GCC 12.2 的 A 纯串行为 **32.17 s**、C 纯串行为 **29.91 s**。在同一 NVHPC 24.7 OpenMP 构建中，仅把 `collapse(3)` 改为只并行外层，耗时从 **51.38 s 降至 28.84 s**，减少 **43.9%**。NVHPC C 纯串行为 **28.91 s**。[同机对照数据](final_results_20261110/supplemental/cpu/summary.csv) |
| 单线程变慢的代码原因 | 反汇编显示，折叠版逐点执行下标进位、两次地址乘法和标量浮点运算。外层并行版把行地址乘法移出最内层，并生成带运行时检查的四点 SIMD 路径及标量备用路径。整数除法只用于初始化线程的起始坐标。此次测量未单独量化索引开销、SIMD 或硬件预取的贡献。[汇编证据](final_results_20261110/CPU_LOOP_EVIDENCE.md) |
| GPU E2E 分段计时 | 作业 `1536382.stdct-mgmt-02` 的 12 次计时均确认在 GPU 上执行。进入数据区占非驻留耗时的 **92.0%–99.7%**，包括映射、输入传输和可能的运行时初始化。驻留阶段已经包含每轮 target 启动和同步。[分段统计](final_results_20261110/supplemental/gpu/summary.csv) |
| GPU target 探针 | 独立探针的首次调用中位数为 **150.00 ms**，后续调用为 **20.98 µs**。探针含同步与一个标量回传，计时范围与求解器不同。[探针原始记录](final_results_20261110/supplemental/gpu/target_probe.csv) |
| CPU 线程扩展 | 作业 `1536540.stdct-mgmt-02` 测试 1、2、4、8、16、24、36 线程。256³、K=1000 下，36 线程在测试配置中最快，耗时 **2.644 s**，相对同批单线程加速 **19.50×**，并行效率 **54.2%**。[扩展统计](final_results_20261110/supplemental/scaling/scaling.csv) · [耗时图](final_results_20261110/supplemental/scaling/scaling_median_s.png) · [加速比图](final_results_20261110/supplemental/scaling/scaling_speedup.png) · [效率图](final_results_20261110/supplemental/scaling/scaling_efficiency.png) |
| 模型有效带宽 | 256³ 的 GPU resident 为 **247.36 GB/s**，CPU12 为 **84.18 GB/s**。使用每个网格点更新 24 字节的模型，单位为十进制 GB/s。[派生数据](final_results_20261110/formal/formal_derived.csv) |

早期跨分配的 256³ 中位数为 A 串行 39.01 s、B MPI P1 45.53 s、C OpenMP CPU1 51.45 s。A 使用 CN-161 上的 GCC 12.2，B 使用独立分配上的 GCC 12.2 和 Open MPI 4.1.5，C 使用 GN-A40-024 上的 NVHPC 24.7。解释 C 单线程偏慢时，引用上表的同机对照和反汇编。

[合稿包](final_results_20261110/) 包含正文、样本、汇总表和图表。CPU 首次作业 `1536381` 因 GCC 模块依赖冲突在编译阶段失败，同机对照统计使用成功重试 `1536409`。原始作业日志和调度截图由 C 成员保留。

## 在 Vanda 复现补测

进入 `c_openmp/nov10_followup` 后，把下列项目名替换为自己的 Vanda 项目。根据需要选择提交的补测。共享 [PBS 脚本](followup.pbs) 保留成功重试时的模块加载顺序，运行使用随附的 [源码](source/) 和 [计时脚本](run_followup.py)。

```bash
project='YOUR_VANDA_PROJECT'
qsub -P "$project" -v C_SUITE=cpu followup.pbs
qsub -P "$project" -v C_SUITE=gpu followup.pbs
qsub -P "$project" -v C_SUITE=scaling followup.pbs
```

输出位于当前目录的 `runs/`。正式三规模数据见 [原正式结果](../deliverables/formal_20261106/README.md)。

合稿前，请填好姓名、学号，确认个人贡献、AI 使用和本人核验过的内容，再把新版 C 章节及图表交给 A。合稿后复核 PDF 中的数字、图表编号、引用与声明。[贡献和 AI 使用声明草稿](final_results_20261110/CONTRIBUTION_AI_DRAFT.md)
