# CapsWriter 本轮改造说明（2026-03-17）

本文档用于完整记录本轮“语音命令编辑 + 前文润色 + 发送/换行语义 + 剪贴板恢复”相关改造。

---

## 1. 改造目标

本轮改造围绕以下真实使用问题展开：

1. 需要把“发送 / 回车 / 换行”从纯文本换行，升级为可控命令动作。
2. 需要“把 A 替换成 B”“润色前文”这类命令式编辑能力，而不是只输出新文本。
3. 需要支持“润色最近 N 次输入”，用于跨多次听写后统一改写。
4. 需要避免误伤终端窗口（PowerShell/CMD/Windows Terminal）。
5. 需要在所有涉及剪贴板的流程中，尽量完整恢复用户剪贴板（不仅文本）。

---

## 2. 总体设计思路

### 2.1 命令词驱动 + 输出动作解耦

- 在 `hot-rule.txt` 中把命令词映射到内部控制标记：
  - `[[CW_SEND]]`
  - `[[CW_NEWLINE]]`
- 在输出层 `TextOutput` 中统一解析控制标记并执行真实键盘动作（Enter / Ctrl+Enter / 粘贴）。
- 目标：避免标记被当作普通文本打出来，并兼容 typing/paste/LLM 各条输出路径。

### 2.2 前文编辑走“安全优先”

- 默认对“最近输出”做回删+重写，不默认 `Ctrl+A` 全文覆盖。
- 终端窗口下拦截高风险命令。
- 支持显式 `全选` 命令，但在终端默认拦截。

### 2.3 润色前文支持两类数据源

- 优先：当前选中文本（用户已全选/选区时）
- 兜底：最近 N 次输出拼接（未选中时）

### 2.4 剪贴板恢复“尽力完整”

- Windows 下尝试备份/恢复多格式剪贴板（文本/图片/富文本等可读格式）。
- 失败时回退文本恢复。

---

## 3. 代码变更清单（按文件）

## `hot-rule.txt`

### 变更内容

- 新增并调整命令映射：
  - `回车` / `发送` -> `[[CW_SEND]]`
  - `换行` -> `[[CW_NEWLINE]]`
- 增加口语尾词兼容：
  - `发送啊` / `回车吧` / `换行呀` 等。

### 目的

- 命令词语义明确化（发送 vs 换行）。
- 提升自然口语触发成功率。

---

## `util/client/output/text_output.py`

### 变更内容

1. 新增控制标记常量：
   - `SEND_TOKEN = [[CW_SEND]]`
   - `NEWLINE_TOKEN = [[CW_NEWLINE]]`
2. 新增动作解析函数 `_iter_output_actions()`：
   - 将文本拆解为 `text/send/newline` 动作序列。
3. 粘贴模式 `_paste_text()` 改造：
   - 文本片段用 Ctrl+V 粘贴；
   - `send` 动作发送 Enter；
   - `newline` 动作在微信使用 Ctrl+Enter，其他窗口 Enter。
4. 打字模式 `_type_text()` 同步支持上述动作语义。
5. 新增 `_is_wechat_window()` 做微信窗口检测。
6. 剪贴板恢复从“文本恢复”改为“状态恢复”：
   - 调用 `backup_clipboard_state()` / `restore_clipboard_state()`。

### 目的

- 保证命令标记不会直接输出到输入框；
- 统一不同输出方式语义；
- 微信中区分发送与换行；
- 尽量恢复原剪贴板内容。

---

## `util/llm/llm_output_typing.py`

### 变更内容

1. `output_text()` 统一走 `TextOutput.output()`（不再直接 `keyboard.write`）。
2. `_process_paste()` 改为调用 `output_text(..., paste=True)`。
3. `_process_streaming()` 的实时输出从 `keyboard.write` 改为 `TextOutput._type_text()`。

### 目的

- 修复“LLM 路径下 `[[CW_SEND]]` 被当作文本输出”的漏网路径；
- 确保 LLM 输出与普通输出行为一致。

---

## `util/client/output/result_processor.py`

### 变更内容

1. 新增命令处理入口 `_try_handle_edit_commands()`，实现：
   - 删除类：`退格`、`删除N个字`、`删除一句`
   - 全选类：`全选`（终端拦截）
   - 替换类：`把A替换成B` / `把A换成B`
   - 润色类：`润色前文`、`润色最近N次输入`、`润色多次输入`、`把前面这段改得更...`
2. 新增终端检测 `_is_terminal_window()`，降低误操作风险。
3. 新增多次输入处理：
   - `_get_recent_outputs()` / `_replace_recent_outputs()`
4. 新增替换词归一化 `_normalize_replace_term()`：
   - 支持“家庭的家 -> 家”“加法的加 -> 加”口语表达。
5. 新增选区优先润色逻辑：
   - `_copy_selected_text()` 读取选中内容；
   - 若有选区，润色后直接覆盖选区；
   - 无选区再回退到最近输出拼接。
6. 剪贴板读写流程统一改为状态备份/恢复（完整格式优先）。

### 目的

- 把命令词转成可落地编辑动作；
- 支持跨多次输入的前文改写；
- 修复“润色前文只把提示词本身改写”的错误使用路径；
- 提升口语替换鲁棒性；
- 避免终端场景误操作。

---

## `util/client/state.py`

### 变更内容

1. 新增 `output_history: List[str]`，记录最近输出历史（上限 100）。
2. `set_output_text()` 增加空文本保护：
   - 空文本（如 `/sil`）不覆盖 `last_output_text`。

### 目的

- 支持“润色最近 N 次输入”；
- 避免无效识别把“最近有效输出”冲掉。

---

## `util/client/clipboard/clipboard.py`

### 变更内容

1. 新增 `backup_clipboard_state()`：
   - Windows + `win32clipboard` 时，枚举并备份可读格式；
   - 其他情况回退文本备份。
2. 新增 `restore_clipboard_state()`：
   - 还原多格式剪贴板或文本剪贴板。
3. `save_and_restore_clipboard()` 改用新备份/恢复机制。
4. `paste_text()` 改用新备份/恢复机制。

### 目的

- 解决“剪贴板可能包含图片/富文本，文本恢复会破坏用户数据”的问题。

---

## `util/client/clipboard/__init__.py`

### 变更内容

- 导出新增 API：
  - `backup_clipboard_state`
  - `restore_clipboard_state`

### 目的

- 方便其他模块统一复用。

---

## `util/llm/llm_get_selection.py`

### 变更内容

- 获取选区前后改为使用：
  - `backup_clipboard_state()`
  - `restore_clipboard_state()`
- 不再只恢复纯文本。

### 目的

- 读取选区时避免破坏用户原剪贴板的非文本内容。

---

## `util/llm/llm_role_config.py`

### 变更内容

- 新增角色字段：
  - `allow_selection_same_as_last_output`
  - `force_paste_for_replace`

### 目的

- 支持润色场景的细粒度行为控制（例如可润色刚输出文本、强制粘贴替换选区）。

---

## `util/llm/llm_handler.py`

### 变更内容

1. 对“润色”角色增加“必须有选区”提示保护（角色模式下）。
2. 支持 `force_paste_for_replace`，必要时强制粘贴模式。

### 目的

- 避免误触发；
- 保证润色结果覆盖选中内容而非追加输出。

---

## `LLM/润色.py`

### 变更内容

1. 新增“润色”角色配置（可被命令模式调用）。
2. 调整 system prompt 为“按要求改写原文”范式。
3. 关键配置：
   - `force_paste_for_replace = True`
   - `allow_selection_same_as_last_output = True`
   - `enable_history = False`

### 目的

- 让润色更符合“编辑器内文本改写”的实际需求，而非闲聊问答。

---

## `readme.md`

### 变更内容

- 新增“命令词与前文编辑”说明章节；
- 补充发送/换行、删除、替换、润色命令以及安全策略的说明。

---

## 4. 当前行为总结（用户视角）

1. 发送/回车/换行支持口语命令，并区分微信场景发送与换行。
2. 支持删除类语音命令。
3. 支持替换最近输出（口语“X的Y”可解析）。
4. 支持润色前文、润色最近 N 次输入。
5. 你先全选后说“润色前文，xxx”会优先处理选区。
6. 终端窗口默认拦截高风险编辑命令。
7. 剪贴板恢复尽量保持原样（文本+多格式）。

---

## 5. 已知边界与注意事项

1. 回删替换依赖“光标仍在目标文本末尾”；若中间移动光标，效果会偏差。
2. Windows 多格式剪贴板恢复属于“尽力而为”，个别应用私有格式可能不可读。
3. 命令触发受 ASR 识别质量影响，建议命令词单独短说。
4. 改动后需重启 `start_client` 使 Python 代码生效。

---

## 6. 推荐后续优化

1. 新增“替换命令调试日志”（打印 old/new/source_len）。
2. 新增“仅改最后一句 / 最后 N 句”命令，进一步降低误删风险。
3. 为微信换行键提供配置项（Ctrl+Enter / Shift+Enter 可切换）。
4. 为前文编辑增加“可视确认弹窗”（可选）。

