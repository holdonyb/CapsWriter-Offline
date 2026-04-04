# coding: utf-8
"""
识别结果处理模块

提供 ResultProcessor 类用于处理服务端返回的识别结果。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import TYPE_CHECKING, Optional

import keyboard
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from config_client import ClientConfig as Config
from util.client.state import console
from util.client.websocket_manager import WebSocketManager
from util.hotword import get_hotword_manager
from util.client.output.text_output import TextOutput
from util.tools.window_detector import get_active_window_info
from . import logger
from util.common.lifecycle import lifecycle
from util.client.state import get_state
from util.client.clipboard import (
    safe_paste, paste_text, backup_clipboard_state, restore_clipboard_state
)
from util.tools.asyncio_to_thread import to_thread

if TYPE_CHECKING:
    from util.client.state import ClientState



def _estimate_tokens(text: str) -> int:
    """估算文本的 token 数"""
    if not text:
        return 0
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4)


class ResultProcessor:
    """
    识别结果处理器会车，会车处理器回车，回车处理器
    
    负责处理服务端返回的识别结果：
    - 接收 WebSocket 消息
    - 执行热词替换
    - 可选地调用 LLM 进行润色
    - 输出最终文本
    - 保存录音和日记
    """
    
    def __init__(self, state: 'ClientState'):
        """
        初始化结果处理器

        Args:
            state: 客户端状态实例
        """
        self.state = state
        self._ws_manager = WebSocketManager(state)
        self._hotword_manager = get_hotword_manager()
        self._text_output = TextOutput()
        self._exit_event = asyncio.Event()
        self._loop = asyncio.get_running_loop()  # 保存事件循环引用
        self._alt_held = False  # 切换窗口模式：Alt 是否被按住

    def request_exit(self):
        """请求退出处理循环（线程安全）"""
        logger.info("收到退出请求，设置退出事件")

        # 线程安全地设置事件
        if self._loop.is_running():
            self._loop.call_soon_threadsafe(self._exit_event.set)
            logger.debug("已通过 call_soon_threadsafe 设置退出事件")
        else:
            self._exit_event.set()
            logger.debug("已直接设置退出事件")

    async def _copy_all_editor_text(self) -> str:
        """Ctrl+A + Ctrl+C 读取当前编辑器全部文本。"""
        clipboard_state = backup_clipboard_state()
        await to_thread(keyboard.press_and_release, 'ctrl+a')
        await asyncio.sleep(0.05)
        await to_thread(keyboard.press_and_release, 'ctrl+c')
        await asyncio.sleep(0.15)
        selected = safe_paste()
        # 恢复用户原剪贴板（完整格式）
        restore_clipboard_state(clipboard_state)
        return selected or ""

    async def _copy_selected_text(self) -> str:
        """Ctrl+C 读取当前选中文本（不改变选区）。"""
        clipboard_state = backup_clipboard_state()
        await to_thread(keyboard.press_and_release, 'ctrl+c')
        await asyncio.sleep(0.15)
        selected = safe_paste()
        restore_clipboard_state(clipboard_state)
        return selected or ""

    @staticmethod
    def _is_terminal_window(window_info: dict) -> bool:
        """检测当前窗口是否终端类窗口。"""
        if not window_info:
            return False
        title = (window_info.get('title') or '').lower()
        class_name = (window_info.get('class_name') or '').lower()
        process_name = (window_info.get('process_name') or '').lower()
        text = f"{title} {class_name} {process_name}"
        terminal_keywords = [
            'terminal', 'powershell', 'pwsh', 'cmd.exe', 'windows terminal',
            'conhost', 'mintty', 'git bash'
        ]
        return any(k in text for k in terminal_keywords)

    async def _delete_last_output_text(self, text: str) -> bool:
        """
        删除最近一次输出文本（通过退格），不使用 Ctrl+A。
        仅在光标位于刚输出文本末尾时有效。
        """
        if not text:
            return False

        # 退格删除。对换行和普通字符都统一处理为一次 backspace。
        # 使用 to_thread 避免与 pynput listener 线程死锁
        def _do_backspace(n: int):
            for i in range(n):
                keyboard.press_and_release('backspace')
                if i < n - 1:
                    time.sleep(0.02)

        await to_thread(_do_backspace, len(text))
        return True

    async def _backspace_chars(self, count: int) -> None:
        """连续退格 count 次。"""
        count = max(1, count)

        def _do_backspace(n: int):
            for i in range(n):
                keyboard.press_and_release('backspace')
                if i < n - 1:
                    time.sleep(0.02)

        await to_thread(_do_backspace, count)

    def _get_last_sentence_text(self) -> str:
        """从最近一次输出中提取最后一句，用于"删除一句"估算删除长度。"""
        text = self.state.last_output_text or ""
        if not text:
            return ""
        # 以常见中英文句末符、换行作为分句边界，取最后一个非空片段
        parts = [p for p in re.split(r'[。！？!?;\n]+', text) if p]
        return parts[-1] if parts else text

    @staticmethod
    def _parse_count_token(token: str) -> int:
        """解析中文/阿拉伯数字次数。"""
        if not token:
            return 1
        token = token.strip()
        if token.isdigit():
            return max(1, int(token))
        mapping = {
            '一': 1, '两': 2, '二': 2, '三': 3, '四': 4,
            '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
        return mapping.get(token, 1)

    def _get_recent_outputs(self, count: int) -> list[str]:
        """获取最近 count 次输出，按原顺序返回。"""
        history = self.state.output_history or []
        if not history:
            return []
        count = max(1, min(count, len(history)))
        return history[-count:]

    def _get_latest_nonempty_output(self) -> str:
        """获取最近一条非空输出。"""
        history = self.state.output_history or []
        if history:
            return history[-1]
        return self.state.last_output_text or ""

    @staticmethod
    def _normalize_replace_term(term: str) -> str:
        """
        归一化替换词：
        - 去掉前后标点和引号
        - 支持口语表达"家庭的家"->"家"，"加法的加"->"加"
        """
        if not term:
            return ""
        t = term.strip(" ，。,.\"'""‘’")
        # 去掉常见后缀
        t = re.sub(r'(这个字|这个词|这个)$', '', t).strip()
        # 口语拆解：X的Y -> Y（Y 通常是目标字/词）
        if '的' in t:
            right = t.rsplit('的', 1)[-1].strip()
            if right and len(right) <= 4:
                t = right
        return t

    async def _replace_recent_outputs(self, old_parts: list[str], new_text: str) -> bool:
        """
        删除最近多次输出后回写新文本。
        注意：要求光标仍在这些文本末尾，且中间未人工插入其它字符。
        """
        if not old_parts:
            return False
        merged = ''.join(old_parts)
        if not merged:
            return False
        if not await self._delete_last_output_text(merged):
            return False
        await paste_text(new_text, restore_clipboard=Config.restore_clip)
        get_state().set_output_text(new_text)
        return True

    async def _replace_all_editor_text(self, new_text: str) -> None:
        """Ctrl+A 后粘贴，整体替换前文。"""
        await to_thread(keyboard.press_and_release, 'ctrl+a')
        await asyncio.sleep(0.05)
        await paste_text(new_text, restore_clipboard=Config.restore_clip)
        get_state().set_output_text(new_text)

    async def _try_handle_edit_commands(self, text: str) -> bool:
        """
        处理编辑命令（返回 True 表示已处理并终止默认上屏流程）：
        1) 退格/删除类命令
        2) 全选
        3) 把X替换成Y / 把X换成Y（对前文全量替换）
        4) 把前面这一段改得更... / 润色前文...
        """
        cmd = text.strip()
        if not cmd:
            return False
        window_info = get_active_window_info()

        # 连续识别模式语音命令
        cmd_clean = cmd.rstrip('。，,.')
        if cmd_clean in ('开始听写', '开启连续识别', '连续识别'):
            mgr = self.state.continuous_manager
            if mgr:
                mgr.start()
            else:
                console.print('    [yellow]连续识别管理器未初始化')
            return True

        if cmd_clean in ('暂停识别', '暂停听写'):
            mgr = self.state.continuous_manager
            if mgr and self.state.continuous_mode:
                mgr.pause()
            return True

        if cmd_clean in ('继续识别', '继续听写'):
            mgr = self.state.continuous_manager
            if mgr and self.state.continuous_mode:
                mgr.resume()
            return True

        if cmd_clean in ('停止听写', '关闭连续识别', '停止连续识别'):
            mgr = self.state.continuous_manager
            if mgr and self.state.continuous_mode:
                mgr.stop()
            return True

        # 0) 退格/删除类命令
        if cmd in {'退格', '退格。', '退格，', '删除', '删除。', '删除，'}:
            await self._backspace_chars(1)
            return True

        m_backspace = re.match(r'^(?:退格|删除)([0-9一二两三四五六七八九十]+)(?:次|个字|个字符)?$', cmd)
        if m_backspace:
            count = self._parse_count_token(m_backspace.group(1))
            await self._backspace_chars(count)
            return True

        if cmd in {'删除一句', '删除一句。', '删除一句，'}:
            # 优先按"最近输出的最后一句"估算长度；取不到时退格 20 个作为兜底
            last_sentence = self._get_last_sentence_text()
            count = len(last_sentence) if last_sentence else 20
            await self._backspace_chars(count)
            return True

        # 0b) 删除指定词：删除XXXX / 删掉XXXX（从最近输出中找到并删除该词）
        m_delete_word = re.match(r'^(?:删除|删掉)(.{2,})$', cmd)
        if m_delete_word:
            target = m_delete_word.group(1).rstrip('。，,.')
            if target and target not in {'一句', '一句。', '一句，'}:
                if self._is_terminal_window(window_info):
                    return True
                history = self.state.output_history or []
                recent = list(reversed(history[-5:])) if history else []
                if not recent:
                    latest = self.state.last_output_text or ""
                    if latest:
                        recent = [latest]
                found_source = None
                found_idx = None
                for i, src in enumerate(recent):
                    if target in src:
                        found_source = src
                        found_idx = i
                        break
                if found_source is not None:
                    replaced = found_source.replace(target, '', 1)
                    tail_count = found_idx
                    tail_parts = recent[:tail_count][::-1]
                    to_delete = ''.join(tail_parts) + found_source
                    if await self._delete_last_output_text(to_delete):
                        full_new = replaced + ''.join(tail_parts)
                        await paste_text(full_new, restore_clipboard=Config.restore_clip)
                        get_state().set_output_text(replaced)
                    console.print(f'    [green]已删除：{target}')
                else:
                    console.print(f'    [yellow]删除：最近输出中未找到 [{target}]')
                return True

        # 0c) 方向键命令：上/下/左/右 及替代说法 [N次]
        ARROW_MAP = {
            '上': 'up', '下': 'down', '左': 'left', '右': 'right',
            '向上': 'up', '向下': 'down', '向左': 'left', '向右': 'right',
            '往上': 'up', '往下': 'down', '往左': 'left', '往右': 'right',
            '上移': 'up', '下移': 'down', '左移': 'left', '右移': 'right',
        }

        # 单次方向键：上/下/左/右/向左/往右/左移...
        if cmd.rstrip('。，,.') in ARROW_MAP:
            key = ARROW_MAP[cmd.rstrip('。，,.')]
            await to_thread(keyboard.press_and_release, key)
            return True

        # 多次方向键：上3次 / 向左5个 / 往右两次 / 左移3次
        m_arrow = re.match(r'^(向[上下左右]|往[上下左右]|[上下左右]移|[上下左右])([0-9一二两三四五六七八九十]+)(?:次|个|步)?$', cmd)
        if m_arrow:
            key = ARROW_MAP[m_arrow.group(1)]
            count = self._parse_count_token(m_arrow.group(2))
            for i in range(count):
                await to_thread(keyboard.press_and_release, key)
                if i < count - 1:
                    await asyncio.sleep(0.02)
            return True

        # 0d) 组合键命令：Ctrl/Alt/Shift + 方向键
        # 例如：Ctrl左 / Ctrl+左 / Alt右 / Shift上3次
        MODIFIER_MAP = {
            'ctrl': 'ctrl', 'control': 'ctrl',
            'alt': 'alt',
            'shift': 'shift',
        }
        m_mod_arrow = re.match(
            r'^(ctrl|control|alt|shift)[+]?(向[上下左右]|往[上下左右]|[上下左右]移|[上下左右])([0-9一二两三四五六七八九十]+)?(?:次|个|步)?$',
            cmd, re.IGNORECASE
        )
        if m_mod_arrow:
            mod = MODIFIER_MAP[m_mod_arrow.group(1).lower()]
            key = ARROW_MAP[m_mod_arrow.group(2)]
            count = self._parse_count_token(m_mod_arrow.group(3)) if m_mod_arrow.group(3) else 1
            combo = f'{mod}+{key}'
            for i in range(count):
                await to_thread(keyboard.press_and_release, combo)
                if i < count - 1:
                    await asyncio.sleep(0.02)
            return True

        # 0e) Home / End 命令
        if cmd.rstrip('。，,.') in {'行首', '行头'}:
            await to_thread(keyboard.press_and_release, 'home')
            return True
        if cmd.rstrip('。，,.') in {'行尾', '行末'}:
            await to_thread(keyboard.press_and_release, 'end')
            return True
        # Ctrl+Home / Ctrl+End（跳到文档开头/结尾）
        if cmd.rstrip('。，,.') in {'文档开头', '文件开头', '最前面'}:
            await to_thread(keyboard.press_and_release, 'ctrl+home')
            return True
        if cmd.rstrip('。，,.') in {'文档结尾', '文件结尾', '最后面'}:
            await to_thread(keyboard.press_and_release, 'ctrl+end')
            return True

        # 0f) 撤销 / 重做
        if cmd.rstrip('。，,.') in {'撤销', '撤回'}:
            await to_thread(keyboard.press_and_release, 'ctrl+z')
            return True
        if cmd.rstrip('。，,.') in {'重做', '恢复'}:
            await to_thread(keyboard.press_and_release, 'ctrl+y')
            return True

        # 0g) 切换窗口模式（Alt+Tab 保持 Alt 按住，方向键选择，确定松开）
        if cmd.rstrip('。，,.') in {'切换窗口', '切换应用'}:
            if not self._alt_held:
                self._alt_held = True
                await to_thread(keyboard.press, 'alt')
                await to_thread(keyboard.press_and_release, 'tab')
                console.print('    [cyan]切换窗口模式：用"上下左右"选择，说"确定"选中，说"取消"退出')
            else:
                # 已经在切换模式，再按一次 Tab
                await to_thread(keyboard.press_and_release, 'tab')
            return True

        if cmd.rstrip('。，,.') in {'确定', '确认', '选中', '选择'}:
            if self._alt_held:
                self._alt_held = False
                await to_thread(keyboard.release, 'alt')
                console.print('    [green]已确认窗口切换')
                return True

        if cmd.rstrip('。，,.') in {'取消', '算了', '返回'}:
            if self._alt_held:
                self._alt_held = False
                await to_thread(keyboard.press_and_release, 'escape')
                await to_thread(keyboard.release, 'alt')
                console.print('    [yellow]已取消窗口切换')
                return True

        # 1) 全选命令
        if cmd in {'全选', '全选。', '全选，'}:
            # 终端里默认不执行全选，避免误操作历史/控制台
            if self._is_terminal_window(window_info):
                return True
            await to_thread(keyboard.press_and_release, 'ctrl+a')
            return True

        # 2) 强制替换命令：把X替换成Y / 把X换成Y
        m_replace = re.match(r'^把(.+?)(?:替换成|换成)(.+)$', cmd)
        if m_replace:
            if self._is_terminal_window(window_info):
                return True
            old = self._normalize_replace_term(m_replace.group(1))
            new = self._normalize_replace_term(m_replace.group(2))
            # 搜索最近 5 条输出历史，找第一条包含 old 的进行替换
            history = self.state.output_history or []
            recent = list(reversed(history[-5:])) if history else []
            if not recent:
                latest = self.state.last_output_text or ""
                if latest:
                    recent = [latest]
            found_source = None
            found_idx = None  # index in history (from end)
            for i, src in enumerate(recent):
                if old in src:
                    found_source = src
                    found_idx = i
                    break
            if found_source is not None:
                replaced = found_source.replace(old, new)
                if replaced != found_source:
                    # Need to delete: all outputs after found_source + found_source itself
                    # Collect outputs that appear after found_source in history
                    tail_count = found_idx  # number of outputs that came after
                    tail_parts = recent[:tail_count][::-1]  # restore original order
                    # Delete from tail_parts + found_source
                    to_delete = ''.join(tail_parts) + found_source
                    if await self._delete_last_output_text(to_delete):
                        # Paste replacement + all the tail parts
                        full_new = replaced + ''.join(tail_parts)
                        await paste_text(full_new, restore_clipboard=Config.restore_clip)
                        get_state().set_output_text(replaced)
            return True

        # 3) 润色前文命令（支持最近 N 次输入）
        # 示例：
        #   把前面这一段改得更有礼貌一些
        #   润色前文，改得更专业
        #   润色最近3次输入，改得更正式
        #   润色多次输入，改得更口语
        #   润色前文
        instruction = None
        source_count = 1

        # 润色最近N次输入 / 润色最近N段
        m_recent = re.match(
            r'^润色最近([0-9一二两三四五六七八九十]+)(?:次|条|段|句)?(?:输入|内容|前文|文字)?(?:[，,:： ]+(.+))?$',
            cmd
        )
        if m_recent:
            source_count = self._parse_count_token(m_recent.group(1))
            instruction = (m_recent.group(2) or '').strip(' ，。,.')
        # 润色多次输入（默认最近3次）
        if instruction is None:
            m_multi = re.match(r'^润色多次输入(?:[，,:： ]+(.+))?$', cmd)
            if m_multi:
                source_count = 3
                instruction = (m_multi.group(1) or '').strip(' ，。,.')

        m_rewrite = re.match(r'^把前面(?:这段|这一段|内容|文字)?(?:改成|改得|改为|改)(.+)$', cmd)
        if m_rewrite and instruction is None:
            instruction = m_rewrite.group(1).strip(' ，。,.')
        else:
            m_polish = re.match(r'^润色前文(?:[，,:： ]+(.+))?$', cmd)
            if m_polish and instruction is None:
                instruction = (m_polish.group(1) or '').strip(' ，。,.')

        if instruction is not None:
            if self._is_terminal_window(window_info):
                return True

            # 优先使用用户当前选中的文本（你全选后说"润色前文"会命中这里）
            selected_source = await self._copy_selected_text()
            use_selected_source = bool(selected_source and selected_source.strip())

            # 未选中时，默认拿最近一次；"润色最近N次输入"会使用 N 次
            source_parts = self._get_recent_outputs(source_count)
            source = selected_source if use_selected_source else ''.join(source_parts)
            if not source:
                console.print('    [yellow]润色：未找到可润色的内容（无选中文字且无历史输出）')
                return True

            console.print(f'    [cyan]润色中{"(选中文字)" if use_selected_source else ""}...')

            # 用"润色"角色，但禁用选区读取，直接把前文和指令喂给模型
            from util.llm.llm_handler import get_handler
            handler = get_handler()
            role = handler.roles.get('润色') or handler.role_loader.get_default_role()

            # 复制一份配置，避免污染全局角色配置
            from copy import copy
            role_cfg = copy(role)
            role_cfg.enable_read_selection = False
            role_cfg.enable_history = False

            req = (
                f"请按要求修改原文。\n"
                f"要求：{instruction or '润色优化，不改变原意'}\n\n"
                f"原文：\n{source}"
            )
            result_text, _, _ = await to_thread(
                handler.process, role_cfg, req, None, None, lambda: False
            )
            final_text = (result_text or source).strip()
            if use_selected_source:
                # 直接覆盖当前选区，不走回删
                await paste_text(final_text, restore_clipboard=Config.restore_clip)
                get_state().set_output_text(final_text)
            else:
                await self._replace_recent_outputs(source_parts, final_text)
            return True

        # 4) 只读查询命令（结果显示在 Toast 弹窗，不上屏）
        # 支持：问一下 <问题> / 总结一下 / 解释一下 / 翻译一下
        query_task = None  # (system_prompt, user_content)

        m_ask = re.match(r'^问一下[，,：:\s]*(.+)$', cmd)
        if m_ask:
            question = m_ask.group(1).strip()
            selected = await self._copy_selected_text()
            if selected and selected.strip():
                query_task = ('请回答用户关于所提供文字的问题。', f'文字：\n{selected.strip()}\n\n问题：{question}')
            else:
                query_task = ('你是一个助手，简洁回答用户问题。', question)

        if query_task is None and cmd in {'总结一下', '总结一下。', '帮我总结', '帮我总结。'}:
            selected = await self._copy_selected_text()
            if selected and selected.strip():
                query_task = ('请用简洁的语言总结以下文字。', selected.strip())
            else:
                last = self._get_latest_nonempty_output()
                if last:
                    query_task = ('请用简洁的语言总结以下文字。', last)

        if query_task is None and cmd in {'解释一下', '解释一下。', '帮我解释', '帮我解释。'}:
            selected = await self._copy_selected_text()
            if selected and selected.strip():
                query_task = ('请解释以下文字的含义。', selected.strip())
            else:
                last = self._get_latest_nonempty_output()
                if last:
                    query_task = ('请解释以下文字的含义。', last)

        if query_task is None and cmd in {'翻译一下', '翻译一下。', '帮我翻译', '帮我翻译。'}:
            selected = await self._copy_selected_text()
            if selected and selected.strip():
                query_task = ('请将以下文字翻译成中文（如果已是中文则翻译成英文）。', selected.strip())
            else:
                last = self._get_latest_nonempty_output()
                if last:
                    query_task = ('请将以下文字翻译成中文（如果已是中文则翻译成英文）。', last)

        if query_task is not None:
            sys_prompt, user_content = query_task
            await self._run_toast_query(sys_prompt, user_content)
            return True

        # 5) D1: 语音点击 UI 元素
        # 命令：点击/按/单击 XXX [按钮/键/选项] / 双击 XXX / 有什么按钮
        if cmd in {'有什么按钮', '有什么按钮。', '有什么选项', '有什么选项。',
                   '列出按钮', '列出按钮。', '列出选项', '列出选项。'}:
            from util.tools.ui_automation import list_elements_as_text
            info = list_elements_as_text()
            console.print(f'    [cyan]{info}')
            try:
                from util.ui.toast import toast
                toast(info, duration=5000)
            except Exception:
                pass
            return True

        m_dblclick = re.match(r'^双击(.+?)(?:按钮|键|选项|菜单|标签)?$', cmd)
        if m_dblclick:
            label = m_dblclick.group(1).strip()
            from util.tools.ui_automation import voice_click
            ok, matched = voice_click(label, double=True)
            if ok:
                console.print(f'    [green]双击：{matched}')
            else:
                console.print(f'    [yellow]双击：未找到 [{label}]')
            return True

        m_click = re.match(
            r'^(?:点击|点一下|单击|按一下|按)(.+?)(?:按钮|键|选项|菜单|标签)?$',
            cmd
        )
        if m_click:
            label = m_click.group(1).strip()
            from util.tools.ui_automation import voice_click
            ok, matched = voice_click(label, double=False)
            if ok:
                console.print(f'    [green]点击：{matched}')
            else:
                console.print(f'    [yellow]点击：未找到 [{label}]')
            return True

        # 6) D2: 系统操作命令
        # 搜索 <内容>
        m_search = re.match(r'^搜索[：:\s]*(.+)$', cmd)
        if m_search:
            query = m_search.group(1).strip()
            import urllib.parse
            import webbrowser
            url = 'https://www.google.com/search?q=' + urllib.parse.quote(query)
            webbrowser.open(url)
            console.print(f'    [cyan]搜索：{query}')
            return True

        # 打开 <应用名>
        m_open = re.match(r'^打开[：:\s]*(.+)$', cmd)
        if m_open:
            app_name = m_open.group(1).strip()
            import subprocess
            try:
                subprocess.Popen(['start', app_name], shell=True)
                console.print(f'    [cyan]打开：{app_name}')
            except Exception as e:
                console.print(f'    [red]打开失败：{e}')
            return True

        # 截图
        if cmd in {'截图', '截图。', '截一下屏', '截一下屏。'}:
            import subprocess
            subprocess.Popen(['powershell', '-command',
                              'Add-Type -AssemblyName System.Windows.Forms;'
                              '[System.Windows.Forms.SendKeys]::SendWait("%+s")'],
                             creationflags=0x08000000)
            console.print('    [cyan]截图：已触发 Win+Shift+S')
            return True

        # 复制这段
        if cmd in {'复制这段', '复制这段。', '复制选中', '复制选中。'}:
            selected = await self._copy_selected_text()
            if selected:
                try:
                    import pyperclip
                    pyperclip.copy(selected)
                except Exception:
                    pass
                console.print(f'    [cyan]已复制：{selected[:30]}')
            return True

        # 7) 打开设置
        if cmd.rstrip('。，,.') in {'打开设置', '设置', '设置面板'}:
            console.print('    [cyan]正在打开设置面板...')
            try:
                from util.client.ui.settings_window import open_settings
                open_settings()
            except Exception as e:
                console.print(f'    [red]无法打开设置面板: {e}')
            return True

        # 8) 重启客户端
        if cmd.rstrip('。，,.') in {'重启', '重启客户端'}:
            console.print('    [bold cyan]正在重启客户端...')
            from core_client import request_restart
            request_restart()
            return True

        return False

    async def _run_toast_query(self, system_prompt: str, user_content: str) -> None:
        """使用 Toast 弹窗显示 LLM 查询结果（不上屏）。"""
        try:
            from util.llm.llm_handler import get_handler
            from util.llm.llm_output_toast import handle_toast_mode
            from copy import copy

            handler = get_handler()
            # 优先使用助手角色（toast 输出模式），回退到小助理
            role = (
                handler.roles.get('小助理')
                or handler.roles.get('大助理')
                or handler.role_loader.get_default_role()
            )
            if not role:
                console.print('    [yellow]查询失败：未找到可用的助手角色')
                return

            role_cfg = copy(role)
            role_cfg.enable_read_selection = False
            role_cfg.enable_history = False
            role_cfg.output_mode = 'toast'
            # 临时覆盖 system_prompt
            role_cfg.system_prompt = system_prompt

            console.print(f'    [cyan]查询中...')
            asyncio.create_task(handle_toast_mode(
                user_content, role_config=role_cfg, content=user_content
            ))
        except Exception as e:
            logger.error(f"只读查询失败: {e}", exc_info=True)
            console.print(f'    [red]查询失败: {e}')
    
    def _format_llm_result(self, llm_result) -> str:
        """格式化 LLM 结果输出"""
        polished_text = llm_result.result
        role_name = llm_result.role_name
        processed = llm_result.processed
        token_count = llm_result.token_count
        generation_time = llm_result.generation_time  # 使用生成时间（从第一个 token 开始）

        polished_text = polished_text.replace('\n', ' ').replace('\r', ' ')
        max_display_length = 50
        if len(polished_text) > max_display_length:
            polished_text = polished_text[:max_display_length] + '...'

        role_label = f'[{role_name}]' if role_name else ''
        result_text = f'[green]{polished_text}[/green]' if processed else polished_text

        if token_count == 0 and polished_text:
            token_count = _estimate_tokens(polished_text)

        # 使用生成时间计算速度（更准确）
        if processed and generation_time > 0:
            speed = token_count / generation_time if token_count > 0 else 0
            speed_label = f'    {speed:.1f} tokens/s' if speed > 0 else ''
        else:
            speed_label = ''

        return f'    模型结果{role_label}：{result_text}{speed_label}'
    
    def _log_modifier_key_state(self) -> None:
        """
        检测并记录当前按下的所有键
        
        用于调试按键卡住问题。
        """
        try:
            import keyboard
            
            # 获取所有当前按下的键
            pressed_keys = keyboard._pressed_events
            
            # if pressed_keys:
            key_names = list(pressed_keys.keys())
            logger.debug(f"当前按下的键: {key_names}")
                
        except Exception as e:
            logger.debug(f"检测按键状态失败: {e}")
    
    async def process_loop(self) -> None:
        """主处理循环"""
        if not await self._ws_manager.connect():
            logger.warning("WebSocket 连接检查失败")
            return

        console.print('[green]连接成功\n')
        logger.info("WebSocket 连接成功")

        try:
            while True:
                # 检查退出事件
                if self._exit_event.is_set():
                    logger.info("检测到退出事件，停止处理循环")
                    break

                # 创建一个任务来接收消息
                recv_task = asyncio.create_task(self.state.websocket.recv())
                logger.debug("已创建接收消息任务")

                # 创建一个任务来等待退出事件
                exit_wait_task = asyncio.create_task(self._exit_event.wait())
                logger.debug("已创建退出等待任务")

                # 等待任意一个任务完成
                done, pending = await asyncio.wait(
                    [recv_task, exit_wait_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                logger.debug(f"任务完成: done={len(done)}, pending={len(pending)}")

                # 取消未完成的任务
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                # 检查是否是退出请求
                if exit_wait_task in done:
                    logger.info("收到退出请求，停止处理循环")
                    # 取消接收任务
                    if recv_task not in done and not recv_task.done():
                        recv_task.cancel()
                        try:
                            await recv_task
                        except asyncio.CancelledError:
                            pass
                    break

                # 如果是接收任务完成，处理消息
                if recv_task in done:
                    try:
                        message = recv_task.result()
                        # 再次检查退出标志
                        if lifecycle.is_shutting_down:
                            logger.info("处理消息前检测到退出请求")
                            break
                        logger.debug("开始处理消息")
                        await self._handle_message(message)
                        logger.debug("消息处理完成")
                    except asyncio.CancelledError:
                        raise
                    except ConnectionClosedError:
                        logger.warning("WebSocket 连接已关闭")
                        break
                    except Exception as e:
                        logger.error(f"处理消息时发生错误: {e}", exc_info=True)
                        raise

        except ConnectionClosedError:
            console.print('[red]连接断开\n')
            logger.error("WebSocket 连接断开")
        except ConnectionClosedOK:
            console.print('[yellow]连接已正常关闭\n')
            logger.info("WebSocket 连接已正常关闭")
        except asyncio.CancelledError:
            logger.info("处理循环被取消")
            raise
        except Exception as e:
            logger.error(f"接收结果时发生错误: {e}", exc_info=True)
            print(e)
        finally:
            self._cleanup()

    async def _handle_message(self, message: str) -> None:
        """处理接收到的消息"""
        import json
        
        # 再次检查退出标志
        if lifecycle.is_shutting_down:
            return

        message = json.loads(message)

        # 使用 text 字段（简单拼接结果，用于语音输入）
        text = message['text']
        original_text = text  # 保存原始识别结果
        delay = message['time_complete'] - message['time_submit']

        if message['is_final']:
            logger.info(f"收到最终识别结果: {text}, 时延: {delay:.2f}s")
        else:
            logger.debug(
                f"接收到识别结果，文本: {text[:50]}{'...' if len(text) > 50 else ''}, "
                f"时延: {delay:.2f}s"
            )

        # 如果非最终结果，继续等待
        if not message['is_final']:
            return

        # 连续识别暂停时，只检查恢复/停止命令，其他丢弃
        mgr = self.state.continuous_manager
        if mgr and self.state.continuous_mode and mgr.paused:
            stripped = text.strip().rstrip('。，,.')
            if stripped in ('继续识别', '继续听写'):
                mgr.resume()
            elif stripped in ('停止听写', '关闭连续识别', '停止连续识别'):
                mgr.stop()
            else:
                logger.debug(f"连续识别暂停中，丢弃: {text}")
            return

        # 繁体转换
        if Config.traditional_convert:
            try:
                from util.zhconv import convert as zhconv_convert
                text = zhconv_convert(text, Config.traditional_locale)
                logger.debug(f"繁体转换后: {text[:50]}{'...' if len(text) > 50 else ''}")
            except Exception as e:
                logger.warning(f"繁体转换失败: {e}")

        # 1. 音素检索，热词替换
        correction_result = self._hotword_manager.get_phoneme_corrector().correct(text, k=10)
        if Config.hot:
            text = correction_result.text

        # 2. 去掉末尾符号
        text = TextOutput.strip_punc(text)

        # 3. 正则替换
        text = self._hotword_manager.get_rule_corrector().substitute(text)

        # 3.5 编辑命令优先处理（全选/替换/润色前文）
        if await self._try_handle_edit_commands(text):
            return

        # 保存最近一次识别结果
        self.state.last_recognition_text = text

        # 控制台输出
        console.print(f'    转录时延：{delay:.2f}s')

        # 先显示原始识别结果
        original_text_stripped = TextOutput.strip_punc(original_text)
        console.print(f'    识别结果：[green]{original_text_stripped}')

        # 录音指示器：显示识别结果
        try:
            from util.client.ui.recording_indicator import show_result
            show_result(text)
        except Exception:
            pass

        # 如果发生了热词替换，显示替换后的结果
        if original_text_stripped != text:
            console.print(f'    热词替换：[cyan]{text}')
            logger.debug(f"热词替换后: {text[:50]}{'...' if len(text) > 50 else ''}")

        # 热词匹配情况
        matched_hotwords = correction_result.matchs
        potential_hotwords = correction_result.similars

        # 1. 显示完全匹配/已替换的热词
        if matched_hotwords and Config.hot:
            # 提取热词文本 (现为 (原词, 热词, 分数))
            replaced_info = [f"{origin}->[green4]{hw}[/]" for origin, hw, score in matched_hotwords]
            console.print(f'    完全匹配：{", ".join(replaced_info)}')

        # 2. 显示潜在热词（从上下文热词中排除已替换的）
        if potential_hotwords and Config.hot:
            replaced_set = {hw for origin, hw, score in matched_hotwords}
            potential_matches = [(origin, hw, score) for origin, hw, score in potential_hotwords if hw not in replaced_set]
            
            if potential_matches:
                # 格式化潜在匹配列表，显示分数
                potential_str = ", ".join([f"{origin}->{hw}({score:.2f})" for origin, hw, score in potential_matches[:5]])
                if len(potential_matches) > 5:
                    potential_str += f" ... (共{len(potential_matches)}个)"
                console.print(f'    潜在热词：[yellow]{potential_str}')

        # 窗口兼容性检测
        paste = Config.paste
        window_info = get_active_window_info()

        if window_info:
            window_title = window_info.get('title', '')
            compatibility_apps = ['weixin', '微信', 'wechat', 'WeChat']
            if window_title in compatibility_apps:
                paste = True
                logger.debug(f"检测到兼容性应用: {window_title}，使用粘贴模式")

        # LLM 处理和输出
        llm_result = None
        if Config.llm_enabled:
            from util.llm.llm_process_text import llm_process_text
            llm_result = await llm_process_text(
                text,
                paste=paste,
                matched_hotwords=potential_hotwords  # 传递上下文热词给 LLM
            )
        else:
            await self._text_output.output(text, paste=paste)
            get_state().set_output_text(text)

        # 保存录音与写入 md 文件
        file_audio = None
        if Config.save_audio:
            from util.client.diary.diary_writer import DiaryWriter

            # 重命名音频文件
            file_path = self.state.pop_audio_file(message['task_id'])
            if file_path:
                from util.client.audio.file_manager import AudioFileManager
                file_manager = AudioFileManager()
                file_manager.file_path = file_path
                file_audio = file_manager.rename(text, message['time_start'])
                logger.debug(f"保存录音文件: {file_audio}")

            # 写入日记
            diary_writer = DiaryWriter()
            diary_writer.write(text, message['time_start'], file_audio)
            logger.debug("写入 MD 文件")

        # LLM 结果显示和保存
        if Config.llm_enabled and llm_result and llm_result.processed:
            console.print(self._format_llm_result(llm_result))
            from util.llm.llm_write_md import write_llm_md
            write_llm_md(
                llm_result.input_text,
                llm_result.result,
                llm_result.role_name,
                message['time_start'],
                file_audio
            )
            logger.debug("写入 LLM MD 文件")

        # 检测修饰键状态（调试用）
        self._log_modifier_key_state()

        console.line()
    
    def _cleanup(self) -> None:
        """清理资源"""
        if self.state.websocket is not None:
            try:
                if self.state.websocket.closed:
                    self.state.websocket = None
                    logger.debug("WebSocket 连接已清理")
            except Exception:
                self.state.websocket = None
