# CapsWriter 快速上手

这份文档面向第一次拿到这个 fork 的人，目标是 5 分钟内跑起来。

## 1. 最省事的用法

优先建议直接使用 release 版本，而不是源码运行。

步骤：

1. 下载程序本体。
2. 下载模型压缩包。
3. 解压到同一个目录结构下。
4. 先运行 `start_server.exe`，再运行 `start_client.exe`。

上游发布页：

- 软件本体：`https://github.com/HaujetZhao/CapsWriter-Offline/releases/latest`
- 模型页面：`https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models`

## 2. 运行前准备

需要先安装：

- Windows 10/11 64 位
- VC++ 运行库

VC++ 运行库：

- `https://learn.microsoft.com/zh-cn/cpp/windows/latest-supported-vc-redist`

## 3. 从源码运行时还要补什么

如果你不是下载 release，而是直接 clone 这个仓库源码，需要额外补齐本地依赖。

### 模型目录

按 [config_server.py](../config_server.py) 里的 `ModelPaths` 准备 `models/` 目录。

### Fun-ASR 运行 DLL

把可运行版本中的整个 `util/fun_asr_gguf/bin/` 目录复制到源码目录。

这个目录里的 DLL 现在不再提交到 Git，所以 clone 下来默认不会有。

### 本地配置文件

推荐只改这两个本地文件，不直接改源码默认值：

- `config_override.json`
- `llm_override.json`

详细说明见 [CONFIGURATION.md](./CONFIGURATION.md)。

## 4. 最常见的启动顺序

1. 启动 `start_server.exe`
2. 等模型加载完成
3. 启动 `start_client.exe`
4. 按住 `CapsLock` 或鼠标侧键开始说话

## 5. 火山方舟配置示例

如果你要用火山方舟的大模型，`llm_override.json` 里要这样写：

```json
{
  "default": {
    "provider": "volcengine",
    "model": "doubao-1-5-pro-32k-250115",
    "api_url": "https://ark.cn-beijing.volces.com/api/v3",
    "api_key": "你的 Ark API Key"
  }
}
```

关键点只有一个：

- `api_url` 必须是完整 URL
- 模型名放在 `model`

不要把模型名填到 `api_url`。

## 6. 常见问题

### 能识别，但 LLM 报 API 或网络错误

优先检查：

1. `provider` 是否写成了 `volcengine`
2. `api_url` 是否为 `https://ark.cn-beijing.volces.com/api/v3`
3. `model` 是否填了真实可用的模型名
4. `api_key` 是否有效

### 设置保存了但没生效

优先看根目录里的：

- `config_override.json`
- `llm_override.json`

界面保存后的结果最终会落到这两个文件里。

### clone 下来就跑不起来

通常不是代码问题，而是缺：

1. `models/`
2. `util/fun_asr_gguf/bin/*.dll`
3. VC++ 运行库

## 7. 给自己维护 fork 的建议

如果你只是自己用，建议：

1. `master` 放稳定可运行版本
2. 新功能再开单独分支
3. 本地依赖不提交 Git
4. API Key 只放 override 文件
