# C 模块合稿资料 · 2026-11-10

正式矩阵和三项补测均已完成，四个有效作业的 PBS 退出码为 0。英文 C 章节已纳入本轮补测，可交给 A 合稿。[英文 C 章节](final_C_openmp.md) · [PBS 作业索引](PBS_status.csv) · [11 月 9 日评语处理表](REVIEW_RESPONSE_20261111.md)

| 作业 | PBS ID | 节点 | 耗时 | 正式测量 |
|---|---|---|---:|---:|
| 正式矩阵 | 1525886.stdct-mgmt-02 | GN-A40-024 | 00:05:29 | 27 |
| CPU 同机诊断 | 1536409.stdct-mgmt-02 | GN-A40-024 | 00:18:38 | 24 |
| GPU 分段计时 | 1536382.stdct-mgmt-02 | GN-A40-094 | 00:00:47 | 9 |
| CPU 线程扩展 | 1536540.stdct-mgmt-02 | GN-A40-024 | 00:07:44 | 21 |

## 结果与证据

- 正式矩阵含 36 次计时，其中 27 次用于统计。三规模的 CPU1、CPU12 和单 GPU 结果均保留。[正式中文说明](../../docs/FORMAL_RESULTS_20261106.md) · [样本](../../deliverables/formal_20261106/samples.csv) · [汇总](../../deliverables/formal_20261106/analysis/summary.csv) · [速度比](../../deliverables/formal_20261106/analysis/speedups.csv) · [耗时图](../../deliverables/formal_20261106/analysis/runtime.png) · [加速比图](../../deliverables/formal_20261106/analysis/speedup.png)
- CPU 同机对照的 8 种配置各有 1 次预热和 3 次正式测量。NVHPC 单线程只并行外层循环时为 28.84 秒，折叠三个循环时为 51.38 秒，耗时减少 43.9%。反汇编显示折叠版的逐点循环多了下标进位与地址乘法，外层并行版则把行地址移出内循环，并生成了带运行时检查的四点 SIMD 路径。[汇编证据](CPU_LOOP_EVIDENCE.md) · [样本](supplemental/cpu/samples.csv) · [汇总](supplemental/cpu/summary.csv)
- GPU 分段计时的 12 次运行均通过设备执行核验。数据区进入占非驻留耗时的 92.0%–99.7%。独立探针首次调用的中位数是 150.00 ms，后续调用是 20.98 µs。两个计时实验在不同运行中采集，报告保留各自计时范围。[样本](supplemental/gpu/samples.csv) · [分段汇总](supplemental/gpu/summary.csv) · [探针](supplemental/gpu/target_probe.csv)
- 线程扩展的 7 个配置均通过小网格核验。36 线程在所测配置中耗时最短，为 2.644 秒，较同批单线程加速 19.50 倍，并行效率为 54.2%。[样本](supplemental/scaling/samples.csv) · [汇总](supplemental/scaling/scaling.csv) · [耗时图](supplemental/scaling/scaling_median_s.png) · [加速图](supplemental/scaling/scaling_speedup.png) · [效率图](supplemental/scaling/scaling_efficiency.png)
- 256³ 模型有效带宽为 GPU resident 247.36 GB/s、CPU12 84.18 GB/s。使用每次更新 24 字节的模型。[派生数据](formal/formal_derived.csv)
- CPU 首次作业 1536381 在编译阶段退出，统计使用成功重试作业 1536409。原始调度截图与作业日志由 C 成员保留。[正式 PBS 历史摘录](../evidence/README.md) · [补测复现说明](../README.md)

## 合稿前还需要什么

1. C 成员填写姓名和学号，确认本人实际完成的工作、自己核对过的证据，以及能够独立解释的内容。按照真实使用情况修改 AI 声明并确认后发给 A。[Contribution 和 AI use 草稿](CONTRIBUTION_AI_DRAFT.md)
2. 将英文 C 章节和图表交给 A。A 用新版替换总报告中的旧 C 内容，核对图表编号、引用、其他成员声明和课程提交要求。[英文 C 章节](final_C_openmp.md)
3. A 合稿后，复核最终 PDF 中的 PBS 退出状态、CPU 对照、GPU 分段和线程扩展数字，并确认上传范围。正式矩阵和这三项补测已齐备。
