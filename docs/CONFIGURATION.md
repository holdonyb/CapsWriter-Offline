# CapsWriter Fork Configuration

这份文档面向「自己维护一个可运行的 CapsWriter fork」的场景。

## 1. 仓库定位

- `origin`: 你自己的 fork
- `upstream`: 原始仓库 `HaujetZhao/CapsWriter-Offline`

建议保留这两个 remote：

```bash
git remote -v
git remote add upstream https://github.com/HaujetZhao/CapsWriter-Offline.git
git remote set-url origin https://github.com/holdonyb/CapsWriter-Offline.git
```

日常同步上游时，只需要：

```bash
git fetch upstream
git switch master
git merge upstream/master
git push origin master
```

你的自用改动建议继续放在单独分支里。

## 2. 哪些文件不再进 Git

为了让 GitHub 仓库更干净、避免大文件警告，下面这些内容改为「本地依赖」：

- `models/`
- `internal/`
- `config_override.json`
- `llm_override.json`
- `util/fun_asr_gguf/bin/*.dll`
- `util/fun_asr_gguf/fun_asr_gguf.zip`

这些文件仍然可以保留在你本机目录中使用，只是不再提交到仓库历史。

## 3. 新机器怎么补齐运行环境

如果你是从这个 fork 的源码直接运行，而不是下载 release，需要手动补齐以下内容：

### 模型文件

从上游 release 的模型页面下载并解压到 `models/`：

- `https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models`

目录结构以 [config_server.py](../config_server.py) 里的 `ModelPaths` 为准。

### Fun-ASR 本地二进制

把你当前可运行版本里的整个 `util/fun_asr_gguf/bin/` 目录复制过来，至少要包含：

- `ggml-vulkan.dll`
- `llama.dll`
- 其余 `ggml-*.dll`
- `mtmd.dll`
- `libomp140.x86_64.dll`

如果缺少这些 DLL，Fun-ASR-Nano-GGUF 路径会启动失败。

## 4. 配置文件怎么分层

推荐保持下面这种分层，后续升级上游时冲突最少：

- 默认配置写在源码里：
  - [config_client.py](../config_client.py)
  - [config_server.py](../config_server.py)
  - [LLM/default.py](../LLM/default.py)
  - `LLM/*.py`
- 本地机器差异写在 override 文件里：
  - `config_override.json`
  - `llm_override.json`

其中：

- `config_override.json` 覆盖 `ClientConfig`
- `llm_override.json` 覆盖各个 LLM 角色的 provider/model/api_key/api_url 等字段

相关读写逻辑在 [util/client/ui/config_editor.py](../util/client/ui/config_editor.py)。

## 5. 火山方舟 / Volcengine 正确写法

如果角色使用火山方舟：

- `provider`: `volcengine`
- `model`: 填具体模型名，例如 `doubao-1-5-pro-32k-250115`
- `api_url`: 必须填完整地址 `https://ark.cn-beijing.volces.com/api/v3`
- `api_key`: 填你的 Ark Key

不要把模型名填到 `api_url` 里。`api_url` 不是模型名字段。

正确示例：

```json
{
  "default": {
    "provider": "volcengine",
    "model": "doubao-1-5-pro-32k-250115",
    "api_url": "https://ark.cn-beijing.volces.com/api/v3",
    "api_key": "你的密钥"
  }
}
```

## 6. 推荐的自用维护方式

如果你只是给自己用，建议：

1. `master` 保持接近上游，方便同步。
2. 自用改动放到单独分支。
3. 本地配置只放 override 文件，不直接把密钥写进源码。
4. 大文件继续留在本机目录，不再提交到 GitHub。

这样以后你要继续同步上游，成本会低很多。
