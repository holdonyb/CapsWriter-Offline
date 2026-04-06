# coding: utf-8
"""
设置面板 - Tkinter GUI

提供可视化界面来修改 CapsWriter 配置，包括：
- Tab 1: 快捷键配置
- Tab 2: 语音处理
- Tab 3: LLM / AI 角色
- Tab 4: 界面 & 输出
- Tab 5: 高级设置
"""

import os
import json
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from config_client import ClientConfig as Config, BASE_DIR
from util.client.ui.config_editor import (
    load_overrides, save_overrides,
    load_role_overrides, save_role_overrides,
)
from util.llm.llm_constants import APIConfig

# 单例窗口引用
_settings_window = None
_settings_lock = threading.Lock()

# 可用的快捷键选项
AVAILABLE_KEYS = [
    'caps_lock', 'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8',
    'f9', 'f10', 'f11', 'f12', 'f13', 'f14', 'f15', 'f16', 'f17',
    'f18', 'f19', 'f20', 'f21', 'f22', 'f23', 'f24',
    'x1', 'x2',
    'ctrl', 'ctrl_r', 'shift', 'shift_r', 'alt', 'alt_r',
    'space', 'tab', 'num_lock', 'scroll_lock', 'pause', 'insert',
    'up', 'down',
    'left', 'right',
]

PROVIDERS = ['ollama', 'openai', 'deepseek', 'moonshot', 'zhipu', 'volcengine', 'claude', 'gemini']
LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']


def _is_http_url(value: str) -> bool:
    """判断是否为完整的 HTTP(S) URL。"""
    value = (value or '').strip().lower()
    return value.startswith('http://') or value.startswith('https://')


def _normalize_role_api_url(provider: str, api_url: str) -> tuple[str, str | None]:
    """规范化角色 API URL，并返回校验错误。"""
    provider = (provider or '').strip()
    api_url = (api_url or '').strip()
    default_url = APIConfig.DEFAULT_API_URLS.get(provider, '')

    # 火山 Ark 默认补全为官方地址，避免用户误以为空值未保存。
    if provider == 'volcengine' and not api_url:
        return default_url, None

    if api_url and not _is_http_url(api_url):
        return '', f'{provider} 的 API URL 必须是完整地址，不能填模型名或其他文本：{api_url}'

    return api_url, None


def open_settings():
    """打开设置面板（线程安全，非阻塞）"""
    global _settings_window
    with _settings_lock:
        if _settings_window is not None:
            try:
                _settings_window.lift()
                _settings_window.focus_force()
                return
            except tk.TclError:
                _settings_window = None

    thread = threading.Thread(target=_create_settings_window, daemon=True)
    thread.start()


def _create_settings_window():
    """在独立线程中创建 Tkinter 设置窗口"""
    global _settings_window

    root = tk.Tk()
    root.title('CapsWriter 设置')
    root.geometry('720x560')
    root.resizable(True, True)

    # 设置图标
    icon_path = os.path.join(BASE_DIR, 'assets', 'icon.ico')
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)
        except Exception:
            pass

    _settings_window = root

    # 加载当前 override
    overrides = load_overrides()
    role_overrides = load_role_overrides()

    # Notebook (Tab 容器)
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True, padx=8, pady=(8, 0))

    # ====== 收集所有控件值的字典 ======
    widgets = {}

    # ====== Tab 1: 快捷键 ======
    tab_shortcut = ttk.Frame(notebook)
    notebook.add(tab_shortcut, text=' 快捷键 ')
    _build_shortcut_tab(tab_shortcut, overrides, widgets)

    # ====== Tab 2: 语音处理 ======
    tab_voice = ttk.Frame(notebook)
    notebook.add(tab_voice, text=' 语音处理 ')
    _build_voice_tab(tab_voice, overrides, widgets)

    # ====== Tab 3: LLM / AI ======
    tab_llm = ttk.Frame(notebook)
    notebook.add(tab_llm, text=' LLM / AI ')
    _build_llm_tab(tab_llm, role_overrides, widgets)

    # ====== Tab 4: 界面 & 输出 ======
    tab_ui = ttk.Frame(notebook)
    notebook.add(tab_ui, text=' 界面 & 输出 ')
    _build_ui_tab(tab_ui, overrides, widgets)

    # ====== Tab 5: 高级 ======
    tab_advanced = ttk.Frame(notebook)
    notebook.add(tab_advanced, text=' 高级 ')
    _build_advanced_tab(tab_advanced, overrides, widgets)

    # ====== 底部按钮 ======
    btn_frame = ttk.Frame(root)
    btn_frame.pack(fill='x', padx=8, pady=8)

    ttk.Button(btn_frame, text='保存并重启', command=lambda: _on_save(root, widgets)).pack(side='right', padx=4)
    ttk.Button(btn_frame, text='保存', command=lambda: _on_save(root, widgets, restart=False)).pack(side='right', padx=4)
    ttk.Button(btn_frame, text='取消', command=root.destroy).pack(side='right', padx=4)

    def on_close():
        global _settings_window
        _settings_window = None
        root.destroy()

    root.protocol('WM_DELETE_WINDOW', on_close)
    root.mainloop()

    # 窗口关闭后清理引用
    with _settings_lock:
        _settings_window = None


# ==============================================================
# Tab builders
# ==============================================================

def _get_val(overrides: dict, key: str):
    """从 override 或 Config 获取当前有效值"""
    if key in overrides:
        return overrides[key]
    return getattr(Config, key, None)


def _build_shortcut_tab(parent, overrides, widgets):
    """构建快捷键 Tab"""
    desc = ttk.Label(parent, text='配置录音快捷键。修改后需要保存并重启客户端才能生效。')
    desc.pack(anchor='w', padx=8, pady=(8, 4))

    # 快捷键列表容器
    list_frame = ttk.LabelFrame(parent, text='快捷键列表')
    list_frame.pack(fill='both', expand=True, padx=8, pady=4)

    # 表头
    header = ttk.Frame(list_frame)
    header.pack(fill='x', padx=4, pady=(4, 0))
    for col, w in [('键名', 12), ('类型', 8), ('长按模式', 8), ('阻塞', 6), ('启用', 6), ('', 6)]:
        ttk.Label(header, text=col, width=w, anchor='center').pack(side='left', padx=2)

    # 滚动区域
    canvas = tk.Canvas(list_frame, height=180)
    scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)
    scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side='left', fill='both', expand=True, padx=4, pady=4)
    scrollbar.pack(side='right', fill='y', pady=4)

    # 获取当前快捷键
    shortcuts = list(_get_val(overrides, 'shortcuts') or [])
    shortcut_rows = []
    widgets['_shortcut_rows'] = shortcut_rows
    widgets['_shortcut_frame'] = scroll_frame

    def add_row(sc=None):
        if sc is None:
            sc = {'key': 'f12', 'type': 'keyboard', 'suppress': True, 'hold_mode': True, 'enabled': True}
        row_frame = ttk.Frame(scroll_frame)
        row_frame.pack(fill='x', padx=2, pady=1)

        key_var = tk.StringVar(value=sc.get('key', 'caps_lock'))
        type_var = tk.StringVar(value=sc.get('type', 'keyboard'))
        hold_var = tk.BooleanVar(value=sc.get('hold_mode', True))
        suppress_var = tk.BooleanVar(value=sc.get('suppress', True))
        enabled_var = tk.BooleanVar(value=sc.get('enabled', True))

        ttk.Combobox(row_frame, textvariable=key_var, values=AVAILABLE_KEYS, width=10, state='readonly').pack(side='left', padx=2)
        ttk.Combobox(row_frame, textvariable=type_var, values=['keyboard', 'mouse'], width=6, state='readonly').pack(side='left', padx=2)
        ttk.Checkbutton(row_frame, variable=hold_var, text='长按').pack(side='left', padx=2)
        ttk.Checkbutton(row_frame, variable=suppress_var, text='阻塞').pack(side='left', padx=2)
        ttk.Checkbutton(row_frame, variable=enabled_var, text='启用').pack(side='left', padx=2)

        row_data = {'frame': row_frame, 'key': key_var, 'type': type_var,
                    'hold_mode': hold_var, 'suppress': suppress_var, 'enabled': enabled_var}

        def remove():
            row_frame.destroy()
            shortcut_rows.remove(row_data)

        ttk.Button(row_frame, text='删除', width=4, command=remove).pack(side='left', padx=2)
        shortcut_rows.append(row_data)

    for sc in shortcuts:
        add_row(sc)

    btn_add = ttk.Button(parent, text='+ 添加快捷键', command=add_row)
    btn_add.pack(anchor='w', padx=8, pady=4)

    # 触发阈值
    thresh_frame = ttk.Frame(parent)
    thresh_frame.pack(fill='x', padx=8, pady=4)
    ttk.Label(thresh_frame, text='触发阈值 (秒):').pack(side='left')
    thresh_var = tk.DoubleVar(value=_get_val(overrides, 'threshold') or 0.3)
    ttk.Spinbox(thresh_frame, from_=0.1, to=1.0, increment=0.05, textvariable=thresh_var, width=6).pack(side='left', padx=4)
    widgets['threshold'] = thresh_var


def _build_voice_tab(parent, overrides, widgets):
    """构建语音处理 Tab"""
    # 复选框区
    checks_frame = ttk.LabelFrame(parent, text='处理选项')
    checks_frame.pack(fill='x', padx=8, pady=8)

    hot_var = tk.BooleanVar(value=_get_val(overrides, 'hot'))
    ttk.Checkbutton(checks_frame, text='热词替换 (hot.txt)', variable=hot_var).pack(anchor='w', padx=8, pady=2)
    widgets['hot'] = hot_var

    hot_rule_var = tk.BooleanVar(value=_get_val(overrides, 'hot_rule'))
    ttk.Checkbutton(checks_frame, text='正则替换 (hot-rule.txt)', variable=hot_rule_var).pack(anchor='w', padx=8, pady=2)
    widgets['hot_rule'] = hot_rule_var

    trash_punc_var = tk.StringVar(value=_get_val(overrides, 'trash_punc') or '')
    punc_frame = ttk.Frame(checks_frame)
    punc_frame.pack(fill='x', padx=8, pady=2)
    ttk.Label(punc_frame, text='去末尾标点:').pack(side='left')
    ttk.Entry(punc_frame, textvariable=trash_punc_var, width=12).pack(side='left', padx=4)
    widgets['trash_punc'] = trash_punc_var

    trad_var = tk.BooleanVar(value=_get_val(overrides, 'traditional_convert'))
    ttk.Checkbutton(checks_frame, text='繁简转换', variable=trad_var).pack(anchor='w', padx=8, pady=2)
    widgets['traditional_convert'] = trad_var

    trad_locale_var = tk.StringVar(value=_get_val(overrides, 'traditional_locale') or 'zh-hant')
    locale_frame = ttk.Frame(checks_frame)
    locale_frame.pack(fill='x', padx=24, pady=2)
    ttk.Label(locale_frame, text='繁体地区:').pack(side='left')
    ttk.Combobox(locale_frame, textvariable=trad_locale_var,
                 values=['zh-hant', 'zh-tw', 'zh-hk'], width=10, state='readonly').pack(side='left', padx=4)
    widgets['traditional_locale'] = trad_locale_var

    # 热词阈值
    thresh_frame = ttk.LabelFrame(parent, text='热词阈值')
    thresh_frame.pack(fill='x', padx=8, pady=4)

    for label, key, lo, hi in [
        ('替换阈值:', 'hot_thresh', 0.5, 1.0),
        ('相似阈值:', 'hot_similar', 0.3, 1.0),
        ('纠错阈值:', 'hot_rectify', 0.3, 1.0),
    ]:
        row = ttk.Frame(thresh_frame)
        row.pack(fill='x', padx=8, pady=2)
        ttk.Label(row, text=label, width=10).pack(side='left')
        var = tk.DoubleVar(value=_get_val(overrides, key) or 0.6)
        scale = ttk.Scale(row, from_=lo, to=hi, variable=var, orient='horizontal', length=200)
        scale.pack(side='left', padx=4)
        val_label = ttk.Label(row, text=f'{var.get():.2f}', width=5)
        val_label.pack(side='left')
        # 更新标签
        def _updater(v, lbl=val_label):
            lbl.config(text=f'{float(v):.2f}')
        scale.config(command=_updater)
        widgets[key] = var

    # 打开文件按钮
    file_frame = ttk.Frame(parent)
    file_frame.pack(fill='x', padx=8, pady=8)
    for fname in ['hot.txt', 'hot-rule.txt', 'hot-rectify.txt']:
        fpath = os.path.join(BASE_DIR, fname)
        ttk.Button(file_frame, text=f'打开 {fname}',
                   command=lambda p=fpath: os.startfile(p) if os.path.exists(p) else None).pack(side='left', padx=4)


def _build_llm_tab(parent, role_overrides, widgets):
    """构建 LLM / AI Tab"""
    # 滚动容器
    canvas = tk.Canvas(parent)
    scrollbar = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
    scroll_frame = ttk.Frame(canvas)
    scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.create_window((0, 0), window=scroll_frame, anchor='nw')
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)

    # 鼠标滚轮
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')
    canvas.bind_all('<MouseWheel>', _on_mousewheel)

    # 加载角色文件
    llm_dir = Path(BASE_DIR) / 'LLM'
    role_files = sorted(llm_dir.glob('*.py'))
    role_files = [f for f in role_files if f.name != '__init__.py']

    role_widgets = {}
    widgets['_roles'] = role_widgets

    intro = ttk.Label(
        scroll_frame,
        text='说明：普通听写默认不走 LLM，直接输出识别结果；只有在语音开头说出“大助理/翻译/格式化/润色”等角色前缀时，才会切换到对应角色。API URL 必须填写完整的 http(s) 地址，不能填模型名。',
        wraplength=640,
        justify='left',
    )
    intro.pack(fill='x', padx=8, pady=(8, 4))

    for role_file in role_files:
        stem = role_file.stem
        # 读取当前模块值
        module_vals = _read_role_module(role_file)
        overrides_for_role = role_overrides.get(stem, {})

        # 合并: override 优先
        merged = {**module_vals, **overrides_for_role}

        display_name = merged.get('name', '') or stem
        if display_name == '':
            display_name = '默认'

        frame = ttk.LabelFrame(scroll_frame, text=f'  {display_name}  ({role_file.name})')
        frame.pack(fill='x', padx=8, pady=4)

        rw = {}
        role_widgets[stem] = rw

        # Row 1: Provider / Model
        r1 = ttk.Frame(frame)
        r1.pack(fill='x', padx=8, pady=2)
        ttk.Label(r1, text='Provider:').pack(side='left')
        prov_var = tk.StringVar(value=merged.get('provider', 'ollama'))
        ttk.Combobox(r1, textvariable=prov_var, values=PROVIDERS, width=10, state='readonly').pack(side='left', padx=4)
        rw['provider'] = prov_var

        ttk.Label(r1, text='Model:').pack(side='left', padx=(12, 0))
        model_var = tk.StringVar(value=merged.get('model', ''))
        ttk.Entry(r1, textvariable=model_var, width=20).pack(side='left', padx=4)
        rw['model'] = model_var

        proc_var = tk.BooleanVar(value=merged.get('process', False))
        ttk.Checkbutton(r1, text='启用LLM', variable=proc_var).pack(side='left', padx=(12, 0))
        rw['process'] = proc_var

        # Row 2: API URL / Key
        r2 = ttk.Frame(frame)
        r2.pack(fill='x', padx=8, pady=2)
        ttk.Label(r2, text='API URL:').pack(side='left')
        url_var = tk.StringVar(value=merged.get('api_url', ''))
        ttk.Entry(r2, textvariable=url_var, width=30).pack(side='left', padx=4)
        rw['api_url'] = url_var

        ttk.Label(r2, text='API Key:').pack(side='left', padx=(12, 0))
        key_var = tk.StringVar(value=merged.get('api_key', ''))
        ttk.Entry(r2, textvariable=key_var, width=20, show='*').pack(side='left', padx=4)
        rw['api_key'] = key_var

        # Row 3: Temperature / Max tokens
        r3 = ttk.Frame(frame)
        r3.pack(fill='x', padx=8, pady=(2, 4))
        ttk.Label(r3, text='Temperature:').pack(side='left')
        temp_var = tk.DoubleVar(value=merged.get('temperature', 0.7))
        ttk.Spinbox(r3, from_=0.0, to=2.0, increment=0.1, textvariable=temp_var, width=5).pack(side='left', padx=4)
        rw['temperature'] = temp_var

        ttk.Label(r3, text='Max tokens:').pack(side='left', padx=(12, 0))
        mt_var = tk.IntVar(value=merged.get('max_tokens', 4096))
        ttk.Spinbox(r3, from_=0, to=65536, increment=256, textvariable=mt_var, width=8).pack(side='left', padx=4)
        rw['max_tokens'] = mt_var

    # 应用感知语调
    tone_frame = ttk.Frame(scroll_frame)
    tone_frame.pack(fill='x', padx=8, pady=8)
    tone_var = tk.BooleanVar(value=getattr(Config, 'app_aware_tone', True))
    ttk.Checkbutton(tone_frame, text='应用感知语调 (根据当前窗口调整 LLM 输出风格)', variable=tone_var).pack(anchor='w')
    widgets['app_aware_tone'] = tone_var


def _build_ui_tab(parent, overrides, widgets):
    """构建界面 & 输出 Tab"""
    frame = ttk.LabelFrame(parent, text='界面')
    frame.pack(fill='x', padx=8, pady=8)

    tray_var = tk.BooleanVar(value=_get_val(overrides, 'enable_tray'))
    ttk.Checkbutton(frame, text='启用托盘图标', variable=tray_var).pack(anchor='w', padx=8, pady=2)
    widgets['enable_tray'] = tray_var

    # 开机自启动（读取注册表实际状态）
    from util.tools.auto_start import is_auto_start_enabled
    auto_start_var = tk.BooleanVar(value=is_auto_start_enabled())
    ttk.Checkbutton(frame, text='开机自动启动', variable=auto_start_var).pack(anchor='w', padx=8, pady=2)
    widgets['auto_start'] = auto_start_var

    # 输出模式
    out_frame = ttk.LabelFrame(parent, text='输出')
    out_frame.pack(fill='x', padx=8, pady=4)

    paste_var = tk.BooleanVar(value=_get_val(overrides, 'paste'))
    ttk.Checkbutton(out_frame, text='粘贴模式 (默认为打字模式)', variable=paste_var).pack(anchor='w', padx=8, pady=2)
    widgets['paste'] = paste_var

    restore_var = tk.BooleanVar(value=_get_val(overrides, 'restore_clip'))
    ttk.Checkbutton(out_frame, text='粘贴后恢复剪贴板', variable=restore_var).pack(anchor='w', padx=8, pady=2)
    widgets['restore_clip'] = restore_var

    # LLM 中断键
    stop_frame = ttk.Frame(out_frame)
    stop_frame.pack(fill='x', padx=8, pady=2)
    ttk.Label(stop_frame, text='LLM 中断键:').pack(side='left')
    stop_var = tk.StringVar(value=_get_val(overrides, 'llm_stop_key') or 'esc')
    ttk.Entry(stop_frame, textvariable=stop_var, width=10).pack(side='left', padx=4)
    widgets['llm_stop_key'] = stop_var

    llm_var = tk.BooleanVar(value=_get_val(overrides, 'llm_enabled'))
    ttk.Checkbutton(out_frame, text='启用角色 LLM 功能（仅在说出角色前缀时触发）', variable=llm_var).pack(anchor='w', padx=8, pady=2)
    widgets['llm_enabled'] = llm_var


def _build_advanced_tab(parent, overrides, widgets):
    """构建高级 Tab"""
    # 服务端
    srv_frame = ttk.LabelFrame(parent, text='服务端')
    srv_frame.pack(fill='x', padx=8, pady=8)

    r1 = ttk.Frame(srv_frame)
    r1.pack(fill='x', padx=8, pady=2)
    ttk.Label(r1, text='地址:').pack(side='left')
    addr_var = tk.StringVar(value=_get_val(overrides, 'addr') or '127.0.0.1')
    ttk.Entry(r1, textvariable=addr_var, width=16).pack(side='left', padx=4)
    widgets['addr'] = addr_var

    ttk.Label(r1, text='端口:').pack(side='left', padx=(12, 0))
    port_var = tk.StringVar(value=_get_val(overrides, 'port') or '6016')
    ttk.Entry(r1, textvariable=port_var, width=8).pack(side='left', padx=4)
    widgets['port'] = port_var

    # 日志
    log_frame = ttk.Frame(srv_frame)
    log_frame.pack(fill='x', padx=8, pady=2)
    ttk.Label(log_frame, text='日志级别:').pack(side='left')
    log_var = tk.StringVar(value=_get_val(overrides, 'log_level') or 'INFO')
    ttk.Combobox(log_frame, textvariable=log_var, values=LOG_LEVELS, width=10, state='readonly').pack(side='left', padx=4)
    widgets['log_level'] = log_var

    # 录音
    rec_frame = ttk.LabelFrame(parent, text='录音')
    rec_frame.pack(fill='x', padx=8, pady=4)

    save_var = tk.BooleanVar(value=_get_val(overrides, 'save_audio'))
    ttk.Checkbutton(rec_frame, text='保存录音文件', variable=save_var).pack(anchor='w', padx=8, pady=2)
    widgets['save_audio'] = save_var

    # UDP
    udp_frame = ttk.LabelFrame(parent, text='UDP')
    udp_frame.pack(fill='x', padx=8, pady=4)

    udp_var = tk.BooleanVar(value=_get_val(overrides, 'udp_broadcast'))
    ttk.Checkbutton(udp_frame, text='启用 UDP 广播', variable=udp_var).pack(anchor='w', padx=8, pady=2)
    widgets['udp_broadcast'] = udp_var

    udp_ctrl_var = tk.BooleanVar(value=_get_val(overrides, 'udp_control'))
    ttk.Checkbutton(udp_frame, text='启用 UDP 控制 (外部程序控制录音)', variable=udp_ctrl_var).pack(anchor='w', padx=8, pady=2)
    widgets['udp_control'] = udp_ctrl_var


# ==============================================================
# Helpers
# ==============================================================

def _read_role_module(file_path: Path) -> dict:
    """读取角色模块的变量值（不执行 import，直接解析文件）"""
    vals = {}
    try:
        text = file_path.read_text(encoding='utf-8')
        # 简单提取 module-level 赋值（不含多行字符串）
        import ast
        tree = ast.parse(text)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    try:
                        vals[target.id] = ast.literal_eval(node.value)
                    except (ValueError, TypeError):
                        pass
    except Exception:
        pass
    return vals


def _on_save(root, widgets, restart=True):
    """保存设置"""
    # 1. 收集 ClientConfig override
    config_override = {}

    # 快捷键
    shortcut_rows = widgets.get('_shortcut_rows', [])
    if shortcut_rows is not None:
        shortcuts = []
        for row in shortcut_rows:
            shortcuts.append({
                'key': row['key'].get(),
                'type': row['type'].get(),
                'hold_mode': row['hold_mode'].get(),
                'suppress': row['suppress'].get(),
                'enabled': row['enabled'].get(),
            })
        config_override['shortcuts'] = shortcuts

    # 简单字段
    simple_fields = {
        'threshold': 'float',
        'hot': 'bool', 'hot_rule': 'bool',
        'trash_punc': 'str',
        'traditional_convert': 'bool', 'traditional_locale': 'str',
        'hot_thresh': 'float', 'hot_similar': 'float', 'hot_rectify': 'float',
        'app_aware_tone': 'bool',
        'enable_tray': 'bool',
        'paste': 'bool', 'restore_clip': 'bool',
        'llm_stop_key': 'str', 'llm_enabled': 'bool',
        'addr': 'str', 'port': 'str',
        'log_level': 'str',
        'save_audio': 'bool',
        'udp_broadcast': 'bool', 'udp_control': 'bool',
    }
    for key, typ in simple_fields.items():
        if key not in widgets:
            continue
        var = widgets[key]
        try:
            if typ == 'bool':
                config_override[key] = var.get()
            elif typ == 'float':
                config_override[key] = round(float(var.get()), 3)
            elif typ == 'int':
                config_override[key] = int(var.get())
            else:
                config_override[key] = var.get()
        except (tk.TclError, ValueError):
            pass

    # 2. 收集 LLM role override
    role_widgets = widgets.get('_roles', {})
    role_override_data = {}
    role_fields = ['provider', 'model', 'process', 'api_url', 'api_key', 'temperature', 'max_tokens']

    for stem, rw in role_widgets.items():
        role_ov = {}
        for field in role_fields:
            if field not in rw:
                continue
            var = rw[field]
            try:
                val = var.get()
                if isinstance(var, tk.BooleanVar):
                    role_ov[field] = val
                elif isinstance(var, tk.DoubleVar):
                    role_ov[field] = round(float(val), 2)
                elif isinstance(var, tk.IntVar):
                    role_ov[field] = int(val)
                else:
                    role_ov[field] = val
            except (tk.TclError, ValueError):
                pass

        provider = role_ov.get('provider', '').strip()
        api_url = role_ov.get('api_url', '')
        normalized_url, error = _normalize_role_api_url(provider, api_url)
        if error:
            role_label = '默认' if stem == 'default' else stem
            messagebox.showerror('保存失败', f'角色“{role_label}”配置有误：\n{error}')
            return
        role_ov['api_url'] = normalized_url

        if role_ov:
            role_override_data[stem] = role_ov

    save_overrides(config_override)
    save_role_overrides(role_override_data)

    # 3. 开机自启动（直接写注册表，不存 override JSON）
    if 'auto_start' in widgets:
        from util.tools.auto_start import set_auto_start
        set_auto_start(widgets['auto_start'].get())

    if restart:
        root.destroy()
        try:
            from core_client import request_restart
            request_restart()
        except Exception:
            messagebox.showinfo('保存成功', '配置已保存。请手动重启客户端使设置生效。')
    else:
        messagebox.showinfo('保存成功', '配置已保存。部分设置需要重启客户端才能生效。')
