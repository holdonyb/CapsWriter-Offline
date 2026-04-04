# coding: utf-8
"""
剪贴板工具模块

提供统一的剪贴板操作接口，包括：
1. 安全读取剪贴板（支持多种编码）
2. 安全写入剪贴板
3. 剪贴板保存/恢复上下文管理器
4. 粘贴文本（模拟 Ctrl+V）
"""
import asyncio
import platform
from contextlib import contextmanager
from typing import Any
import pyclip
from pynput import keyboard
from . import logger


# 支持的编码列表
CLIPBOARD_ENCODINGS = ['utf-8', 'gbk', 'utf-16', 'latin1']

# Windows 全格式剪贴板支持（尽力而为）
try:
    import win32clipboard  # type: ignore
except Exception:
    win32clipboard = None


def safe_paste() -> str:
    """
    安全地从剪贴板读取并解码文本

    尝试多种编码方式，确保能够正确读取

    Returns:
        解码后的文本字符串，失败返回空字符串
    """
    try:
        clipboard_data = pyclip.paste()

        # 尝试多种编码方式
        for encoding in CLIPBOARD_ENCODINGS:
            try:
                return clipboard_data.decode(encoding)
            except (UnicodeDecodeError, AttributeError):
                continue

        # 如果所有编码都失败，返回空字符串
        logger.debug(f"剪贴板解码失败，尝试了编码: {CLIPBOARD_ENCODINGS}")
        return ""

    except Exception as e:
        logger.warning(f"剪贴板读取失败: {e}")
        return ""


def safe_copy(content: str) -> bool:
    """
    安全地复制内容到剪贴板

    Args:
        content: 要复制的内容

    Returns:
        是否成功
    """
    if not content:
        return False

    try:
        pyclip.copy(content)
        logger.debug(f"剪贴板写入成功，长度: {len(content)}")
        return True
    except Exception as e:
        logger.warning(f"剪贴板写入失败: {e}")
        return False


def copy_to_clipboard(content: str):
    """
    复制内容到剪贴板（兼容旧 API）

    Args:
        content: 要复制的内容
    """
    safe_copy(content)


def backup_clipboard_state() -> Any:
    """
    备份剪贴板状态。

    - Windows: 尝试备份全部可读格式（文本/图片/富文本等）
    - 其他平台: 退化为文本备份
    """
    if platform.system() == 'Windows' and win32clipboard:
        data_items = []
        try:
            win32clipboard.OpenClipboard()
            fmt = 0
            while True:
                fmt = win32clipboard.EnumClipboardFormats(fmt)
                if fmt == 0:
                    break
                try:
                    data = win32clipboard.GetClipboardData(fmt)
                    data_items.append((fmt, data))
                except Exception:
                    # 某些格式不可读，忽略
                    pass
            return {'mode': 'raw', 'items': data_items}
        except Exception as e:
            logger.debug(f"全格式备份失败，退回文本备份: {e}")
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
    return {'mode': 'text', 'text': safe_paste()}


def restore_clipboard_state(state: Any) -> bool:
    """恢复剪贴板状态（与 backup_clipboard_state 配套）。"""
    if not state:
        return False
    mode = state.get('mode') if isinstance(state, dict) else None
    if mode == 'raw' and platform.system() == 'Windows' and win32clipboard:
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            for fmt, data in state.get('items', []):
                try:
                    win32clipboard.SetClipboardData(fmt, data)
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.debug(f"全格式恢复失败: {e}")
            return False
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
    if mode == 'text':
        text = state.get('text', '')
        try:
            pyclip.copy(text)
            return True
        except Exception:
            return False
    return False


@contextmanager
def save_and_restore_clipboard():
    """
    剪贴板保存/恢复上下文管理器

    用法:
        with save_and_restore_clipboard():
            # 在这里操作剪贴板
            pyclip.copy("临时内容")
        # 退出后剪贴板恢复原内容
    """
    original = backup_clipboard_state()
    try:
        yield
    finally:
        if original:
            restore_clipboard_state(original)
            logger.debug("剪贴板已恢复")


async def paste_text(text: str, restore_clipboard: bool = True):
    """
    通过模拟 Ctrl+V 粘贴文本

    Args:
        text: 要粘贴的文本
        restore_clipboard: 粘贴后是否恢复原剪贴板内容
    """
    # 保存剪切板（尽可能保留全部格式）
    original = None
    if restore_clipboard:
        try:
            original = backup_clipboard_state()
        except Exception:
            pass

    # 复制要粘贴的文本
    pyclip.copy(text)
    logger.debug(f"已复制文本到剪贴板，长度: {len(text)}")

    # 粘贴结果（使用 pynput 模拟 Ctrl+V）
    controller = keyboard.Controller()
    if platform.system() == 'Darwin':
        # macOS: Command+V
        with controller.pressed(keyboard.Key.cmd):
            controller.tap('v')
    else:
        # Windows/Linux: Ctrl+V
        with controller.pressed(keyboard.Key.ctrl):
            controller.tap('v')
    
    logger.debug("已发送粘贴命令 (Ctrl+V)")

    # 还原剪贴板
    if restore_clipboard and original:
        await asyncio.sleep(0.1)
        restore_clipboard_state(original)
        logger.debug("剪贴板已恢复（完整/文本）")
