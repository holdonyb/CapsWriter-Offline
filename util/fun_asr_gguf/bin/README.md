# Local Runtime Binaries

这个目录下的 `*.dll` 属于本地运行依赖，不再提交到 Git。

如果你是从源码运行而不是使用 release，请从你本机已有的可运行版本里复制 `util/fun_asr_gguf/bin/` 到这里。

常见必需文件包括：

- `ggml-vulkan.dll`
- `llama.dll`
- `mtmd.dll`
- `libomp140.x86_64.dll`
- 其余 `ggml-*.dll`
