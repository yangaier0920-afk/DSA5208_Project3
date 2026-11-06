# C 的正式实验成果（2026-11-06）

本目录为组员复现图表及合稿所需的精简成果；来源为已完成的 v5 三规模正式实验。完整原始证据保留在作者本机，不混入历史 pilot。

- `samples.csv`：36 行性能数值，9 warmup、27 measured；不是终端转录。
- `run_status.json`：实验协议和完成状态。
- `environment.json`：裁剪后的平台、编译器与资源设置，仅用于复现图注；没有账号、调度 cookie、GPU UUID 或绝对路径。
- `analysis/`：两张 PNG 与矢量 PDF、时间/速度比 CSV、验证简表、图注和图表元数据。

从模块根目录运行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-plots.txt
.venv/bin/python analyze_c.py deliverables/formal_20261106
```

分析仅重写派生图表，不更改 samples.csv。正式结果解读见 [中文说明](../../docs/C_RESULTS_README_zh.md)。
