# coding: utf-8
"""
应用感知上下文注入器

将当前活跃窗口的应用名称注入到 LLM system prompt 末尾，
让模型根据自身训练知识自行判断合适的输出风格，
而非由我们硬编码每个应用的语调规则。
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def build_app_context_hint(window_info: Optional[dict]) -> str:
    """
    从窗口信息中提取应用名称，返回一行简短的上下文描述。

    Args:
        window_info: 来自 get_active_window_info() 的窗口信息

    Returns:
        一行上下文描述（如"当前应用：微信"），或空字符串
    """
    if not window_info:
        return ''

    # 优先用可读的 app_name，其次 process_name，最后 title 前段
    app_name = (
        window_info.get('app_name')
        or window_info.get('process_name')
        or ''
    )
    # 去掉 .exe 后缀，截取合理长度
    app_name = app_name.replace('.exe', '').replace('.EXE', '').strip()
    if len(app_name) > 40:
        app_name = app_name[:40]

    if not app_name:
        # 用窗口标题前 20 字作为兜底
        title = (window_info.get('title') or '').strip()
        app_name = title[:20] if title else ''

    if not app_name:
        return ''

    logger.debug(f"应用感知：注入当前应用名 [{app_name}]")
    return f'当前应用：{app_name}'


def inject_app_context(original_system_prompt: str, window_info: Optional[dict]) -> str:
    """
    将应用名称上下文注入到 system_prompt 末尾。
    仅提供事实（当前是哪个应用），语调判断完全交给模型。

    Args:
        original_system_prompt: 角色原始 system prompt
        window_info: 当前窗口信息

    Returns:
        增加了应用名称的 system_prompt（若无法识别则原样返回）
    """
    from config_client import ClientConfig as Config
    if not getattr(Config, 'app_aware_tone', True):
        return original_system_prompt

    hint = build_app_context_hint(window_info)
    if not hint:
        return original_system_prompt

    separator = '\n\n' if original_system_prompt.strip() else ''
    return f'{original_system_prompt}{separator}{hint}'
