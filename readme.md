# CapsWriter-Offline (v2.5)

![demo](assets/demo.png)

> **按住 CapsLock 说话，松开就上屏。就这么简单。**

**CapsWriter-Offline** 是一个专为 Windows 打造的**完全离线**语音输入工具。


## 🚀 更新说明：

v2.5新增：
- **语音清理（LLM 驱动）**：默认角色自动去除填充词（嗯/啊/呃）、口吃重复（我我我→我）、识别自我纠正（不是X，是Y→Y），全部由 LLM 智能判断，不使用硬编码规则
- **录音状态指示器**：录音时屏幕右下角显示脉冲动画，识别完成后短暂显示结果再淡出
- **应用感知语调**：自动获取当前活跃窗口的应用名称，传递给 LLM，让模型自行判断合适的输出风格（如微信口语化、邮件正式化）
- **格式化角色**：说"格式化"将口述文字整理成 Markdown 列表/步骤格式
- **只读查询命令**：`问一下`/`总结一下`/`解释一下`/`翻译一下` 对选中文字操作，结果在 Toast 弹窗显示，不会输出到光标位置
- **语音点击 UI 元素**：说"点击 XXX"模糊匹配当前窗口的按钮/菜单并点击（已内置打包）
- **语音快捷操作**：`搜索 X`（浏览器搜索）、`打开 X`（启动应用）、`截图`（Win+Shift+S）、`复制这段`
- **方向键与光标控制**：`上`/`下`/`左`/`右`（支持N次）、`Ctrl左`/`Shift下` 等组合键、`行首`/`行尾`/`文档开头`/`文档结尾`
- **删除指定词**：`删除XXXX` 从最近输出中找到并删除指定词
- **撤销/重做**：`撤销`（Ctrl+Z）、`重做`（Ctrl+Y）
- 修复音频缓冲区积压、异步死锁、润色前文无响应、语音替换不稳定等多个 Bug
- 修复 PyInstaller 打包后工作目录和子进程重复启动问题
- 完善打包配置，支持 Python 3.11 + PyInstaller 6.x

v2.4新增：
- **改进 [Fun-ASR-Nano-GGUF](https://github.com/HaujetZhao/Fun-ASR-GGUF) 模型，使 Encoder 支持通过 DML 用显卡（独显、集显均可）加速推理，Encoder 和 CTC 默认改为 FP16 精度，以便更好利用显卡算力**，短音频延迟最低可降至 200ms 以内。
- 服务端 Fun-ASR-Nano 使用单独的热词文件 hot-server.txt ，只具备建议替换性，而客户端的热词具有强制替换性，二者不再混用
- 可以在句子的开头或结尾说「逗号、句号、回车」，自动转换为对应标点符号，支持说连续多个回车。
- Fun-ASR-Nano 加入采样温度，避免极端情况下的因贪婪采样导致的无限复读
- 服务端字母拼写合并处理

v2.3新增：
- **引入 [Fun-ASR-Nano-GGUF](https://github.com/HaujetZhao/Fun-ASR-GGUF) 模型支持，推理更轻快**
- 重构了大文件转录逻辑，采用异步流式处理
- 优化中英混排空格
- 增强了服务端对异常断连的清理逻辑

v2.2 新增：
-   **改进热词检索**：将每个热词的前两个音素作为索引进行匹配，而非只用首音素索引。
-   **UDP广播和控制**：支持将结果 UDP 广播，也可以通过 UDP 控制客户端，便于做扩展。
-   **Toast窗口编辑**：支持对角色输出的 Toast 窗口内容进行编辑。
-   **多快捷键**：支持设置多个听写键，以及鼠标快捷键，通过 pynput 实现。
-   **繁体转换**：支持输出繁体中文，通过 zhconv 实现。

v2.1 新增：
-   **更强的模型**：内置多种模型可选，速度与准确率大幅提升。
-   **更准的 ITN**：重新编写了数字 ITN 逻辑，日期、分数、大写转换更智能。
-   **RAG 检索增强**：热词识别不再死板，支持音素级的 fuzzy 匹配，就算发音稍有偏差也能认出。
-   **LLM 角色系统**：集成大模型，支持润色、翻译、写作等多种自定义角色。
-   **纠错检索**：可记录纠错历史，辅助LLM润色。
-   **托盘化运行**：新增托盘图标，可以完全隐藏前台窗口。
-   **完善的日志**：全链路日志记录，排查问题不再抓瞎。

这个项目鸽了整整两年，真不是因为我懒。在这段时间里，我一直在等一个足够惊艳的离线语音模型。Whisper 虽然名气大，但它实际的延迟和准确率始终没法让我完全满意。直到 `FunASR-Nano` 开源发布，它那惊人的识别表现让我瞬间心动，它的 `LLM Decoder` 能识别我讲话的意图进而调整输出，甚至通过我的语速决定在何时添加顿号，就是它了！必须快马加鞭，做出这个全新版本。


## ✨ 核心特性

-   **语音输入**：按住 `CapsLock键` 或 `鼠标侧键X2` 说话，松开即输入，默认去除末尾逗句号。支持对讲机模式和单击录音模式。
-   **录音指示器**：录音时右下角出现脉冲动画，识别完成后短暂显示结果再淡出。
-   **文件转录**：音视频文件往客户端一丢，字幕 (`.srt`)、文本 (`.txt`)、时间戳 (`.json`) 统统都有。
-   **数字 ITN**：自动将「十五六个」转为「15~16个」，支持各种复杂数字格式。
-   **热词语境**：在 `hot-server.txt` 记下专业术语，经音素筛选后，用作 Fun-ASR-Nano 的语境增强识别
-   **热词替换**：在 `hot.txt` 记下偏僻词，通过音素模糊匹配，相似度大于阈值则强制替换。
-   **正则替换**：在 `hot-rule.txt` 用正则或简单等号规则，精准强制替换。
-   **纠错记录**：在 `hot-rectify.txt` 记录对识别结果的纠错，可辅助LLM润色。
-   **语音清理**：默认角色自动去除填充词（嗯/啊/呃）、口吃重复、自我纠正，全部由 LLM 智能判断。
-   **应用感知语调**：自动获取当前窗口应用名称传递给 LLM，让模型自行判断合适的输出风格。
-   **LLM 角色**：预置了润色、翻译、格式化、代码助手等角色，当识别结果的开头匹配任一角色名字时，将交由该角色处理。
-   **语音命令**：支持退格、替换、润色前文、格式化、搜索、打开应用、点击 UI 元素、截图等语音命令。
-   **只读查询**：对选中文字说"问一下/总结一下/解释一下/翻译一下"，结果在 Toast 弹窗显示，不影响光标位置。
-   **语音点击**：说"点击 XXX"模糊匹配当前窗口的按钮/菜单并点击（已内置打包）。
-   **托盘菜单**：右键托盘图标即可添加热词、复制结果、清除LLM记忆。
-   **C/S 架构**：服务端与客户端分离，虽然 Win7 老电脑跑不了服务端模型，但最少能用客户端输入。
-   **日记归档**：按日期保存你的每一句语音及其识别结果。
-   **录音保存**：所有语音均保存为本地音频文件，隐私安全，永不丢失。

**CapsWriter-Offline** 的精髓在于：**完全离线**（不受网络限制）、**响应极快**、**高准确率** 且 **高度自定义**。我追求的是一种「如臂使指」的流畅感，让它成为一个专属的一体化输入利器。无需安装，一个U盘就能带走，随插随用，保密电脑也能用。

LLM 角色既可以使用 Ollama 运行的本地模型，又可以用 API 访问在线模型。


## 💻 平台支持

目前**仅能保证在 Windows 10/11 (64位) 下完美运行**。

-   **Linux**：暂无环境进行测试和打包，无法保证兼容性。
-   **MacOS**：由于底层的 `keyboard` 库已放弃支持 MacOS，且系统权限限制极多，暂时无法支持。


## 🎬 快速开始

1.  **准备环境**：确保安装了 [VC++ 运行库](https://learn.microsoft.com/zh-cn/cpp/windows/latest-supported-vc-redist)。
2.  **下载解压**：下载 [Latest Release](https://github.com/HaujetZhao/CapsWriter-Offline/releases/latest) 里的软件本体，再到 [Models Release](https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models) 下载模型压缩包，将模型解压，放入 `models` 文件夹中对应模型的文件夹里。
3.  **启动服务**：双击 `start_server.exe`，它会自动最小化到托盘菜单。
4.  **启动听写**：双击 `start_client.exe`，它会自动最小化到托盘菜单。
5.  **开始录音**：按住 `CapsLock键` 或 `鼠标侧键X2` 就可以说话了！

如果你是直接 clone 源码仓库而不是下载 release，请额外看 [docs/CONFIGURATION.md](docs/CONFIGURATION.md)，里面说明了模型、Fun-ASR 本地 DLL 和 LLM override 的正确配置方式。


## 🎤 模型说明

你可以在 `config_server.py` 的 `model_type` 中切换：

-   **funasr_nano**（默认推荐）：目前的旗舰模型，速度较快，准确率最高。
-   **sensevoice**：阿里新一代大模型，速度超快，准确率稍逊。
-   **paraformer**：v1 版本的主导模型，现主要作为兼容备份。


## ⚙️ 个性化配置

所有的设置都在根目录的 `config_server.py` 和 `config_client.py` 里：
-   修改 `shortcut` 可以更换快捷键（如 `right shift`）。
-   修改 `hold_mode = False` 可以切换为“点一下录音，再点一下停止”。
-   修改 `llm_enabled` 来开启或关闭 AI 助手功能。


## 🧠 命令词与前文编辑（v2.4+）

除了普通听写，本项目现在支持”命令词”直接编辑最近输出内容。
命令词基于客户端 `hot-rule.txt` 和 LLM 角色协同实现，默认不做全文 `Ctrl+A` 覆盖，以避免误伤终端等场景。

### 1) 发送与换行

- `发送` / `回车`：触发发送动作（`[[CW_SEND]]`）
- `换行`：触发换行动作（`[[CW_NEWLINE]]`）
- 微信中：`发送` 用 `Enter`，`换行` 用 `Ctrl+Enter`（不发送）
- 支持口语结尾，如：`发送啊`、`换行呀`、`回车吧`

### 2) 删除命令

- `退格` / `删除`：删除 1 个字符
- `退格3次` / `删除3个字`：按次数连续退格
- `删除一句`：按最近输出的最后一句长度回删（取不到时使用保守兜底）
- `删除XXXX`：从最近 5 次输出中找到并删除指定词（如"删除今天"会删掉最近输出里的"今天"）

### 3) 光标移动与编辑（v2.5+）

- `上` / `下` / `左` / `右`：方向键
- `左3次` / `右5个`：多次方向键
- `Ctrl左` / `Ctrl右`：按词跳转（Ctrl+方向键）
- `Shift上` / `Shift下`：Shift+方向键（选中文字）
- `Alt左` / `Alt右`：Alt+方向键
- `行首` / `行尾`：Home / End
- `文档开头` / `文档结尾`：Ctrl+Home / Ctrl+End
- `撤销` / `重做`：Ctrl+Z / Ctrl+Y
- `切换窗口`：按住 Alt 并按 Tab，进入窗口切换模式
  - 用 `上`/`下`/`左`/`右` 选择窗口
  - 说 `确定` 切换到所选窗口（松开 Alt）
  - 说 `取消` 放弃切换（按 Escape 并松开 Alt）

### 3) 强制替换（最近输出）

- `把A替换成B` / `把A换成B`
- 搜索最近 5 次输出中包含 A 的记录进行替换
- 这样可以减少在 Cursor/终端等窗口误操作整段文本的风险

### 4) 润色前文（LLM 改写）

- `润色前文，改得更有礼貌一些`
- `润色最近3次输入，改得更正式`
- `润色多次输入，改得更口语`（默认最近 3 次）
- `把前面这一段改得更专业`

工作方式：把最近 N 次输出拼接为原文，再将”修改要求 + 原文”送入 `LLM/润色.py`，最后回删原文并写回改写结果。

### 5) 只读查询（v2.5+）

先用鼠标选中屏幕上的文字，然后说以下命令，结果会在 Toast 弹窗中显示，不会输出到光标位置：

- `问一下 <你的问题>`：基于选中文字提问
- `总结一下`：总结选中文字
- `解释一下`：解释选中文字
- `翻译一下`：翻译选中文字

### 6) 格式化（v2.5+）

- `格式化`：将选中文字或最近输出整理成 Markdown 结构（列表、步骤、表格等）

### 7) 语音点击 UI 元素（v2.5+）

- `点击 XXX` / `单击 XXX`：模糊匹配当前窗口中名为 XXX 的按钮/菜单项并点击
- `双击 XXX`：双击匹配的元素
- `有什么按钮`：列出当前窗口所有可交互的 UI 元素

### 8) 语音快捷操作（v2.5+）

- `搜索 <内容>`：打开浏览器搜索
- `打开 <应用名>`：启动应用程序
- `截图`：触发 Win+Shift+S 截图
- `复制这段`：复制选中文字

### 9) 安全策略

- 检测到终端类窗口（PowerShell/CMD/Windows Terminal）时，会拦截高风险命令（如全选替换、前文润色），避免破坏命令行内容。
- 命令改写依赖“光标仍位于刚输出文本末尾”；若中途手工移动光标，建议先手工定位再执行命令。


## 🛠️ 常见问题

**Q: 为什么按了没反应？**  
A: 请确认 `start_client.exe` 的黑窗口还在运行。若想在管理员权限运行的程序中输入，也需以管理员权限运行客户端。

**Q: 为什么识别结果没字？**  
A: 到 `年/月/assets` 文件夹中检查录音文件，看是不是没有录到音；听听录音效果，是不是麦克风太差，建议使用桌面 USB 麦克风；检查麦克风权限。

**Q: 我可以用显卡加速吗？**  
A: 目前 Fun-ASR-Nano 模型支持显卡加速，且默认开启，Encoder 使用 DirectML 加速，Decoder 使用 Vulkan 加速。但是对于高U低显的集显用户，显卡加速的效果可能还不如CPU，可以到 `config_server.py` 中把 `dml_enable` 或 `vulkan_enable` 设为 False 以禁用显卡加速。Paraformer 和 SenseVoice 本身在 CPU 上就已经超快，用 DirectML 加速反而每次识别会有 200ms 启动开销，因此对它们没有开启显卡加速。

**Q: 低性能电脑转录太慢？**  
A:  
1. 对于短音频，`Fun-ASR-Nano` 在独显上可以 200~300ms 左右转录完毕，`sensevoice` 或 `paraformer` 在 CPU 上可以 100ms 左右转录完毕，这是参考延迟。
2. 如果 `Fun-ASR-Nano` 太慢，尝试到 `config_server.py` 中把 `dml_enable` 或 `vulkan_enable` 设为 False 以禁用显卡加速。
3. 如果性能较差，还是慢，就更改 `config_server.py` 中的 `model_type` ，切换模型为 `sensevoice` 或 `paraformer`。
4. 如果性能太差，连 `sensevoice` 或 `paraformer` 都还是慢，就把 `num_threads` 降低。

**Q: Fun-ASR-Nano 模型几乎不能用？**  
A: Fun-ASR-Nano 的 LLM Decoder 使用 llama.cpp 默认通过 Vulkan 实现显卡加速，部分集显在 FP16 矩阵计算时没有用 FP32 对加和缓存，可能导致数值溢出，影响识别效果，如果遇到了，可以到 config_server.py 中将 `vulkan_enable` 设为 False ，用 CPU 进行解码。

**Q: 需要热词替换？**  
A: 服务端 Fun-ASR-Nano 会参考 `hot-server.txt` 进行语境增强识别；客户端则会根据 `hot.txt` 的相似度匹配或 `hot-rule.txt` 的正则规则，执行强制替换。若启用了润色，LLM 角色可参考 `hot-rectify.txt` 中的纠错历史。

**Q: 如何使用 LLM 角色？**  
A: 只需要在语音的**开头**说出角色名。例如，你配置了一个名为「翻译」的角色，录音时说「翻译，今天天气好」，翻译角色就会接手识别结果，在翻译后输出。它就像是一个随时待命的插件，你喊它名字，它就干活。你可以配置它们直接打字输出，或者在 TOAST 弹窗中显示。`ESC` 可以中断 LLM 的流式输出。

**Q: LLM 角色模型怎么选？**  
A: 你可以在 `LLM` 文件夹里为每个角色配置后端。既可以用 Ollama 部署本地轻量模型（如 gemma3:4b, qwen3:4b 等），也可以填写 DeepSeek 等在线大模型的 API Key。

**Q: LLM 角色可以读取屏幕内容？**  
A: 是的。如果你的 AI 角色开启了 `enable_read_selection`，你可以先用鼠标选中屏幕上的一段文字，然后按住快捷键说：“翻译一下”，LLM 就会识别你的指令，将选中文字进行翻译。但当所选文字与上一次的角色输出完全相同时，则不会提供给角色，以避免浪费 token。

**Q: 为什么我说“发送/换行”偶尔没触发？**  
A: 常见原因是识别结果不是纯命令词（例如识别成整句口语）。建议单独短说命令词；也可以在 `hot-rule.txt` 继续扩展你的口语习惯写法。

**Q: 前文润色/替换为什么有时效果不对？**  
A: 这些命令默认针对“最近输出内容”做回删重写，不是全文编辑器语义。若你手动移动了光标或插入了其他内容，建议先把光标移到目标段末尾再执行命令。

**Q: 想要隐藏黑窗口？**  
A: 点击托盘菜单即可隐藏黑窗口。

**Q: 如何开机启动？**  
A: `Win+R` 输入 `shell:startup` 打开启动文件夹，将服务端、客户端的快捷方式放进去即可。


## 🚀 我的其他优质项目推荐

| 项目名称 | 说明 | 体验地址 |
| :--- | :--- | :--- |
| [**IME_Indicator**](https://github.com/HaujetZhao/IME_Indicator) | Windows 输入法中英状态指示器 | [下载即用](https://github.com/HaujetZhao/IME_Indicator/releases/latest/download/IME-Indicator.exe) |
| [**Rust-Tray**](https://github.com/HaujetZhao/Rust-Tray) | 将控制台最小化到托盘图标的工具 | [下载即用](https://github.com/HaujetZhao/Rust-Tray/releases/latest/download/Tray.exe) |
| [**Gallery-Viewer**](https://github.com/HaujetZhao/Gallery-Viewer-HTML) | 网页端图库查看器，纯 HTML 实现 | [点击即用](https://haujetzhao.github.io/Gallery-Viewer-HTML/) |
| [**全景图片查看器**](https://github.com/HaujetZhao/Panorama-Viewer-HTML) | 单个网页实现全景照片、视频查看 | [点击即用](https://haujetzhao.github.io/Panorama-Viewer-HTML/) |
| [**图标生成器**](https://github.com/HaujetZhao/Font-Awesome-Icon-Generator-HTML) | 使用 Font-Awesome 生成网站 Icon | [点击即用](https://haujetzhao.github.io/Font-Awesome-Icon-Generator-HTML/) |
| [**五笔编码反查**](https://github.com/HaujetZhao/wubi86-revert-query) | 86 五笔编码在线反查 | [点击即用](https://haujetzhao.github.io/wubi86-revert-query/) |
| [**快捷键映射图**](https://github.com/HaujetZhao/ShortcutMapper_Chinese) | 可视化、交互式的快捷键映射图 (中文版) | [点击即用](https://haujetzhao.github.io/ShortcutMapper_Chinese/) |


## ❤️ 致谢

本项目基于以下优秀的开源项目：

-   [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)
-   [FunASR](https://github.com/alibaba-damo-academy/FunASR)

感谢 Google Antigravity、Anthropic Claude、GLM，如果不是这些编程助手，许多功能（例如基于音素的热词检索算法）我是无力实现的。

特别感谢那些慷慨解囊的捐助者，你们的捐助让我用在了购买这些优质的 AI 编程助手服务，并最终将这些成果反馈到了软件的更新里。


如果觉得好用，欢迎点个 Star 或者打赏支持：


![sponsor](assets/sponsor.jpg)	
