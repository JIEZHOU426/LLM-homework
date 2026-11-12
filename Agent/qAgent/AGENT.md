# qAgent 项目约定（示例 AGENT.md）

> 本文件演示 qAgent 的“项目规则”能力：启动时整份读取一次，作为一条 system
> 消息注入会话，之后每轮复用同一条消息（不重复注入、不破坏 prompt cache），
> 并随会话事件日志一起持久化，恢复会话时原样还原。
> 文件名可改：`[agents] filename` 或环境变量 `QAGENT_AGENTS_FILE`；
> `AGENT.md` 与 `AGENTS.md` 互为等价名。

## 回答与语言

- 一律使用简体中文；代码、命令、路径保持原文。
- 结论先行，再给依据；不确定时说明不确定在哪里，不要编造文件内容或运行结果。

## 工具使用

- 读写文件前先用 `list_directory` / `get_file_type` 确认目标存在与类型。
- 删除、覆盖前必须已在会话里说明“将要删除/覆盖哪个路径”，再执行。
- 文件工具默认限制在工作目录内；需要跨目录时先在 `config.ini` 里把
  `[files] confine_to_workspace` 设为 `false`，不要绕过工具直接改盘。

## 代码风格

- Python 走 `from __future__ import annotations`，函数与类必须写中文或英文
  docstring，注释解释“为什么”而不是“是什么”。
- 新增工具必须实现 `Tool` 契约（`spec` + `run`），并补一条 unittest。

## 变更记录

- 改协议、改配置项、改目录结构时，同步更新 `README.md` 与 `config.ini.example`。
