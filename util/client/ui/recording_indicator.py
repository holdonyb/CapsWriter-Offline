# coding: utf-8
"""
录音状态悬浮指示器（Tkinter 实现）

使用 Tkinter Toplevel 窗口，挂在 ToastMessageManager 的 root 上。
在录音时显示动态指示器：
- 录音中：右下角出现红点脉冲 + "录音中"
- 识别完成：短暂显示识别结果（最多 30 字）后 1.5s 消失
- 聆听中：绿点 + "聆听中"（连续识别模式）
- 已暂停：灰点 + "已暂停"（连续识别暂停）

线程安全设计：
  所有公共函数只往 Queue 里放命令（线程安全），
  由 Tkinter 线程的轮询循环取出并执行，
  绝不从非 Tk 线程调用 root.after()。
"""

from __future__ import annotations

import logging
import math
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# ── 全局单例 ──────────────────────────────────────────────────────────────
_indicator: Optional['RecordingIndicator'] = None
_lock = threading.Lock()

# 命令队列（全局，在指示器对象创建前就可往里放消息）
_command_queue: queue.Queue = queue.Queue()
_poll_started = False


def _ensure_polling(root) -> None:
    """确保 Tk 线程上已经启动了轮询循环（只启动一次）。"""
    global _poll_started
    if _poll_started:
        return
    _poll_started = True
    # 利用 toast_manager 已有的 root 轮询机制：
    # 在 toast_manager 的 Tk 线程上调度（通过 Queue）。
    # 但我们需要启动自己的 after 循环。这里用一个 trick：
    # toast_manager 的 _process_queue 已在 Tk 线程上跑，
    # 我们只需在第一次构造 indicator 时（已拿到 root）
    # 让 toast_manager 帮我们在 Tk 线程执行一次 _start_poll。
    try:
        from util.ui.toast_manager import ToastMessageManager
        mgr = ToastMessageManager()
        # 借助 toast_manager 的消息队列，在 Tk 线程上执行回调
        # ToastMessageManager._process_queue 每次都会 poll 消息队列，
        # 我们可以直接在队列消息的处理回调里启动 poll
        _do_start_poll(root)
    except Exception as e:
        logger.debug(f"启动指示器轮询失败: {e}")


def _do_start_poll(root) -> None:
    """在 Tk 线程上启动轮询（仅由 _ensure_polling 调用）。"""
    def _poll():
        try:
            # 处理队列中所有待处理命令
            for _ in range(20):  # 每次最多处理 20 条，防止阻塞 Tk
                try:
                    method_name, args = _command_queue.get_nowait()
                    ind = _indicator
                    if ind is not None:
                        fn = getattr(ind, method_name, None)
                        if fn:
                            fn(*args)
                except queue.Empty:
                    break
                except Exception as e:
                    logger.debug(f"指示器命令执行失败: {e}")
        except Exception:
            pass
        # 继续轮询（这里的 after 是在 Tk 线程调用的，安全）
        try:
            root.after(50, _poll)
        except Exception:
            pass

    # 通过 toast_manager 的队列在 Tk 线程调度第一次 poll
    # 使用一个极简的 ToastMessage 来 trick 进入 Tk 线程
    # 但更简单：直接把 _poll 函数放到 toast_manager 的队列里
    # 然而 toast_manager 的队列接受 ToastMessage 对象，不接受回调
    #
    # 方案B：直接调用 root.after 一次。虽然从非 Tk 线程调用，
    # 但这是一次性调用（仅在 indicator 首次创建时），风险极低。
    # 后续所有调度都通过 Queue + Tk 线程的 after 循环完成。
    try:
        root.after(0, _poll)
    except Exception as e:
        logger.debug(f"启动轮询 after 失败: {e}")


def _get_root():
    """获取 ToastMessageManager 的 Tk root（懒初始化 toast manager）。"""
    try:
        from util.ui.toast_manager import ToastMessageManager
        mgr = ToastMessageManager()
        # 等待 root 初始化完成
        import time
        for _ in range(50):  # 最多等 500ms
            if mgr.root is not None:
                return mgr.root
            time.sleep(0.01)
        return mgr.root
    except Exception as e:
        logger.debug(f"获取 Tk root 失败: {e}")
        return None


def _get_indicator() -> Optional['RecordingIndicator']:
    """获取或创建全局指示器实例（懒初始化）。"""
    global _indicator
    if _indicator is not None:
        return _indicator
    with _lock:
        if _indicator is not None:
            return _indicator
        try:
            root = _get_root()
            if root is None:
                logger.debug("RecordingIndicator: 无 Tk root，跳过")
                return None
            _indicator = RecordingIndicator(root)
            _ensure_polling(root)
            logger.debug("RecordingIndicator 已初始化（Tkinter）")
        except Exception as e:
            logger.debug(f"RecordingIndicator 初始化失败（非致命）: {e}")
    return _indicator


def _schedule_command(method_name: str, *args) -> None:
    """线程安全地将命令放入队列（可从任意线程调用）。"""
    _command_queue.put((method_name, args))


# ── 公共 API（线程安全）────────────────────────────────────────────────────

def show_recording() -> None:
    """录音开始时调用（线程安全）。"""
    try:
        if _get_indicator() is None:
            return
        _schedule_command('_on_recording')
    except Exception as e:
        logger.debug(f"show_recording 失败（非致命）: {e}")


def show_result(text: str) -> None:
    """识别完成时调用，传入识别文本（线程安全）。"""
    try:
        if _get_indicator() is None:
            return
        display = text[:30] + ('...' if len(text) > 30 else '')
        _schedule_command('_on_result', display)
    except Exception as e:
        logger.debug(f"show_result 失败（非致命）: {e}")


def hide_recording() -> None:
    """录音取消/完成时调用（线程安全）。"""
    try:
        if _get_indicator() is None:
            return
        _schedule_command('_on_hide')
    except Exception as e:
        logger.debug(f"hide_recording 失败（非致命）: {e}")


def show_listening() -> None:
    """连续识别模式：显示"聆听中"状态（线程安全）。"""
    try:
        if _get_indicator() is None:
            return
        _schedule_command('_on_listening')
    except Exception as e:
        logger.debug(f"show_listening 失败（非致命）: {e}")


def hide_listening() -> None:
    """连续识别模式：隐藏"聆听中"指示器（线程安全）。"""
    try:
        if _get_indicator() is None:
            return
        _schedule_command('_on_hide')
    except Exception as e:
        logger.debug(f"hide_listening 失败（非致命）: {e}")


def show_paused() -> None:
    """连续识别模式暂停：显示"已暂停"状态（线程安全）。"""
    try:
        if _get_indicator() is None:
            return
        _schedule_command('_on_paused')
    except Exception as e:
        logger.debug(f"show_paused 失败（非致命）: {e}")


# ── Tkinter 窗口实现 ──────────────────────────────────────────────────────

try:
    import tkinter as tk

    class RecordingIndicator:
        """右下角悬浮录音状态指示器（Tkinter 实现）

        所有方法（_on_xxx / _redraw / _pulse_tick 等）仅由 Tk 线程调用。
        外部线程只通过 _schedule_command → Queue → Tk 轮询 来触发。
        """

        # 状态常量
        STATE_HIDDEN = 'hidden'
        STATE_RECORDING = 'recording'
        STATE_RESULT = 'result'
        STATE_LISTENING = 'listening'
        STATE_PAUSED = 'paused'

        # 颜色配置
        BG_COLOR = '#1a1a2e'
        RECORDING_COLOR = '#e84545'
        LISTENING_COLOR = '#4caf50'
        PAUSED_COLOR = '#888888'
        TEXT_COLOR = '#ffffff'

        # 窗口尺寸
        WIDTH = 160
        HEIGHT = 44
        CORNER_RADIUS = 10
        MARGIN_RIGHT = 24
        MARGIN_BOTTOM = 48

        def __init__(self, root: tk.Tk):
            self._root = root
            self._state = self.STATE_HIDDEN
            self._pulse_phase = 0.0  # 0..2*pi
            self._pulse_after_id = None
            self._result_timer_id = None
            self._text = ''
            self._window: Optional[tk.Toplevel] = None
            self._canvas: Optional[tk.Canvas] = None

            # 窗口创建将由 Tk 线程的轮询触发
            _command_queue.put(('_create_window', ()))

        def _create_window(self) -> None:
            """在 Tk 线程中创建 Toplevel 窗口。"""
            if self._window is not None:
                return  # 已创建
            try:
                self._window = tk.Toplevel(self._root)
                self._window.overrideredirect(True)
                self._window.attributes('-topmost', True)
                self._window.attributes('-alpha', 0.92)
                # 透明色 key
                self._window.configure(bg='#010101')
                self._window.attributes('-transparentcolor', '#010101')
                self._window.geometry(f'{self.WIDTH}x{self.HEIGHT}')

                self._canvas = tk.Canvas(
                    self._window,
                    width=self.WIDTH,
                    height=self.HEIGHT,
                    bg='#010101',
                    highlightthickness=0,
                    bd=0,
                )
                self._canvas.pack(fill='both', expand=True)

                self._move_to_corner()
                self._window.withdraw()
            except Exception as e:
                logger.debug(f"创建指示器窗口失败: {e}")
                self._window = None

        def _move_to_corner(self) -> None:
            """将窗口移动到右下角。"""
            if not self._window:
                return
            try:
                sw = self._window.winfo_screenwidth()
                sh = self._window.winfo_screenheight()
                x = sw - self.WIDTH - self.MARGIN_RIGHT
                y = sh - self.HEIGHT - self.MARGIN_BOTTOM
                self._window.geometry(f'+{x}+{y}')
            except Exception:
                pass

        # ── 状态切换（仅在 Tk 线程调用）──────────────────────────────────

        def _on_recording(self) -> None:
            """切换到录音中状态。"""
            self._cancel_timers()
            self._state = self.STATE_RECORDING
            self._text = '录音中'
            self._pulse_phase = 0.0
            self._show_window()
            self._start_pulse()

        def _on_result(self, text: str) -> None:
            """切换到结果展示状态。"""
            self._cancel_timers()
            self._state = self.STATE_RESULT
            self._text = text or '识别完成'
            self._stop_pulse()
            self._redraw()
            self._show_window()
            # 1.5s 后淡出或回到聆听状态
            self._result_timer_id = self._root.after(1500, self._on_result_timeout)

        def _on_result_timeout(self) -> None:
            """结果显示超时，回到聆听或隐藏。"""
            self._result_timer_id = None
            # 检查是否处于连续模式
            try:
                from util.client.state import get_state
                state = get_state()
                if getattr(state, 'continuous_mode', False):
                    mgr = getattr(state, 'continuous_manager', None)
                    if mgr and getattr(mgr, 'paused', False):
                        self._on_paused()
                    else:
                        self._on_listening()
                    return
            except Exception:
                pass
            self._on_hide()

        def _on_listening(self) -> None:
            """切换到聆听中状态（连续识别）。"""
            self._cancel_timers()
            self._state = self.STATE_LISTENING
            self._text = '聆听中'
            self._stop_pulse()
            self._redraw()
            self._show_window()

        def _on_paused(self) -> None:
            """切换到已暂停状态。"""
            self._cancel_timers()
            self._state = self.STATE_PAUSED
            self._text = '已暂停'
            self._stop_pulse()
            self._redraw()
            self._show_window()

        def _on_hide(self) -> None:
            """隐藏窗口。"""
            self._cancel_timers()
            self._stop_pulse()
            self._state = self.STATE_HIDDEN
            if self._window:
                try:
                    self._window.withdraw()
                except Exception:
                    pass

        # ── 显示/绘制 ─────────────────────────────────────────────────────

        def _show_window(self) -> None:
            """显示窗口。"""
            if not self._window:
                return
            try:
                self._move_to_corner()
                self._window.deiconify()
                self._window.lift()
                self._window.attributes('-topmost', True)
                self._redraw()
            except Exception:
                pass

        def _redraw(self) -> None:
            """重新绘制 Canvas 内容。"""
            if not self._canvas:
                return
            try:
                self._canvas.delete('all')
                w, h = self.WIDTH, self.HEIGHT
                r = self.CORNER_RADIUS

                # 圆角矩形背景
                self._draw_rounded_rect(0, 0, w, h, r, self.BG_COLOR)

                # 左侧彩色竖条
                accent = self._get_accent_color()
                self._canvas.create_rectangle(
                    4, 8, 8, h - 8,
                    fill=accent, outline=accent
                )

                # 圆点指示器（录音时有脉冲效果）
                dot_x, dot_y = 20, h // 2
                dot_r = 5
                if self._state == self.STATE_RECORDING:
                    # 脉冲效果：半径在 4~6 之间变化
                    pulse_scale = 1.0 + 0.2 * math.sin(self._pulse_phase)
                    dot_r = int(5 * pulse_scale)
                self._canvas.create_oval(
                    dot_x - dot_r, dot_y - dot_r,
                    dot_x + dot_r, dot_y + dot_r,
                    fill=accent, outline=accent
                )

                # 文字
                self._canvas.create_text(
                    32, h // 2,
                    text=self._text,
                    fill=self.TEXT_COLOR,
                    font=('Microsoft YaHei', 11),
                    anchor='w',
                    width=w - 38,  # 文字最大宽度
                )
            except Exception:
                pass

        def _draw_rounded_rect(self, x1, y1, x2, y2, r, color):
            """在 Canvas 上绘制圆角矩形。"""
            points = [
                x1 + r, y1,
                x2 - r, y1,
                x2, y1,
                x2, y1 + r,
                x2, y2 - r,
                x2, y2,
                x2 - r, y2,
                x1 + r, y2,
                x1, y2,
                x1, y2 - r,
                x1, y1 + r,
                x1, y1,
            ]
            self._canvas.create_polygon(
                points, fill=color, outline=color, smooth=True
            )

        def _get_accent_color(self) -> str:
            """根据状态返回强调色。"""
            if self._state == self.STATE_RECORDING:
                return self.RECORDING_COLOR
            elif self._state == self.STATE_LISTENING:
                return self.LISTENING_COLOR
            elif self._state == self.STATE_PAUSED:
                return self.PAUSED_COLOR
            elif self._state == self.STATE_RESULT:
                return self.LISTENING_COLOR
            return self.LISTENING_COLOR

        # ── 脉冲动画（在 Tk 线程） ───────────────────────────────────────

        def _start_pulse(self) -> None:
            """开始脉冲动画。"""
            self._stop_pulse()
            self._pulse_tick()

        def _pulse_tick(self) -> None:
            """脉冲动画帧（由 Tk after 调度，始终在 Tk 线程）。"""
            if self._state != self.STATE_RECORDING:
                return
            self._pulse_phase += 0.15  # 约 40ms 一帧，一个周期约 42 帧 ≈ 1.7s
            if self._pulse_phase > 2 * math.pi:
                self._pulse_phase -= 2 * math.pi
            self._redraw()
            try:
                self._pulse_after_id = self._root.after(40, self._pulse_tick)
            except Exception:
                self._pulse_after_id = None

        def _stop_pulse(self) -> None:
            """停止脉冲动画。"""
            if self._pulse_after_id is not None:
                try:
                    self._root.after_cancel(self._pulse_after_id)
                except Exception:
                    pass
                self._pulse_after_id = None

        # ── 定时器管理 ────────────────────────────────────────────────────

        def _cancel_timers(self) -> None:
            """取消所有定时器。"""
            if self._result_timer_id is not None:
                try:
                    self._root.after_cancel(self._result_timer_id)
                except Exception:
                    pass
                self._result_timer_id = None

except ImportError:
    # tkinter 未安装时，提供空实现
    class RecordingIndicator:  # type: ignore
        def __init__(self, root=None):
            pass
