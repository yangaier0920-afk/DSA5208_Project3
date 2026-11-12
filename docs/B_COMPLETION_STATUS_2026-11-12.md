# B 完成状态（2026-11-12）

已核验并归档：9 节点 144 核三规模强扩展、弱扩展、分轴诊断；参考节点 RTT；432/720 核历史作业（PBS 退出码均为 0）。

最新成功采集状态时间：2026-11-12T15:04:13.068685+08:00。该时间之后 SSH 意外断开，以下是历史快照，不能当作实时状态。

| experiment | job | state | exit_status |
|---|---|---|---|
| clean144 | 1536849.stdct-mgmt-02 | F | 0 |
| paired144 | 1536850.stdct-mgmt-02 | Q | None |
| baseline | 1546654.stdct-mgmt-02 | R | None |
| optimize72 | 1546655.stdct-mgmt-02 | H | None |
| suspect_diag | 1536853.stdct-mgmt-02 | Q | None |
| link_suspect | 1546667.stdct-mgmt-02 | Q | None |
| link_reference | 1536855.stdct-mgmt-02 | F | 0 |

整节点 P1、72 核优化消融、4 节点 144 核配对矩阵仍需采集完成证据；原异常节点诊断与探针仍排队。2D 扩展脚本已准备，尚未提交。任务尚未全部完成，不能将排队作业当成结果。

结果与原始证据：[B 补充结果](../b_mpi/nov12/final_results_20261112/README.md)。恢复 SSH 后继续采集，运行 analyze_feedback.py 与 build_results.py，脚本只接受完整且退出码为 0 的正式作业。

九节点复测的节点/布局已变化，不能据此唯一认定 CN-011/CN-108 硬件故障。所有慢样本保留；不以单调加速或预测时间作为筛选条件。
