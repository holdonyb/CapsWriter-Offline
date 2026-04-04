# coding: utf-8
"""
连续识别管理器

在连续识别模式下，使用 VAD 自动检测语音段落，
自动触发录音→识别→输出流程，无需按住热键。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Optional

from util.client.audio.vad import EnergyVAD, VADEvent

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from util.client.state import ClientState


class ContinuousRecognitionManager:
    """
    连续识别管理器

    由音频回调调用 feed_audio()，运行 VAD 检测语音起止，
    自动往 queue_in 发 begin/data/finish 消息。

    与热键模式共存：
    - 热键录音期间 VAD 暂停（通过检查 state.recording）
    - 热键释放后 VAD 自动恢复
    """

    def __init__(
        self,
        state: 'ClientState',
        energy_threshold: float = 0.015,
        silence_duration: float = 1.5,
        min_speech_duration: float = 0.3,
    ):
        self.state = state
        self.vad = EnergyVAD(
            energy_threshold=energy_threshold,
            silence_duration=silence_duration,
            min_speech_duration=min_speech_duration,
        )

        self.paused = False
        self._active = False  # 当前是否正在由连续模式驱动的录音
        self._recording_start_time = 0.0

    def feed_audio(self, indata, timestamp: float) -> None:
        """
        由音频回调调用，传入一帧音频数据。

        注意：此函数在音频回调线程中执行，必须非阻塞。

        Args:
            indata: numpy array，音频帧数据
            timestamp: 当前时间戳
        """
        # 热键录音期间跳过 VAD（让热键优先）
        if self.state.recording and not self._active:
            self.vad.reset()
            return

        # 暂停时只检测恢复命令（由 result_processor 处理），不执行 VAD
        if self.paused:
            return

        event = self.vad.process(indata)

        if event == VADEvent.SPEECH_START:
            self._on_speech_start(indata, timestamp)
        elif event == VADEvent.SPEECH_CONTINUE:
            self._on_speech_continue(indata, timestamp)
        elif event == VADEvent.SPEECH_END:
            self._on_speech_end(timestamp)

    def _on_speech_start(self, indata, timestamp: float) -> None:
        """VAD 检测到语音开始。"""
        if self._active:
            return  # 防重入

        self._active = True
        self._recording_start_time = timestamp
        self.state.recording = True
        self.state.recording_start_time = timestamp

        logger.info("连续识别：语音开始")

        # 发送 begin 到队列
        self._put_queue({'type': 'begin', 'time': timestamp, 'data': None})

        # 发送当前帧数据（这是第一帧语音数据）
        self._put_queue({'type': 'data', 'time': timestamp, 'data': indata.copy()})

        # 显示录音指示器
        try:
            from util.client.ui.recording_indicator import show_recording
            show_recording()
        except Exception:
            pass

    def _on_speech_continue(self, indata, timestamp: float) -> None:
        """VAD 检测到语音持续。"""
        if not self._active:
            return
        self._put_queue({'type': 'data', 'time': timestamp, 'data': indata.copy()})

    def _on_speech_end(self, timestamp: float) -> None:
        """VAD 检测到语音结束。"""
        if not self._active:
            return

        logger.info("连续识别：语音结束")

        # 发送 finish 到队列
        self._put_queue({'type': 'finish', 'time': timestamp, 'data': None})

        self._active = False
        self.state.recording = False
        self.state.recording_start_time = 0.0

        # 指示器切回"聆听中"
        try:
            from util.client.ui.recording_indicator import show_listening
            show_listening()
        except Exception:
            pass

    def _put_queue(self, item: dict) -> None:
        """线程安全地将数据放入 asyncio 队列。"""
        if self.state.loop and self.state.queue_in:
            asyncio.run_coroutine_threadsafe(
                self.state.queue_in.put(item),
                self.state.loop
            )

    def toggle(self) -> bool:
        """
        切换连续识别模式。

        Returns:
            切换后的连续模式状态（True=开启，False=关闭）
        """
        from util.client.state import get_state
        state = get_state()

        if state.continuous_mode:
            # 关闭
            self.stop()
            return False
        else:
            # 开启
            self.start()
            return True

    def start(self) -> None:
        """开启连续识别模式。"""
        from util.client.state import get_state, console
        state = get_state()
        state.continuous_mode = True
        self.paused = False
        self.vad.reset()
        self._active = False

        console.print('[bold green]连续识别模式已开启[/bold green]')
        logger.info("连续识别模式已开启")

        # 显示聆听指示器
        try:
            from util.client.ui.recording_indicator import show_listening
            show_listening()
        except Exception:
            pass

    def stop(self) -> None:
        """关闭连续识别模式。"""
        from util.client.state import get_state, console
        state = get_state()

        # 如果当前正在连续模式录音，先结束
        if self._active:
            self._on_speech_end(time.time())

        state.continuous_mode = False
        self.paused = False
        self.vad.reset()
        self._active = False

        console.print('[bold yellow]连续识别模式已关闭[/bold yellow]')
        logger.info("连续识别模式已关闭")

        # 隐藏指示器
        try:
            from util.client.ui.recording_indicator import hide_listening
            hide_listening()
        except Exception:
            pass

    def pause(self) -> None:
        """暂停连续识别（仍监听恢复命令）。"""
        from util.client.state import console

        # 如果当前正在录音，先结束当前段
        if self._active:
            self._on_speech_end(time.time())

        self.paused = True
        self.vad.reset()

        console.print('[yellow]连续识别已暂停[/yellow]')
        logger.info("连续识别已暂停")

        try:
            from util.client.ui.recording_indicator import show_paused
            show_paused()
        except Exception:
            pass

    def resume(self) -> None:
        """恢复连续识别。"""
        from util.client.state import console

        self.paused = False
        self.vad.reset()

        console.print('[green]连续识别已恢复[/green]')
        logger.info("连续识别已恢复")

        try:
            from util.client.ui.recording_indicator import show_listening
            show_listening()
        except Exception:
            pass
