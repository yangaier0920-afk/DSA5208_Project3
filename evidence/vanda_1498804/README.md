# Vanda 作业 1498804.stdct-mgmt-02

用户本人提交并下载，AI 于 2026-10-27 审计。此目录保存精选原始日志/汇总、绑定样例及派生分析，未修改原始数值。全量原始包在交接 ZIP 的 raw_evidence/vanda_1498804_results.tar.gz；SHA-256：`b8054404ae5277d68abaffc56f25dfd8574a69b44e377c9e9cb3892d0b4b7a8e`。

全量包含逐次 stdout/stderr、源码快照及原 Linux 程序。`audit.json` 记录本次从完整原件核对源码/程序校验值、278 次验证、156 次性能执行及统计的结果。此精选目录未重复保存程序和全部逐次文件，重新完整审计时先解压原始包，再运行根目录 analyze_results.py。

运行：`python3 analyze_results.py --results 解压后的Vanda_parallel_1498804.stdct-mgmt-02 --out-dir 自选新目录`。图表额外需要 matplotlib，并加 --plots；集群计算程序/验证器不依赖 matplotlib。

结论边界见 B_Vanda实验分析.md：仅单节点单规模；单进程实现差异、波动及 PBS 库警告未消除。
