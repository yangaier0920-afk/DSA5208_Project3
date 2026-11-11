# 11 月 9 日评语处理表

更新于 2026-11-11。复核了正式 36 行计时、九种配置的中位数、GPU 设备标志、验证摘要与四个作业的退出状态。英文章节使用现有的正式矩阵和三项已通过的补测。[英文 C 章节](final_C_openmp.md) · [PBS 索引](PBS_status.csv)

| 反馈 | 当前结论与证据 |
|---|---|
| 正式矩阵和 64³ GPU E2E | 保留九种配置和全部正式样本。18 项小网格验证通过，6 组 CPU/GPU 全网格最大差为 0。64³ 的 GPU E2E 相对 CPU12 为 0.80×，128³ 和 256³ 分别为 2.82× 和 2.69×。[正式样本](../../deliverables/formal_20261106/samples.csv) · [验证表](../../deliverables/formal_20261106/analysis/validation_summary.csv) |
| CPU1 相比 A 串行、B MPI P1 | 原始 39.01 / 45.53 / 51.45 s 对应三套实现与运行条件。作业 1536409 在同机同核对照了 A 和 C，并在相同 NVHPC 构建条件下单独改变 C 的工作分配。去掉 `collapse(3)` 后 C 单线程从 51.38 s 降至 28.84 s，耗时减少 43.9%。折叠版逐点执行进位和地址乘法并使用标量 stencil，外层并行版把行地址计算移出最内层，并生成受运行时检查保护的四点 SIMD 路径。各因素的独立耗时仍未测量。[同机对照](supplemental/cpu/summary.csv) · [反汇编](CPU_LOOP_EVIDENCE.md) |
| 拆分 GPU E2E overhead | 作业 1536382 已分别计时数据区进入、驻留、回传、退出，并完成小 target 探针。进入阶段占非驻留时间的 92.0%–99.7%。探针首次与后续调用中位数分别为 150.00 ms 和 20.98 µs。进入阶段合并映射、运行时设置和输入传输，探针另含同步与标量回传。现有分段足以回应评语的诊断要求。[分段结果](supplemental/gpu/summary.csv) · [探针](supplemental/gpu/target_probe.csv) |
| GPU resident 加速比非单调 | 每次边长翻倍，CPU1 耗时增长 7.89×、8.13×，GPU resident 增长 3.84×、7.97×，CPU12 增长 6.98×、5.51×。两个基线的耗时增长不同，解释了 resident 相对 CPU12 为 2.34×、4.25×、2.94×。[正式中位数](../../deliverables/formal_20261106/analysis/summary.csv) · [加速比](../../deliverables/formal_20261106/analysis/speedups.csv) |
| CPU 线程扩展 | 作业 1536540 已完成 1、2、4、8、16、24、36 线程，256³、K=1000，每档三次正式测量。36 线程在所测配置中最快，2.644 s、19.50×、54.2% 效率。[线程扩展数据](supplemental/scaling/scaling.csv) · [耗时图](supplemental/scaling/scaling_median_s.png) · [加速图](supplemental/scaling/scaling_speedup.png) · [效率图](supplemental/scaling/scaling_efficiency.png) |
| PBS 完成证据与正式图 | 原正式作业 1525886 的独立 PBS 历史显示 `Exit_status = 0`。正式 runtime 和 speedup 均有 PNG/PDF，样本、汇总、验证简表和图注齐备。[PBS 历史摘录](../evidence/README.md) · [正式图表](../../deliverables/formal_20261106/analysis/) |
| 英文 C 章节 | 已完成并纳入三项补测。组员可从复现目录或合稿包打开。[复现目录英文稿](../../docs/final_C_openmp.md) · [合稿英文稿](final_C_openmp.md) |
| 成员贡献和 AI 声明 | 已准备草稿。待本人补姓名、学号、实际个人贡献和亲自核验的内容。[声明草稿](CONTRIBUTION_AI_DRAFT.md) |

现有结果足以完成 C 模块。重跑九种正式配置、加入 MPI+GPU 或多 GPU、用更多实验把 GPU 数据区进入拆成纯初始化和纯 PCIe 传输，均可从本次合稿任务中移除。剩余交付是确认个人声明，并由 A 把新版 C 章节与图表并入总报告后复核最终 PDF。
