# A 固定工作量串行规模结果（2026-11-05）

正式结果：Vanda 1522376.stdct-mgmt-02，CN-161，Xeon Platinum 8452Y，GCC12.2.0/-O2。
PBS已结束、退出0，walltime 6分23秒；获配两CPU槽，单线程程序绑定CPU65。

10配置、10预热、30正式，全部固定1000轮。小案例2D/3D离散误差分别1.11e-15/2.78e-15；全部运行边界误差0。
核对下载源码/runner哈希、40次原始输出与样本、10行统计，通过；见 verification.json。
二进制哈希由原runner记录，本地没有下载的Linux二进制，未另行验证二进制文件。

- 2D全区间边长增长指数2.066；3D为2.995，接近2/3理论值。
- 每点每轮中位成本：2D 1.70–2.10ns；3D 2.05–2.36ns。
- 最大2D/3D中位耗时34.296/39.009秒。固定工作量结果与收敛研究分开解释。
- 原始下载保留在 [批次目录](../../a_scaling_20261104/Vanda_1522376.stdct-mgmt-02/)，不改原件。
- [独立英文小节](../../docs/A_SERIAL_SCALING_2026-11-05.md)已合入 [A完整章节](../../docs/final_A_numerics.md)。

复现图表（仓库根目录）：

```bash
python a_scaling_20261104/analyze_a_scaling.py a_scaling_20261104/Vanda_1522376.stdct-mgmt-02 --output evidence/vanda_1522376_a_scaling
```

serial_scaling 和 point_update_cost 各提供PNG/PDF。图中点为三次正式中位数，误差棒min/max，时间和规模坐标为对数。
最终提交选PDF报告、源码、README、必要脚本和精简数值CSV；本目录验证记录和原始终端日志保留内部。
