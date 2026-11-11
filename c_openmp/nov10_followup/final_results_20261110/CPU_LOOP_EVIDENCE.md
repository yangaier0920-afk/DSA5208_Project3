# 单线程循环分工的汇编证据

证据取自 PBS 作业 1536409 保存的 x86-64 ELF 文件。两种 OpenMP 变体都用 NVHPC 24.7、`-O2 -mp=multicore`，测试同一节点的同一颗 CPU，网格为 256³，迭代 1000 次。两者用同一份 stencil，构建选项只改变工作分配使用外层循环还是 `collapse(3)`。[计时汇总](supplemental/cpu/summary.csv) · [PBS 脚本](../followup.pbs) · [stencil 源码](../source/jacobi_c_cpu_diag.cpp#L120)

| NVHPC 变体 | 单线程中位数 | 保存的二进制中的证据 |
|---|---:|---|
| `c_nv_collapse` | 51.377 s | 每个点更新下标并检查进位。见 `0x4059d1–0x4059f8` 的 `cmp/setg/cmovg`。随后 `0x405a0e` 和 `0x405a18` 用两次 `imul` 计算地址。stencil 用标量浮点指令，除法为 `vdivsd`。 |
| `c_nv_outer` | 28.837 s | 行地址乘法位于 `0x405b4f` 和 `0x405b61`，在最内层循环之外。运行时检查后的 SIMD 路径在 `0x405f20–0x405f9b`，包含 `ymm` 寄存器上的 `vaddpd`、`vdivpd`、向量存储，循环下标每次加 4。另有标量备用路径。 |
| 正式 `c_formal` | 51.396 s | CPU 工作函数也有逐点下标进位、两次地址乘法和标量 `vdivsd`。地址乘法位于 `0x405d4e` 和 `0x405d58`。 |

折叠版也有整数除法，用来把线程分到的扁平起始下标转换为三维坐标。它位于逐点循环之前，逐点循环的回跳不经过该段。因此，逐点额外开销应描述为索引进位、地址计算和标量运算，不能写成每个点都做两次整数除法。

编译日志中第 125 行的未向量化诊断没有完整反映外层并行二进制的代码路径。反汇编直接显示这个二进制同时含向量路径和标量备用路径。当前计时没有使用运行时采样来确认分支路径，也没有分别关闭 SIMD 和地址优化，所以无法给两项开销分配各自的耗时。硬件预取贡献也未单独测量。[折叠版编译日志](../evidence/c_nv_collapse.vec#L33) · [外层并行编译日志](../evidence/c_nv_outer.vec#L33)

可从原始作业的 `build` 目录复查诊断二进制：

```bash
llvm-objdump -d --no-show-raw-insn --line-numbers --x86-asm-syntax=intel   --disassemble-symbols=__nv_main_F1L110_1 c_nv_collapse
llvm-objdump -d --no-show-raw-insn --line-numbers --x86-asm-syntax=intel   --disassemble-symbols=__nv_main_F1L110_1 c_nv_outer
llvm-objdump -d --no-show-raw-insn --x86-asm-syntax=intel   --disassemble-symbols=__nv_main_F1L92_1 c_formal
```
