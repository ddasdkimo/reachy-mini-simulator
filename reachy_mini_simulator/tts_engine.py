"""語音輸出引擎 - 透過 OpenAI TTS API 將文字轉為語音並播放。

支援兩種播放模式：
1. sounddevice 直接播放（預設，robot=None）
2. 透過 RobotInterface.media 推送到機器人喇叭（robot 不為 None）

所有外部依賴（openai, sounddevice, numpy）皆為 optional import，
未安裝或無 API key 時優雅降級為僅記錄文字。
"""

from __future__ import annotations

import logging
import os
import queue
import threading
from typing import Callable

logger = logging.getLogger(__name__)

# ── Optional imports ─────────────────────────────────────────
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]
    logger.warning("numpy 未安裝，TTS 音訊處理無法使用")

try:
    import sounddevice as sd
except ImportError:
    sd = None  # type: ignore[assignment]
    logger.warning("sounddevice 未安裝，TTS 直接播放無法使用")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    logger.warning("openai 未安裝，TTS 引擎無法使用")

# ── 預設設定 ─────────────────────────────────────────────────
TTS_MODEL = "tts-1"
TTS_VOICE = "nova"
TTS_SPEED = 1.0
TTS_SAMPLE_RATE = 24000  # OpenAI PCM 輸出取樣率
DEFAULT_OUTPUT_SAMPLE_RATE = 24000


class TTSEngine:
    """文字轉語音引擎，使用 OpenAI TTS API。

    在背景執行緒中處理語音合成與播放，不會阻塞主迴圈。
    沒有 OPENAI_API_KEY 或缺少依賴時優雅降級為僅記錄文字。

    用法::

        tts = TTSEngine()
        tts.start()
        tts.speak("你好呀！")
        # ...
        tts.stop()
    """

    def __init__(
        self,
        robot=None,
        api_key: str | None = None,
        *,
        model: str = TTS_MODEL,
        voice: str = TTS_VOICE,
        speed: float = TTS_SPEED,
        output_sample_rate: int = DEFAULT_OUTPUT_SAMPLE_RATE,
        on_speak_start: Callable[[], None] | None = None,
        on_speak_end: Callable[[], None] | None = None,
    ) -> None:
        """初始化 TTS 引擎。

        Args:
            robot: RobotInterface 實例。不為 None 時透過機器人喇叭播放，
                   為 None 時使用 sounddevice 直接播放。
            api_key: OpenAI API 金鑰。若為 None 則從環境變數
                     OPENAI_API_KEY 讀取。
            model: OpenAI TTS 模型名稱。
            voice: TTS 語音選項。
            speed: 語音速度倍率。
            output_sample_rate: 輸出音訊取樣率（Hz）。
            on_speak_start: 開始播放語音時的回呼。
            on_speak_end: 播放語音結束時的回呼。
        """
        self._robot = robot
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._voice = voice
        self._speed = speed
        self._output_sample_rate = output_sample_rate

        # 若有 robot，從 SDK 取得實際 sample rate
        self._robot_sample_rate: int = output_sample_rate
        if robot is not None:
            try:
                self._robot_sample_rate = robot.media.get_output_audio_samplerate()
            except Exception:
                logger.warning("無法從 robot.media 取得取樣率，使用預設 %d", output_sample_rate)
                self._robot_sample_rate = output_sample_rate

        # OpenAI client（延遲初始化）
        self._client = None

        # 佇列與執行緒
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        # 回呼
        self.on_speak_start: Callable[[], None] | None = on_speak_start
        """開始播放語音時的回呼。"""

        self.on_speak_end: Callable[[], None] | None = on_speak_end
        """播放語音結束時的回呼。"""

        # 可用性判斷
        self._api_available = bool(self._api_key) and OpenAI is not None
        if not self._api_available:
            if not self._api_key:
                logger.info("TTSEngine: 無 OPENAI_API_KEY，降級為文字記錄模式")
            elif OpenAI is None:
                logger.info("TTSEngine: openai 套件未安裝，降級為文字記錄模式")

    @property
    def available(self) -> bool:
        """TTS API 是否可用。"""
        return self._api_available

    def start(self) -> None:
        """啟動背景 TTS 處理執行緒。"""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("TTSEngine 已啟動")

    def stop(self) -> None:
        """停止背景 TTS 處理執行緒。"""
        self._stop.set()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("TTSEngine 已停止")

    def speak(self, text: str) -> None:
        """將文字加入語音合成佇列。

        Args:
            text: 要朗讀的文字。空白文字會被忽略。
        """
        text = text.strip()
        if text:
            self._queue.put(text)

    # ── 背景執行緒 ───────────────────────────────────────────

    def _run(self) -> None:
        """背景執行緒主迴圈。"""
        while not self._stop.is_set():
            try:
                text = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if text is None:
                break

            try:
                self._process(text)
            except Exception:
                logger.exception("TTS 處理錯誤")

    def _process(self, text: str) -> None:
        """處理單筆文字轉語音。

        Args:
            text: 要合成並播放的文字。
        """
        if not self._api_available:
            logger.info("TTS (文字記錄): %s", text)
            return

        if self.on_speak_start:
            self.on_speak_start()

        try:
            self._synthesize_and_play(text)
        finally:
            if self.on_speak_end:
                self.on_speak_end()

    def _synthesize_and_play(self, text: str) -> None:
        """呼叫 OpenAI TTS API 並播放音訊。

        根據 robot 參數決定播放方式：
        - robot 不為 None：重新取樣後透過 robot.media 推送到機器人喇叭
        - robot 為 None：透過 sounddevice 直接播放

        Args:
            text: 要合成的文字。
        """
        # 延遲初始化 OpenAI client
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key)

        response = self._client.audio.speech.create(
            model=self._model,
            voice=self._voice,
            input=text,
            response_format="pcm",
            speed=self._speed,
        )

        # PCM 資料：24kHz, 16-bit signed, mono
        pcm_bytes = response.read()
        samples_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        samples_float = samples_int16.astype(np.float32) / 32768.0

        if self._robot is not None:
            # ── Real 模式：推送到機器人喇叭 ──
            # 重新取樣至機器人 sample rate
            resampled = self._resample(
                samples_float, TTS_SAMPLE_RATE, self._robot_sample_rate
            )
            chunk_size = self._robot_sample_rate // 10  # 100ms per chunk
            self._robot.media.start_playing()
            try:
                for i in range(0, len(resampled), chunk_size):
                    chunk = resampled[i : i + chunk_size].astype(np.float32)
                    self._robot.media.push_audio_sample(chunk)
            finally:
                self._robot.media.stop_playing()
        else:
            # ── Mock 模式：用 sounddevice 播放 ──
            # 若需要重新取樣
            if TTS_SAMPLE_RATE != self._output_sample_rate:
                samples_float = self._resample(
                    samples_float, TTS_SAMPLE_RATE, self._output_sample_rate
                )
            self._play_audio(samples_float)

    def _play_audio(self, samples) -> None:
        """透過 sounddevice 播放音訊。

        Args:
            samples: 浮點音訊陣列。
        """
        if sd is None:
            logger.warning("sounddevice 未安裝，無法播放音訊")
            return

        try:
            sd.play(samples, samplerate=self._output_sample_rate)
            sd.wait()
        except Exception:
            logger.exception("音訊播放錯誤")

    @staticmethod
    def _resample(samples, from_rate: int, to_rate: int):
        """重新取樣音訊。

        Args:
            samples: 浮點音訊陣列。
            from_rate: 原始取樣率。
            to_rate: 目標取樣率。

        Returns:
            重新取樣後的浮點音訊陣列。
        """
        if from_rate == to_rate:
            return samples

        try:
            from math import gcd
            from scipy.signal import resample_poly

            g = gcd(to_rate, from_rate)
            return resample_poly(samples, to_rate // g, from_rate // g).astype(
                np.float32
            )
        except ImportError:
            # scipy 不可用，用簡易線性插值
            logger.warning("scipy 未安裝，使用簡易重新取樣")
            ratio = to_rate / from_rate
            new_length = int(len(samples) * ratio)
            indices = np.linspace(0, len(samples) - 1, new_length)
            return np.interp(indices, np.arange(len(samples)), samples).astype(
                np.float32
            )
