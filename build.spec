# -*- mode: python ; coding: utf-8 -*-
"""
CapsWriter-Offline 完整打包配置（服务端 + 客户端）

打包命令：
    pyinstaller build.spec

打包结果：
    dist/CapsWriter-Offline/
    ├── start_server.exe
    ├── start_client.exe
    ├── internal/          (第三方依赖)
    ├── config_*.py        (配置文件)
    ├── core_*.py          (核心入口)
    ├── util/              (工具模块)
    ├── LLM/               (角色定义)
    └── ...
"""

import os
import sys
import glob

# ── 配置选项 ─────────────────────────────────────────────────────────────
INCLUDE_CUDA_PROVIDER = False     # 是否收集 CUDA provider（体积大，需 CUDA 环境）

# ── 路径 ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath('.')
ICON_FILE = os.path.join(PROJECT_ROOT, 'assets', 'icon.ico')

RUNTIME_HOOK = os.path.join(PROJECT_ROOT, 'assets', 'runtime_hook.py')

# ── 排除的模块（减小体积） ────────────────────────────────────────────────
excludes = [
    'IPython', 'PySide6', 'PySide2',
    'matplotlib', 'scipy', 'pandas',
    'wx', 'funasr',
    'torch', 'torchvision', 'torchaudio',
    'tensorflow', 'keras', 'sklearn', 'scikit-learn',
    'pytest', 'unittest', 'doctest',
    'notebook', 'jupyter', 'ipykernel',
    'setuptools', 'distutils', 'pip',
]

# ── 隐藏导入（PyInstaller 无法自动检测的） ─────────────────────────────────
# 服务端
server_hiddenimports = [
    'websockets', 'websockets.legacy', 'websockets.legacy.server',
    'numpy', 'sherpa_onnx',
    'rich', 'rich.console', 'rich.theme', 'rich.markdown',
    'pystray', 'PIL', 'PIL.Image',
    'psutil',
]

# 客户端
client_hiddenimports = [
    'websockets', 'websockets.legacy', 'websockets.legacy.client',
    'keyboard', 'pyclip', 'pyperclip',
    'numpy', 'numba',
    'sounddevice',
    'pypinyin', 'pypinyin.style',
    'watchdog', 'watchdog.observers', 'watchdog.events',
    'typer', 'colorama',
    'srt',
    'openai', 'httpx',
    'rich', 'rich.console', 'rich.theme', 'rich.markdown',
    'pystray', 'PIL', 'PIL.Image',
    'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets',
    'win32gui', 'win32process', 'win32clipboard', 'psutil',
    'pynput', 'pynput.keyboard', 'pynput.mouse',
    'markdown_it',
]

# ── 排除用户代码（不需要排除——由 runtime hook 保证 exe 旁的 .py 优先加载）
# exclude_user_modules 留空，让 PyInstaller 正常追踪依赖
exclude_user_modules = []

# ── CUDA DLL 排除 ─────────────────────────────────────────────────────────
cuda_exclude_dirs = [
    os.path.join('C:', os.sep, 'Program Files', 'NVIDIA GPU Computing Toolkit', 'CUDA'),
    os.path.join('C:', os.sep, 'Program Files', 'NVIDIA', 'CUDNN'),
]

# ── 数据文件收集 ──────────────────────────────────────────────────────────
datas = []

# 如果需要 CUDA provider
if INCLUDE_CUDA_PROVIDER:
    try:
        import onnxruntime
        ort_dir = os.path.dirname(onnxruntime.__file__)
        cuda_dll = os.path.join(ort_dir, 'capi', 'onnxruntime_providers_cuda.dll')
        if os.path.exists(cuda_dll):
            datas.append((cuda_dll, 'onnxruntime/capi'))
    except ImportError:
        pass


# ══════════════════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════════════════

# --- 服务端 ---
server_a = Analysis(
    ['core_server.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=server_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[RUNTIME_HOOK],
    excludes=excludes + exclude_user_modules,
    noarchive=False,
)

# --- 客户端 ---
client_a = Analysis(
    ['core_client.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=client_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[RUNTIME_HOOK],
    excludes=excludes + exclude_user_modules,
    noarchive=False,
)

# ── 合并依赖 ──────────────────────────────────────────────────────────────
MERGE(
    (server_a, 'start_server', 'start_server'),
    (client_a, 'start_client', 'start_client'),
)

# ── 过滤 CUDA 系统 DLL ───────────────────────────────────────────────────
def filter_cuda_system_dlls(binaries):
    """排除从系统 CUDA 目录收集的 DLL"""
    filtered = []
    for name, path, typecode in binaries:
        skip = False
        if path:
            path_lower = path.lower()
            for d in cuda_exclude_dirs:
                if path_lower.startswith(d.lower()):
                    skip = True
                    break
        if not skip:
            filtered.append((name, path, typecode))
    return filtered

if not INCLUDE_CUDA_PROVIDER:
    server_a.binaries = filter_cuda_system_dlls(server_a.binaries)
    client_a.binaries = filter_cuda_system_dlls(client_a.binaries)

# ══════════════════════════════════════════════════════════════════════════
# PYZ + EXE
# ══════════════════════════════════════════════════════════════════════════

server_pyz = PYZ(server_a.pure)
client_pyz = PYZ(client_a.pure)

server_exe = EXE(
    server_pyz,
    server_a.scripts,
    [],
    exclude_binaries=True,
    name='start_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
    contents_directory='internal',
)

client_exe = EXE(
    client_pyz,
    client_a.scripts,
    [],
    exclude_binaries=True,
    name='start_client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
    contents_directory='internal',
)

# ══════════════════════════════════════════════════════════════════════════
# COLLECT → dist/CapsWriter-Offline/
# ══════════════════════════════════════════════════════════════════════════

coll = COLLECT(
    server_exe, server_a.binaries, server_a.datas,
    client_exe, client_a.binaries, client_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CapsWriter-Offline',
)

# ══════════════════════════════════════════════════════════════════════════
# 打包后处理：复制用户代码文件到输出目录
# ══════════════════════════════════════════════════════════════════════════

import shutil

dist_dir = os.path.join('dist', 'CapsWriter-Offline')

# 需要复制的用户代码和配置
copy_items = {
    # 文件
    'config_client.py': 'config_client.py',
    'config_server.py': 'config_server.py',
    'core_client.py': 'core_client.py',
    'core_server.py': 'core_server.py',
    'hot.txt': 'hot.txt',
    'hot-rule.txt': 'hot-rule.txt',
    'hot-rectify.txt': 'hot-rectify.txt',
    'hot-server.txt': 'hot-server.txt',
}

# 需要复制的目录
copy_dirs = ['util', 'LLM', 'assets']

# 需要创建目录连接符的目录
link_dirs = ['models']

if os.path.isdir(dist_dir):
    # 复制文件
    for src, dst in copy_items.items():
        src_path = os.path.join(PROJECT_ROOT, src)
        dst_path = os.path.join(dist_dir, dst)
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            print(f'  复制: {src} -> {dst}')

    # 复制目录
    for d in copy_dirs:
        src_path = os.path.join(PROJECT_ROOT, d)
        dst_path = os.path.join(dist_dir, d)
        if os.path.isdir(src_path):
            if os.path.exists(dst_path):
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            print(f'  复制目录: {d}/')

    # 创建目录连接符
    for d in link_dirs:
        src_path = os.path.join(PROJECT_ROOT, d)
        dst_path = os.path.join(dist_dir, d)
        if os.path.isdir(src_path) and not os.path.exists(dst_path):
            try:
                os.symlink(src_path, dst_path, target_is_directory=True)
                print(f'  链接: {d}/ -> {src_path}')
            except OSError:
                print(f'  [WARN] 创建链接失败（需管理员权限），请手动复制: {d}/')

    print(f'\n[OK] 打包完成: {os.path.abspath(dist_dir)}')
