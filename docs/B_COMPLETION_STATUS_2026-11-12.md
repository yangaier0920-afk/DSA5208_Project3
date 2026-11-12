# B 完成状态（2026-11-12）

已核验并归档的作业以结果表与 PBS 退出码为准；下表中的 Q/H/R 不计入完成结果。

最新成功采集状态时间：2026-11-12T16:03:56.271157+08:00。以下为已保存快照，不能当作实时状态。

| experiment | job | state | exit_status |
|---|---|---|---|
| clean144 | 1536849.stdct-mgmt-02 | F | 0 |
| paired144 | 1536850.stdct-mgmt-02 | F | 0 |
| baseline | 1546654.stdct-mgmt-02 | F | 0 |
| optimize72 | 1546655.stdct-mgmt-02 | F | 0 |
| suspect_diag | 1536853.stdct-mgmt-02 | Q | None |
| link_suspect | 1546667.stdct-mgmt-02 | Q | None |
| link_reference | 1536855.stdct-mgmt-02 | F | 0 |
| twod | 1546883.stdct-mgmt-02 | F | 0 |

核心任务：整节点 P1、72 核优化消融、九节点及四节点 144 核矩阵均已通过独立 PBS/数值/绑定/重复次数核验。原异常节点诊断与探针的完成状态见下表；可选 2D 已另行跑通并核验；不将排队作业计为结果。

结果与原始证据：[B 补充结果](../b_mpi/nov12/final_results_20261112/README.md)。继续采集后运行 analyze_feedback.py 与 build_results.py，脚本只接受完整且退出码为 0 的正式作业。

九节点复测的节点/布局已变化，不能据此唯一认定 CN-011/CN-108 硬件故障。所有慢样本保留；不以单调加速或预测时间作为筛选条件。
