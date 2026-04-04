# coding: utf-8
"""
配置 Override 读写工具

通过 JSON override 文件修改配置，不直接修改 Python 源文件。
- config_override.json: 覆盖 ClientConfig 字段
- llm_override.json: 覆盖 LLM 角色配置
"""

import json
from pathlib import Path

from config_client import BASE_DIR

_CONFIG_OVERRIDE_PATH = Path(BASE_DIR) / 'config_override.json'
_LLM_OVERRIDE_PATH = Path(BASE_DIR) / 'llm_override.json'


# ==================== ClientConfig Override ====================

def load_overrides() -> dict:
    """读取 config_override.json，不存在则返回空 dict"""
    if not _CONFIG_OVERRIDE_PATH.exists():
        return {}
    try:
        return json.loads(_CONFIG_OVERRIDE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_overrides(data: dict) -> None:
    """写入 config_override.json"""
    _CONFIG_OVERRIDE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def get_effective_value(key: str, default=None):
    """override 优先，否则返回 ClientConfig 的值，最后用 default"""
    overrides = load_overrides()
    if key in overrides:
        return overrides[key]
    from config_client import ClientConfig
    return getattr(ClientConfig, key, default)


def apply_overrides_to_config():
    """将 config_override.json 中的值覆盖到 ClientConfig 上"""
    overrides = load_overrides()
    if not overrides:
        return
    from config_client import ClientConfig
    for key, value in overrides.items():
        if hasattr(ClientConfig, key):
            setattr(ClientConfig, key, value)


# ==================== LLM Role Override ====================

def load_role_overrides() -> dict:
    """读取 llm_override.json

    格式: { "角色模块名": { "provider": ..., "model": ..., ... }, ... }
    模块名使用文件 stem，如 "default", "润色", "翻译"
    """
    if not _LLM_OVERRIDE_PATH.exists():
        return {}
    try:
        return json.loads(_LLM_OVERRIDE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_role_overrides(data: dict) -> None:
    """写入 llm_override.json"""
    _LLM_OVERRIDE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def get_role_override(role_stem: str) -> dict:
    """获取某个角色的 override 配置"""
    return load_role_overrides().get(role_stem, {})


def set_role_override(role_stem: str, overrides: dict) -> None:
    """设置某个角色的 override 配置"""
    all_overrides = load_role_overrides()
    if overrides:
        all_overrides[role_stem] = overrides
    else:
        all_overrides.pop(role_stem, None)
    save_role_overrides(all_overrides)
