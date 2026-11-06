# C 正式三规模结果：2026-11-06

本页使用正式 job **1525886.stdct-mgmt-02** 的本地已下载证据。已核对 run.log 的 COMPLETED / JOB_EXIT_STATUS=0、run_status、样本数量和每个配置的 repeat，以及样本 CSV 与逐次 stdout 时间一致性。当前下载中没有独立 PBS 最终 qstat 记录，因此不把日志退出码冒充 PBS 历史 Exit_status。

## 验收与环境

- suite=formal、status=COMPLETED、cpu_only=false；18 项验证、6 组 CPU/GPU 全网格比较通过，六组最大差均为 0。
- 36 次性能调用：9 次预热、27 次 measured；64³/128³/256³ × CPU1/CPU12/GPU，每配置 repeat=1/2/3 齐全。GPU 两类时间来自同一次调用。
- 正式节点 **GN-A40-024**，Intel Xeon Platinum 8452Y；NVIDIA A40、46068 MiB，驱动 **575.57.08**。
- NVHPC/24.7-CUDA-12.3.0、GCC 13.2.0；分配 36 个 CPU 核和 1 GPU，CPU 比较使用 1 / 12 线程。240 GB 是本次已确认资源记录；实际硬件与软件证据见 environment.json 和 run.log。
- pilot 节点 GN-A40-036、驱动 610.43.02 与本批不同；正式曲线只使用本批，不能拼入 pilot 数字。
- 整理核验时 7 个核心源码/脚本与正式运行快照逐字节一致；本次仅更新了当前 analyze_c.py 的完整矩阵验收和绘图，求解器、构建及运行等其余 6 个文件仍一致；下载的 GPU 二进制 SHA256 与 environment.json 一致。

## 正式耗时（秒）

固定 K=1000、double、相同初值/边界/工作量。以下为排除 warmup 后三次测量中位数；原始 min/max 见 summary.csv。

| 规模 | CPU1 | CPU12 | GPU resident | GPU end-to-end |
|---|---:|---:|---:|---:|
| 64³ | 0.802221 | 0.124330 | 0.053188 | 0.156299 |
| 128³ | 6.330078 | 0.867985 | 0.204269 | 0.308162 |
| 256³ | 51.450687 | 4.783182 | 1.627774 | 1.779479 |

| 规模 | CPU12 加速比 | CPU12 效率 | GPU resident / CPU12 速度比 | GPU e2e / CPU12 速度比 |
|---|---:|---:|---:|---:|
| 64³ | 6.45× | 53.8% | 2.34× | 0.80× |
| 128³ | 7.29× | 60.8% | 4.25× | 2.82× |
| 256³ | 10.76× | 89.6% | 2.94× | 2.69× |

GPU 速度比统一定义为 CPU12 时间 / GPU 时间，大于 1 表示 GPU 更快。

## 可以得出的结论

1. 64³ 时，GPU 驻留比 CPU12 快，但端到端仍较慢；128³ 和 256³ 时，GPU 端到端分别比 CPU12 快约 2.82×、2.69×。在本次离散测试点上，端到端优势从 128³ 出现；没有测量精确交叉规模。
2. GPU resident 相对 CPU12 的速度比为 2.34× → 4.25× → 2.94×，**并非随规模单调增大**；相对 CPU1 则约为 15.08× → 30.99× → 31.61×。必须写清 CPU 基准。
3. `(e2e中位数-resident中位数)/e2e中位数` 约为 66.0%、33.7%、8.5%。说明两种计时口径的相对差距下降；该差值包括设备分配、映射、传输、释放等，不能单独归因于 PCIe 或初始化某一项。
4. CPU12 的速度比和效率随这三个规模上升，但只有 1/12 线程对照，不能宣称已找到最优线程数或完整线程扩展规律。
5. CPU12 的三次样本存在波动，尤其 128³ 为 0.572921–0.870379 s；按既定规则保留全部有效样本，报告中位数和范围，不删除快/慢样本。

## 数值与计时限制

小案例的 CPU/GPU 全网格一致不代表三个大规模均做了逐点导出比较；性能样本使用 runner 的诊断与残差一致性检查。三规模相对残差约为 0.0047745、0.00626234、0.00666474，固定 1000 轮不代表达到统一收敛阈值。

resident 含 K 次 kernel 启动和同步，并非 kernel-only 设备事件时间。end-to-end 含设备数据区建立、传入、迭代、最终解回传和退出数据区，不含主机数学初始化、最终诊断和文件 I/O。三次 min/max 不是置信区间。本次结论限于上述节点、软件栈和固定工作量。

## 证据入口与后续交付

- 完整 run.log 仅保留在作者本机 results 中，不随仓库发布。
- [run_status.json](../deliverables/formal_20261106/run_status.json)
- [samples.csv](../deliverables/formal_20261106/samples.csv)
- [summary.csv](../deliverables/formal_20261106/analysis/summary.csv)
- [speedups.csv](../deliverables/formal_20261106/analysis/speedups.csv)
- [裁剪后的平台配置 environment.json](../deliverables/formal_20261106/environment.json)
- 本地详细核验记录仅保留在作者本机；仓库提供 [验证简表](../deliverables/formal_20261106/analysis/validation_summary.csv)。

已生成并检查 runtime.png / speedup.png（300 dpi）与同名矢量 PDF；`.venv` 绘图环境已建立，依赖版本保存在 requirements-plots.txt。实现、设置、验证表和讨论见 [中文成果 README](C_RESULTS_README_zh.md)。当前先审阅中文稿，英文 final_C_openmp.md 暂不撰写；contribution / AI usage 与向 A 发送材料未执行。无需重新排队 formal。
