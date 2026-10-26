# 文件整理与完整性

此目录是供小组 GitHub 共享和后续开发使用的工作副本。原项目目录、WSL 副本、Atlas 完整下载及个人诊断记录仍在原处保留。

## 保留在共享目录中的内容

- 根目录三份 C++、两份 Python、参数 JSON 和两份 PBS：与整理时的原文件逐字节一致。
- `docs/TEAM_CONTRACT.zh-CN.md`：原参数文档的共享副本，调整了本仓库内链接。
- `reference/cases/`：14 个原始 stdout JSON，含 10 个正确性案例和 4 个本机性能试跑。
- `reference/reference_results.json` 与 `reference/local_pilot.json`：原汇总的共享派生副本，仅修改命令中的可执行文件路径，并增加派生说明及原文件 SHA-256；数值结果对象保持原样。
- `reference/contract_at_run.json`：参考运行时原配置的字节重建，SHA-256 与汇总记录一致；`contract_snapshot.json` 为当时保存的同内容格式化快照。根目录配置已更新 A 的采纳状态，数值参数没有改变。
- `evidence/`：Atlas 原始数值输出与派生摘要，不包含个人登录输出及完整 PBS 诊断信息。

## 留在原工作区的材料

个人 WSL 安装/故障记录、磁盘路径、VS Code 截图、培训 PDF、课堂截图、编译后的程序、完整终端日志、Atlas 重复下载和其他临时文件。它们不属于小组代码入口，但原始证据未删除。

`PACKAGE_MANIFEST.json` 记录整理时每个交付文件的大小和 SHA-256，清单自身不计入清单。后续开发修改文件后，该清单代表初次交付基线，不能再用它声称所有文件仍未改变。

JSON 证据和原项目要求文件关闭了 Git 换行转换，保留原始字节；源码与 PBS 脚本使用 LF。这样 clone 后仍可用交付清单核对字节校验值。
