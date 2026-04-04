# coding: utf-8
"""
Windows UI 自动化工具

使用 uiautomation 库（Windows UI Automation API）实现语音点击 UI 元素，
这是 CapsWriter 独有的超越 TypeLess 的高级功能。

依赖：pip install uiautomation
"""

from __future__ import annotations

import difflib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_clickable_elements() -> list[dict]:
    """
    扫描当前焦点窗口所有可交互元素。

    Returns:
        元素信息列表，每项包含 name, type, ctrl
    """
    try:
        import uiautomation as auto

        window = auto.GetFocusedControl()
        if window is None:
            return []
        window = window.GetTopLevelControl()
        if window is None:
            return []

        result = []
        CLICKABLE_TYPES = {
            'ButtonControl', 'MenuItemControl', 'TabItemControl',
            'CheckBoxControl', 'RadioButtonControl', 'ListItemControl',
            'HyperlinkControl', 'MenuBarControl', 'MenuItem',
        }

        def _scan(ctrl, depth=0):
            if depth > 6:
                return
            try:
                name = ctrl.Name
                ctrl_type = ctrl.ControlTypeName
                if name and ctrl_type in CLICKABLE_TYPES:
                    result.append({
                        'name': name,
                        'type': ctrl_type,
                        'ctrl': ctrl,
                    })
                for child in ctrl.GetChildren():
                    _scan(child, depth + 1)
            except Exception:
                pass

        _scan(window)
        return result

    except ImportError:
        logger.debug("uiautomation 未安装，语音点击功能不可用")
        return []
    except Exception as e:
        logger.debug(f"get_clickable_elements 失败: {e}")
        return []


def voice_click(label: str, double: bool = False) -> tuple[bool, str]:
    """
    语音点击：找到名称最接近 label 的可点击元素并点击。

    Args:
        label: 目标元素名称（来自语音识别）
        double: 是否双击

    Returns:
        (success, matched_name)
    """
    elements = get_clickable_elements()
    if not elements:
        return False, ''

    names = [e['name'] for e in elements]
    matches = difflib.get_close_matches(label, names, n=1, cutoff=0.55)
    if not matches:
        return False, ''

    matched_name = matches[0]
    for e in elements:
        if e['name'] == matched_name:
            try:
                if double:
                    e['ctrl'].DoubleClick()
                else:
                    e['ctrl'].Click()
                logger.info(f"语音点击成功: [{matched_name}] ({e['type']})")
                return True, matched_name
            except Exception as ex:
                logger.warning(f"语音点击 [{matched_name}] 失败: {ex}")
                return False, matched_name

    return False, ''


def list_elements_as_text() -> str:
    """
    列出当前窗口所有可交互元素，返回可读文本。

    Returns:
        格式化的元素列表字符串
    """
    elements = get_clickable_elements()
    if not elements:
        return '未找到可交互元素（可能需要安装 uiautomation）'

    lines = []
    seen = set()
    for e in elements:
        key = (e['name'], e['type'])
        if key not in seen:
            seen.add(key)
            lines.append(f"  • {e['name']}（{e['type']}）")

    if not lines:
        return '当前窗口没有可交互元素'
    return f"当前窗口共 {len(lines)} 个可交互元素：\n" + '\n'.join(lines[:20])
