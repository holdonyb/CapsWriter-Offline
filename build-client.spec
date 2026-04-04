# -*- mode: python ; coding: utf-8 -*-
"""
CapsWriter-Offline 仅客户端打包配置

打包命令：
    pyinstaller build-client.spec

适用场景：
    - 仅需客户端（服务端在其他机器运行）
    - Win7 兼容打包（使用 Python 3.8 环境）
"""

import os
import shutil

# ── 配置选项 ─────────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath('.')
ICON_FILE = os.path.join(PROJECT_ROOT, 'assets', 'icon.ico')
RUNTIME_HOOK = os.path.join(PROJECT_ROOT, 'assets', 'runtime_hook.py')

# ── 排除的模块 ────────────────────────────────────────────────────────────
excludes = [
    'IPython', 'PySide6', 'PySide2',
    'matplotlib', 'scipy', 'pandas',
    'wx', 'funasr',
    'torch', 'torchvision', 'torchaudio',
    'tensorflow', 'keras', 'sklearn', 'scikit-learn',
    'pytest', 'unittest', 'doctest',
    'notebook', 'jupyter', 'ipykernel',
    'setuptools', 'distutils', 'pip',
    # 服务端专用
    'sherpa_onnx',
]

# ── 排除用户代码（不需要排除——由 runtime hook 保证 exe 旁的 .py 优先加载）
exclude_user_modules = []

# ── 隐藏导入 ──────────────────────────────────────────────────────────────
hiddenimports = [
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

# ══════════════════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════════════════

a = Analysis(
    ['core_client.py'],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[RUNTIME_HOOK],
    excludes=excludes + exclude_user_modules,
    noarchive=False,
)

# ══════════════════════════════════════════════════════════════════════════
# PYZ + EXE + COLLECT
# ══════════════════════════════════════════════════════════════════════════

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='start_client',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=ICON_FILE if os.path.exists(ICON_FILE) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CapsWriter-Client',
    contents_directory='internal',
)

# ══════════════════════════════════════════════════════════════════════════
# 打包后处理：复制用户代码
# ══════════════════════════════════════════════════════════════════════════

dist_dir = os.path.join('dist', 'CapsWriter-Client')

copy_items = {
    'config_client.py': 'config_client.py',
    'core_client.py': 'core_client.py',
    'hot.txt': 'hot.txt',
    'hot-rule.txt': 'hot-rule.txt',
    'hot-rectify.txt': 'hot-rectify.txt',
}

copy_dirs = ['util', 'LLM', 'assets']

if os.path.isdir(dist_dir):
    for src, dst in copy_items.items():
        src_path = os.path.join(PROJECT_ROOT, src)
        dst_path = os.path.join(dist_dir, dst)
        if os.path.exists(src_path):
            shutil.copy2(src_path, dst_path)
            print(f'  复制: {src} -> {dst}')

    for d in copy_dirs:
        src_path = os.path.join(PROJECT_ROOT, d)
        dst_path = os.path.join(dist_dir, d)
        if os.path.isdir(src_path):
            if os.path.exists(dst_path):
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            print(f'  复制目录: {d}/')

    print(f'\n[OK] 客户端打包完成: {os.path.abspath(dist_dir)}')
