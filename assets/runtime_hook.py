# Runtime hook: 将 exe 所在目录加入 sys.path 最前面
# 这样用户代码（config_client.py, util/, LLM/ 等）可以从 exe 旁边的源文件加载
import os
import sys

# PyInstaller 打包后 sys.executable 指向 exe 文件
exe_dir = os.path.dirname(os.path.abspath(sys.executable))
if exe_dir not in sys.path:
    sys.path.insert(0, exe_dir)
