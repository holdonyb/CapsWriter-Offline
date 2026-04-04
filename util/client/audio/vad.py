# coding: utf-8
"""
基于能量的语音活动检测 (VAD)

使用 RMS 能量检测语音起止，无额外依赖。
状态机：SILENCE -> SPEECH -> TRAILING_SILENCE -> SILENCE
"""

from __future__ import annotations

import enum
import logging
import math
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class VADEvent(enum.Enum):
    """VAD 检测事件"""
    NONE = 'none'
    SPEECH_START = 'speech_start'
    SPEECH_CONTINUE = 'speech_continue'
    SPEECH_END = 'speech_end'


class VADState(enum.Enum):
    """VAD 内部状态"""
    SILENCE = 'silence'
    PENDING_SPEECH = 'pending_speech'  # 疑似语音，等待确认
    SPEECH = 'speech'
    TRAILING_SILENCE = 'trailing_silence'  # 语音后的拖尾静音


class EnergyVAD:
    """
    基于 RMS 能量的语音活动检测器

    每帧（通常 50ms）调用 process() 传入音频数据，
    返回 VADEvent 表示当前帧的语音状态变化。

    Args:
        energy_threshold: RMS 能量阈值，高于此值视为语音
        silence_duration: 语音结束后静音多久判定段结束（秒）
        min_speech_duration: 最短语音持续时长（秒），防止噪音误触
        frame_duration: 每帧时长（秒），应与音频回调一致
    """

    def __init__(
        self,
        energy_threshold: float = 0.015,
        silence_duration: float = 1.5,
        min_speech_duration: float = 0.3,
        frame_duration: float = 0.05,
    ):
        self.energy_threshold = energy_threshold
        self.silence_duration = silence_duration
        self.min_speech_duration = min_speech_duration
        self.frame_duration = frame_duration

        # 内部状态
        self._state = VADState.SILENCE
        self._speech_frames = 0  # 连续语音帧计数
        self._silence_frames = 0  # 连续静音帧计数

        # 预计算帧数阈值
        self._min_speech_frames = max(1, int(min_speech_duration / frame_duration))
        self._silence_frames_threshold = max(1, int(silence_duration / frame_duration))

    @staticmethod
    def compute_rms(audio: np.ndarray) -> float:
        """计算音频帧的 RMS 能量。"""
        if audio.size == 0:
            return 0.0
        # 处理多声道：取平均
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return float(np.sqrt(np.mean(audio ** 2)))

    def process(self, audio_frame: np.ndarray) -> VADEvent:
        """
        处理一帧音频数据，返回 VAD 事件。

        Args:
            audio_frame: 音频数据 (float32 numpy array)

        Returns:
            VADEvent 枚举值
        """
        rms = self.compute_rms(audio_frame)
        is_speech = rms >= self.energy_threshold

        if self._state == VADState.SILENCE:
            if is_speech:
                self._state = VADState.PENDING_SPEECH
                self._speech_frames = 1
            return VADEvent.NONE

        elif self._state == VADState.PENDING_SPEECH:
            if is_speech:
                self._speech_frames += 1
                if self._speech_frames >= self._min_speech_frames:
                    # 确认为语音
                    self._state = VADState.SPEECH
                    self._silence_frames = 0
                    return VADEvent.SPEECH_START
            else:
                # 误触，回到静音
                self._state = VADState.SILENCE
                self._speech_frames = 0
            return VADEvent.NONE

        elif self._state == VADState.SPEECH:
            if is_speech:
                self._silence_frames = 0
                return VADEvent.SPEECH_CONTINUE
            else:
                # 开始拖尾静音
                self._state = VADState.TRAILING_SILENCE
                self._silence_frames = 1
                return VADEvent.SPEECH_CONTINUE

        elif self._state == VADState.TRAILING_SILENCE:
            if is_speech:
                # 恢复语音
                self._state = VADState.SPEECH
                self._silence_frames = 0
                return VADEvent.SPEECH_CONTINUE
            else:
                self._silence_frames += 1
                if self._silence_frames >= self._silence_frames_threshold:
                    # 确认语音结束
                    self._state = VADState.SILENCE
                    self._speech_frames = 0
                    self._silence_frames = 0
                    return VADEvent.SPEECH_END
                return VADEvent.SPEECH_CONTINUE

        return VADEvent.NONE

    def reset(self) -> None:
        """重置 VAD 状态。"""
        self._state = VADState.SILENCE
        self._speech_frames = 0
        self._silence_frames = 0

    @property
    def is_speech(self) -> bool:
        """当前是否在语音中。"""
        return self._state in (VADState.SPEECH, VADState.TRAILING_SILENCE, VADState.PENDING_SPEECH)
