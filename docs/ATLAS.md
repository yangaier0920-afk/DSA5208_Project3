# Atlas 作业脚本

`atlas_serial.pbs` 和 `atlas_parallel_smoke.pbs` 是已跑通的历史小作业脚本，编译时从**提交目录**读取根目录源码。因此应在本仓库根目录 `qsub atlas_serial.pbs`，不要把脚本单独移动到另一个目录后提交。

| 脚本 | 历史申请 | 实际功能 |
|---|---|---|
| `atlas_serial.pbs` | serial，1 CPU，2GB，5 分钟上限 | 编译串行 Jacobi，运行 n=1/2/16/32 |
| `atlas_parallel_smoke.pbs` | parallel，12 CPU/12 MPI slots，2GB，5 分钟上限 | MPI 2/4/12 和 OpenMP 4/12 环境检查 |

脚本要求 PBS 环境变量，不能直接在登录节点用 bash 执行。编译和数值运行在计算节点完成。脚本使用 GCC 12.2.0、OpenMPI 4.1.5-GCC-12.2.0 及 `/app1/ebenv`；这些来自 2026-10-23 的成功作业，提交前核对集群当前模块、队列和资源限制。

运行输出写入 `results/atlas_serial_<jobid>/` 或 `results/atlas_smoke_<jobid>/`；提交后保存 qstat 完整状态、源码 hash、脚本和原始结果。`results/` 默认被 Git 忽略，正式共享时审查并选入 `evidence/`。

第二个脚本没有编译或运行 MPI/混合 Jacobi，不能作为混合算法正确性或加速比证据。已有小样本耗时不用于正式扩展性结论。正式混合 PBS 资源、P/T 配置与核绑定仍待 B/C 实现及实测。
