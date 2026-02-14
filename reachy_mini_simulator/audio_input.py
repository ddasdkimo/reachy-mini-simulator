"""語音輸入管線 - 麥克風擷取 + 能量 VAD + OpenAI Whisper API STT。

從麥克風擷取音訊，透過能量偵測判斷說話段落，
再以 OpenAI Whisper API 進行語音轉文字，最後透過回呼函式傳出辨識結果。

依賴：
- numpy + sounddevice：麥克風擷取與 VAD（必要）
- openai：雲端 STT（必要，需 OPENAI_API_KEY）
"""

from __future__ import annotations

import io
import logging
import os
import queue
import struct
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
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore[assignment,misc]
    logger.warning("openai 未安裝，Whisper API 無法使用")

# ── 預設設定 ─────────────────────────────────────────────────
MIC_SAMPLE_RATE = 16000
MIC_CHANNELS = 1
MIC_BLOCK_SIZE = 512  # 每次回呼的 samples 數（~32ms @ 16kHz）
ENERGY_THRESHOLD = 0.015  # RMS 能量門檻（浮點 -1~1 範圍）
SILENCE_TIMEOUT = 1.2  # 靜音超過此秒數視為說話結束
MIN_SPEECH_DURATION = 0.4  # 最短語音段落秒數
WHISPER_LANGUAGE = "zh"


class AudioInput:
    """麥克風語音輸入管線：擷取 → 能量 VAD → OpenAI Whisper API → 文字回呼。

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
        energy_threshold: float = ENERGY_THRESHOLD,
        silence_timeout: float = SILENCE_TIMEOUT,
        min_speech_duration: float = MIN_SPEECH_DURATION,
        whisper_language: str = WHISPER_LANGUAGE,
        api_key: str | None = None,
    ) -> None:
        """初始化語音輸入管線。

        Args:
            on_transcript: 辨識到文字時的回呼函式，接收一個字串參數。
            sample_rate: 麥克風取樣率（Hz）。
            channels: 麥克風聲道數。
            block_size: 每次音訊回呼的樣本數。
            energy_threshold: RMS 能量門檻，高於此值視為有語音。
            silence_timeout: 靜音多久後視為說話結束（秒）。
            min_speech_duration: 最短語音段落長度（秒）。
            whisper_language: Whisper 辨識語言。
            api_key: OpenAI API 金鑰。若為 None 則從 OPENAI_API_KEY 讀取。
        """
        self.on_transcript = on_transcript

        # 音訊參數
        self._sample_rate = sample_rate
        self._channels = channels
        self._block_size = block_size

        # VAD 參數
        self._energy_threshold = energy_threshold
        self._silence_timeout = silence_timeout
        self._min_speech_duration = min_speech_duration

        # Whisper 參數
        self._whisper_language = whisper_language
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

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

        # OpenAI client（延遲初始化）
        self._client = None

        # 可用性
        self._available = all([
            np is not None,
            sd is not None,
            OpenAI is not None,
            bool(self._api_key),
        ])
        if not self._available:
            missing = []
            if np is None:
                missing.append("numpy")
            if sd is None:
                missing.append("sounddevice")
            if OpenAI is None:
                missing.append("openai")
            if not self._api_key:
                missing.append("OPENAI_API_KEY")
            logger.warning("語音輸入管線缺少: %s", ", ".join(missing))

    @property
    def available(self) -> bool:
        """是否所有必要依賴皆已安裝。"""
        return self._available

    def start(self) -> None:
        """啟動麥克風擷取與語音辨識。"""
        if not self._available:
            logger.warning("語音輸入管線缺少必要依賴，無法啟動")
            return

        # 若已在執行，先停止再重啟
        if self._vad_thread and self._vad_thread.is_alive():
            logger.warning("語音輸入管線已在執行中，先停止再重啟")
            self.stop()

        # 自動噪音校正
        self._calibrate_noise_floor()

        self._stop.clear()
        self._speech_active = False
        self._audio_buffer = []
        self._silence_start = 0.0
        self._vad_thread = threading.Thread(target=self._vad_loop, daemon=True)
        self._stt_thread = threading.Thread(target=self._stt_loop, daemon=True)
        self._vad_thread.start()
        self._stt_thread.start()
        logger.warning(
            "語音輸入管線已啟動（能量 VAD + OpenAI Whisper API, 門檻=%.4f）",
            self._energy_threshold,
        )

    def _calibrate_noise_floor(self) -> None:
        """錄製 1 秒環境音，自動設定 VAD 門檻為噪音底 × 3。"""
        rms_values: list[float] = []

        def _cal_callback(indata, frames, time_info, status):
            audio = indata[:, 0]
            rms_values.append(float(np.sqrt(np.mean(audio ** 2))))

        try:
            with sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=self._block_size,
                callback=_cal_callback,
            ):
                time.sleep(1.0)
        except Exception:
            logger.warning("噪音校正失敗，使用預設門檻")
            return

        if rms_values:
            noise_floor = float(np.mean(rms_values))
            new_threshold = max(noise_floor * 3.0, ENERGY_THRESHOLD)
            logger.warning(
                "噪音校正: 底噪=%.4f → 門檻=%.4f（原=%.4f）",
                noise_floor, new_threshold, self._energy_threshold,
            )
            self._energy_threshold = new_threshold

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
        """從麥克風擷取音訊並用能量偵測語音段落。"""

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
                logger.warning("麥克風串流已開啟")
                while not self._stop.is_set():
                    self._stop.wait(timeout=0.1)
        except Exception:
            logger.exception("麥克風錯誤")

    def _process_vad(self, audio) -> None:
        """對音訊區塊進行能量 VAD 處理。

        使用 RMS（均方根）能量判斷是否有語音活動。

        Args:
            audio: 單聲道浮點音訊陣列。
        """
        rms = float(np.sqrt(np.mean(audio ** 2)))
        is_speech = rms >= self._energy_threshold
        now = time.time()

        if is_speech:
            if not self._speech_active:
                self._speech_active = True
                self._speech_start = now
                self._audio_buffer = []
                logger.warning("偵測到語音開始 (RMS=%.4f)", rms)
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
                        logger.warning("語音段落: %.1f 秒", duration)
                    self._speech_active = False
                    self._audio_buffer = []
                    self._silence_start = 0.0

    # ── STT 迴圈 ─────────────────────────────────────────────

    def _stt_loop(self) -> None:
        """使用 OpenAI Whisper API 進行語音轉文字。"""
        logger.warning("STT 迴圈啟動（OpenAI Whisper API）")

        while not self._stop.is_set():
            try:
                audio = self._stt_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if audio is None:
                break

            try:
                text = self._transcribe(audio)
                if text:
                    logger.warning("STT 辨識結果: %s", text)
                    if self.on_transcript:
                        self.on_transcript(text)
            except Exception:
                logger.exception("STT 辨識錯誤")

    def _transcribe(self, audio) -> str:
        """將浮點音訊陣列轉為 WAV 並送到 OpenAI Whisper API。

        Args:
            audio: float32 numpy 陣列，取樣率為 self._sample_rate。

        Returns:
            辨識出的文字。
        """
        # 延遲初始化 OpenAI client
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key)

        # float32 → int16 PCM → WAV bytes
        wav_bytes = self._audio_to_wav(audio)

        transcript = self._client.audio.transcriptions.create(
            model="whisper-1",
            file=("recording.wav", wav_bytes),
            response_format="text",
            language=self._whisper_language,
        )
        return transcript.strip()

    def _audio_to_wav(self, audio) -> bytes:
        """將 float32 numpy 陣列轉換為 WAV 格式的 bytes。

        Args:
            audio: float32 numpy 陣列。

        Returns:
            WAV 格式的二進位資料。
        """
        # float32 [-1, 1] → int16
        int16_audio = (audio * 32767).astype(np.int16)
        pcm_bytes = int16_audio.tobytes()

        # 建構 WAV header
        buf = io.BytesIO()
        num_samples = len(int16_audio)
        data_size = num_samples * 2  # 16-bit = 2 bytes per sample
        # RIFF header
        buf.write(b"RIFF")
        buf.write(struct.pack("<I", 36 + data_size))
        buf.write(b"WAVE")
        # fmt chunk
        buf.write(b"fmt ")
        buf.write(struct.pack("<I", 16))  # chunk size
        buf.write(struct.pack("<H", 1))   # PCM format
        buf.write(struct.pack("<H", 1))   # mono
        buf.write(struct.pack("<I", self._sample_rate))
        buf.write(struct.pack("<I", self._sample_rate * 2))  # byte rate
        buf.write(struct.pack("<H", 2))   # block align
        buf.write(struct.pack("<H", 16))  # bits per sample
        # data chunk
        buf.write(b"data")
        buf.write(struct.pack("<I", data_size))
        buf.write(pcm_bytes)

        return buf.getvalue()
