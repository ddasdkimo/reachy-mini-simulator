"""語音輸入管線 - 麥克風擷取 + Silero VAD + faster-whisper STT。

從麥克風擷取音訊，透過 Silero VAD 偵測說話段落，
再以 faster-whisper 進行語音轉文字，最後透過回呼函式傳出辨識結果。

所有外部依賴（sounddevice, torch, faster-whisper）皆為 optional import，
未安裝時模組仍可被 import，但 start() 會記錄警告並跳過。
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)

# ── Optional imports ─────────────────────────────────────────
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore[assignment]
    logger.warning("numpy 未安裝，語音輸入管線無法使用")

try:
    import sounddevice as sd
except ImportError:
    sd = None  # type: ignore[assignment]
    logger.warning("sounddevice 未安裝，麥克風擷取無法使用")

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]
    logger.warning("torch 未安裝，Silero VAD 無法使用")

_faster_whisper_available = False
try:
    from faster_whisper import WhisperModel  # noqa: F401
    _faster_whisper_available = True
except ImportError:
    logger.warning("faster-whisper 未安裝，語音轉文字無法使用")

# ── 預設設定 ─────────────────────────────────────────────────
MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1
MIC_BLOCK_SIZE = 512  # 每次回呼的 samples 數（~32ms @ 16kHz）
VAD_THRESHOLD = 0.5
SILENCE_TIMEOUT = 1.0  # 靜音超過此秒數視為說話結束
MIN_SPEECH_DURATION = 0.3  # 最短語音段落秒數
WHISPER_MODEL_SIZE = "medium"
WHISPER_COMPUTE_TYPE = "int8"
WHISPER_LANGUAGE = "zh"
WHISPER_BEAM_SIZE = 5


class AudioInput:
    """麥克風語音輸入管線：擷取 → VAD → STT → 文字回呼。

    用法::

        def on_text(text: str) -> None:
            print(f"使用者說：{text}")

        audio = AudioInput(on_transcript=on_text)
        audio.start()
        # ...
        audio.stop()
    """

    def __init__(
        self,
        on_transcript: Callable[[str], None] | None = None,
        *,
        sample_rate: int = MIC_SAMPLE_RATE,
        channels: int = MIC_CHANNELS,
        block_size: int = MIC_BLOCK_SIZE,
        vad_threshold: float = VAD_THRESHOLD,
        silence_timeout: float = SILENCE_TIMEOUT,
        min_speech_duration: float = MIN_SPEECH_DURATION,
        whisper_model_size: str = WHISPER_MODEL_SIZE,
        whisper_compute_type: str = WHISPER_COMPUTE_TYPE,
        whisper_language: str = WHISPER_LANGUAGE,
        whisper_beam_size: int = WHISPER_BEAM_SIZE,
    ) -> None:
        """初始化語音輸入管線。

        Args:
            on_transcript: 辨識到文字時的回呼函式，接收一個字串參數。
            sample_rate: 麥克風取樣率（Hz）。
            channels: 麥克風聲道數。
            block_size: 每次音訊回呼的樣本數。
            vad_threshold: VAD 語音偵測門檻（0~1）。
            silence_timeout: 靜音多久後視為說話結束（秒）。
            min_speech_duration: 最短語音段落長度（秒）。
            whisper_model_size: Whisper 模型大小。
            whisper_compute_type: Whisper 計算精度。
            whisper_language: Whisper 辨識語言。
            whisper_beam_size: Whisper beam search 大小。
        """
        self.on_transcript = on_transcript

        # 音訊參數
        self._sample_rate = sample_rate
        self._channels = channels
        self._block_size = block_size

        # VAD 參數
        self._vad_threshold = vad_threshold
        self._silence_timeout = silence_timeout
        self._min_speech_duration = min_speech_duration

        # Whisper 參數
        self._whisper_model_size = whisper_model_size
        self._whisper_compute_type = whisper_compute_type
        self._whisper_language = whisper_language
        self._whisper_beam_size = whisper_beam_size

        # 內部佇列與執行緒
        self._stt_queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._vad_thread: threading.Thread | None = None
        self._stt_thread: threading.Thread | None = None

        # VAD 狀態
        self._audio_buffer: list = []
        self._speech_active = False
        self._silence_start = 0.0
        self._speech_start = 0.0

        # 暫停旗標（TTS 播放時暫停以避免迴聲）
        self.paused = False

        # VAD 模型（延遲載入）
        self._vad_model = None

        # Whisper 模型（延遲載入）
        self._whisper_model = None

        # 可用性
        self._available = all([np is not None, sd is not None, torch is not None])
        if not self._available:
            logger.warning("語音輸入管線缺少必要依賴，start() 將不會啟動")

    @property
    def available(self) -> bool:
        """是否所有必要依賴皆已安裝。"""
        return self._available

    def start(self) -> None:
        """啟動麥克風擷取與語音辨識。"""
        if not self._available:
            logger.warning("語音輸入管線缺少必要依賴，無法啟動")
            return

        # 載入 VAD 模型
        if self._vad_model is None:
            try:
                logger.info("載入 Silero VAD 模型...")
                self._vad_model, _ = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    trust_repo=True,
                )
                self._vad_model.eval()
                logger.info("Silero VAD 模型載入完成")
            except Exception:
                logger.exception("Silero VAD 模型載入失敗")
                return

        self._stop.clear()
        self._vad_thread = threading.Thread(target=self._vad_loop, daemon=True)
        self._stt_thread = threading.Thread(target=self._stt_loop, daemon=True)
        self._vad_thread.start()
        self._stt_thread.start()
        logger.info("語音輸入管線已啟動")

    def stop(self) -> None:
        """停止麥克風擷取與語音辨識。"""
        self._stop.set()
        self._stt_queue.put(None)
        if self._vad_thread:
            self._vad_thread.join(timeout=5)
        if self._stt_thread:
            self._stt_thread.join(timeout=5)
        logger.info("語音輸入管線已停止")

    # ── VAD 迴圈 ─────────────────────────────────────────────

    def _vad_loop(self) -> None:
        """從麥克風擷取音訊並偵測語音段落。"""

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning("音訊狀態: %s", status)
            if not self.paused:
                audio = indata[:, 0].copy()
                self._process_vad(audio)

        try:
            with sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=self._block_size,
                callback=audio_callback,
            ):
                logger.info("麥克風串流已開啟")
                while not self._stop.is_set():
                    self._stop.wait(timeout=0.1)
        except Exception:
            logger.exception("麥克風錯誤")

    def _process_vad(self, audio) -> None:
        """對音訊區塊進行 VAD 處理。

        Args:
            audio: 單聲道浮點音訊陣列。
        """
        tensor = torch.from_numpy(audio)

        try:
            speech_prob = self._vad_model(tensor, self._sample_rate).item()
        except Exception:
            return

        now = time.time()

        if speech_prob >= self._vad_threshold:
            if not self._speech_active:
                self._speech_active = True
                self._speech_start = now
                self._audio_buffer = []
                logger.debug("偵測到語音開始")
            self._silence_start = 0.0
            self._audio_buffer.append(audio)
        else:
            if self._speech_active:
                self._audio_buffer.append(audio)
                if self._silence_start == 0.0:
                    self._silence_start = now
                elif now - self._silence_start >= self._silence_timeout:
                    # 語音結束
                    duration = now - self._speech_start
                    if duration >= self._min_speech_duration:
                        full_audio = np.concatenate(self._audio_buffer)
                        self._stt_queue.put(full_audio)
                        logger.info("語音段落: %.1f 秒", duration)
                    self._speech_active = False
                    self._audio_buffer = []
                    self._silence_start = 0.0

    # ── STT 迴圈 ─────────────────────────────────────────────

    def _stt_loop(self) -> None:
        """使用 faster-whisper 進行語音轉文字。"""
        if not _faster_whisper_available:
            logger.warning("faster-whisper 未安裝，STT 迴圈結束")
            return

        from faster_whisper import WhisperModel

        logger.info("載入 Whisper 模型: %s", self._whisper_model_size)
        self._whisper_model = WhisperModel(
            self._whisper_model_size,
            compute_type=self._whisper_compute_type,
        )
        logger.info("Whisper 模型載入完成")

        while not self._stop.is_set():
            try:
                audio = self._stt_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if audio is None:
                break

            try:
                segments, _info = self._whisper_model.transcribe(
                    audio,
                    language=self._whisper_language,
                    beam_size=self._whisper_beam_size,
                    vad_filter=True,
                )
                text = "".join(seg.text for seg in segments).strip()
                if text:
                    logger.info("STT 辨識結果: %s", text)
                    if self.on_transcript:
                        self.on_transcript(text)
            except Exception:
                logger.exception("STT 辨識錯誤")
