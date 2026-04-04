# coding: utf-8
"""
文本输出模块

提供 TextOutput 类用于将识别结果输出到当前窗口。
"""

from __future__ import annotations

import asyncio
import platform
from typing import Optional
import re

import keyboard
import pyclip
from pynput import keyboard as pynput_keyboard

from config_client import ClientConfig as Config
from util.client.clipboard import backup_clipboard_state, restore_clipboard_state
from util.tools.window_detector import get_active_window_info
from . import logger


SEND_TOKEN = '[[CW_SEND]]'
NEWLINE_TOKEN = '[[CW_NEWLINE]]'


class TextOutput:
    """
    文本输出器
    
    提供文本输出功能，支持模拟打字和粘贴两种方式。
    """
    
    @staticmethod
    def strip_punc(text: str) -> str:
        """
        消除末尾最后一个标点
        
        Args:
            text: 原始文本
            
        Returns:
            去除末尾标点后的文本
        """
        if not text or not Config.trash_punc:
            return text
        clean_text = re.sub(f"(?<=.)[{Config.trash_punc}]$", "", text)
        return clean_text
    
    async def output(self, text: str, paste: Optional[bool] = None) -> None:
        """
        输出识别结果
        
        根据配置选择使用模拟打字或粘贴方式输出文本。
        
        Args:
            text: 要输出的文本
            paste: 是否使用粘贴方式（None 表示使用配置值）
        """
        if not text:
            return
        
        # 确定输出方式
        if paste is None:
            paste = Config.paste
        
        if paste:
            await self._paste_text(text)
        else:
            self._type_text(text)
    
    async def _paste_text(self, text: str) -> None:
        """
        通过粘贴方式输出文本
        
        Args:
            text: 要粘贴的文本
        """
        logger.debug(f"使用粘贴方式输出文本，长度: {len(text)}")
        
        # 保存剪贴板（尽可能保留图片/富文本等格式）
        temp = backup_clipboard_state() if Config.restore_clip else None
        
        # 粘贴结果（使用 pynput 模拟 Ctrl+V / Enter / Ctrl+Enter）
        controller = pynput_keyboard.Controller()
        is_wechat = self._is_wechat_window()
        for kind, content in self._iter_output_actions(text):
            if kind == 'text' and content:
                pyclip.copy(content)
                if platform.system() == 'Darwin':
                    with controller.pressed(pynput_keyboard.Key.cmd):
                        controller.tap('v')
                else:
                    with controller.pressed(pynput_keyboard.Key.ctrl):
                        controller.tap('v')
            elif kind == 'send':
                controller.tap(pynput_keyboard.Key.enter)
            elif kind == 'newline':
                self._tap_newline(controller, is_wechat)

        logger.debug("已发送粘贴/发送/换行命令")
        
        # 还原剪贴板
        if Config.restore_clip and temp is not None:
            await asyncio.sleep(0.1)
            restore_clipboard_state(temp)
            logger.debug("剪贴板已恢复")
    
    def _type_text(self, text: str) -> None:
        """
        通过模拟打字方式输出文本

        使用 keyboard.write 替代 pynput.keyboard.Controller.type()，
        避免与中文输入法冲突。

        Args:
            text: 要输出的文本
        """
        logger.debug(f"使用打字方式输出文本，长度: {len(text)}")
        is_wechat = self._is_wechat_window()
        for kind, content in self._iter_output_actions(text):
            if kind == 'text' and content:
                keyboard.write(content)
            elif kind == 'send':
                keyboard.press_and_release('enter')
            elif kind == 'newline':
                if is_wechat:
                    keyboard.press_and_release('ctrl+enter')
                else:
                    keyboard.press_and_release('enter')

    @staticmethod
    def _is_wechat_window() -> bool:
        """检测当前前台是否微信窗口。"""
        info = get_active_window_info() or {}
        title = (info.get('title') or '').lower()
        process_name = (info.get('process_name') or '').lower()
        app_name = (info.get('app_name') or '').lower()
        combined = f"{title} {process_name} {app_name}"
        return any(k in combined for k in ['wechat', 'weixin', '微信'])

    @staticmethod
    def _iter_output_actions(text: str) -> list[tuple[str, str]]:
        """
        将输出文本解析成动作序列：
        - ('text', '普通文本')
        - ('send', '')
        - ('newline', '')
        """
        # 兼容历史规则：将 '\n' 视作 send
        normalized = text.replace('\r\n', '\n').replace('\r', '\n')
        normalized = normalized.replace('\n', SEND_TOKEN)
        pattern = f"({re.escape(SEND_TOKEN)}|{re.escape(NEWLINE_TOKEN)})"
        chunks = re.split(pattern, normalized)
        actions: list[tuple[str, str]] = []
        for chunk in chunks:
            if not chunk:
                continue
            if chunk == SEND_TOKEN:
                actions.append(('send', ''))
            elif chunk == NEWLINE_TOKEN:
                actions.append(('newline', ''))
            else:
                actions.append(('text', chunk))
        return actions

    @staticmethod
    def _tap_newline(controller: pynput_keyboard.Controller, is_wechat: bool) -> None:
        """模拟“换行”动作：微信中使用 Ctrl+Enter，其他应用使用 Enter。"""
        if is_wechat:
            with controller.pressed(pynput_keyboard.Key.ctrl):
                controller.tap(pynput_keyboard.Key.enter)
        else:
            controller.tap(pynput_keyboard.Key.enter)
