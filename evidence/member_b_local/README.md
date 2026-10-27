# 本地证据，2026-10-27

此目录只记录本机 Mac 验证，不是 Atlas/Vanda 性能证据。四个程序编译成功，原串行/OpenMP 验证通过；MPI/混合综合验证 278 次执行通过；另有 4 个大 halo 对照检查。小规模重复计时共 24 次执行，只检查工具流程，不据此讨论扩展性。

validation_summary.json 保留原始汇总，包括完整命令和每次结果；逐次原始 stdout/stderr 在忽略目录 results/b_local_validation，可用验证器重新生成。build.log 记录实际编译选项。源码及程序哈希见汇总与 metadata.json。C++ 源码在测试后未改变。
