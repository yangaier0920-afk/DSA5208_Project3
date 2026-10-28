# A/B最新证据汇总：截至2026-10-28

新增1501884的1024/2048同分配数据及非对称正确性；旧10月27日目录保留。当前共四个性能作业、五个规模数据集，各自使用本作业本规模的串行及同策略MPI P=1基准，不合并样本。

- [经复核中文分析](../vanda_1501884_ab_supplement/analysis_reviewed.md)：当前解释、局限及停止追加实验的边界。
- [performance_comparison.csv](performance_comparison.csv)：全部45配置，含min/max、样本CV、双基准加速比/效率。
- [measurement_samples.csv](measurement_samples.csv)：450次性能执行，含45次预热和405次正式；全部保留。
- [communication_comparison.csv](communication_comparison.csv)：20个通信比较，区分“中位数之比”与“同轮降低的中位数”。
- [execution_sequence_1501884.csv](execution_sequence_1501884.csv)：本次180条实际执行顺序，时间以UTC+8明确记录。
- [asymmetric_validation.csv](asymmetric_validation.csv)：31次完整小网格逐点验证。
- [source_binary_identity.csv](source_binary_identity.csv)：36项历史源码/程序一致性比较。
- [same_allocation_scale_ratios.csv](same_allocation_scale_ratios.csv)：本次各配置2048/1024中位耗时比，仅为描述统计。
- [new_job_review.json](new_job_review.json)：日志顺序、构建、上传快照、NUMA与额外串行前检核对。
- [raw_archives_manifest.json](raw_archives_manifest.json)：六份原件归档及SHA-256。

三幅图分别展示全正式轮次、当前双基准扩展、各历史分配。误差线仅为min/max。当前显著的逐轮变化不删除，不按快慢挑选子集。统计支持“此分配内时间变化明显”，不支持已确定共享负载/频率/带宽/NUMA原因或已证明底层通信重叠。

四套原结构化验证共有352次数值、16次拒绝，另有31次非对称数值；独立全网格执行共203次（172原问题+31非对称）。这些是重复套件执行数，不是203个独立数学问题。沿用verify_small的额外串行前检不计入以上结构化总数；本次另有6次，其中3次有保留的数值日志。

重建：从仓库根目录运行 `python summarize_ab_supplement.py --out-dir results/ab_summary_rebuild_NEW`，输出目录必须不存在。本脚本只读现有原件，不运行求解器；原始审计先运行audit_ab_supplement.py并指定全新的审计目录。图表已人工目视复核。
