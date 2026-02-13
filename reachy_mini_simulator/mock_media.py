"""MockMedia - 模擬 Reachy Mini 的相機與音訊介面。

提供與 reachy_mini.media 相同的介面，用於在沒有實體機器人的情況下進行開發與測試。
支援兩種影像來源模式：合成測試畫面（預設）或 webcam。
"""

from __future__ import annotations

import logging
import random
import time
from datetime import datetime

import numpy as np
import numpy.typing as npt

from .robot_interface import MediaInterface

logger = logging.getLogger(__name__)


class MockMedia(MediaInterface):
    """模擬 Reachy Mini 的 media 介面，提供相機畫面與音訊播放功能。"""

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        sample_rate: int = 16000,
        use_webcam: bool = False,
    ) -> None:
        self.width = width
        self.height = height
        self.sample_rate = sample_rate
        self.use_webcam = use_webcam

        self._is_playing = False
        self._total_audio_samples_pushed = 0
        self._cap = None  # webcam VideoCapture 物件

        # Phase 2A: 音檔播放
        self._sound_playing = False
        self._sound_file: str | None = None
        self._sound_start_time: float = 0.0
        self._sound_duration: float = 3.0  # 模擬播放時長

        # Phase 2B: 錄音
        self._is_recording = False
        self._recording_samples: list[npt.NDArray[np.float32]] = []
        self._recording_start_time: float = 0.0

        if self.use_webcam:
            self._init_webcam()

    def _init_webcam(self) -> None:
        try:
            import cv2
            self._cap = cv2.VideoCapture(0)
            if not self._cap.isOpened():
                logger.warning("無法開啟 webcam，回退到合成畫面模式")
                self._cap = None
                self.use_webcam = False
            else:
                logger.info("webcam 已開啟")
        except ImportError:
            logger.warning("未安裝 opencv-python，回退到合成畫面模式")
            self.use_webcam = False

    def get_frame(self) -> npt.NDArray[np.uint8]:
        if self.use_webcam and self._cap is not None:
            return self._read_webcam_frame()
        return self._generate_synthetic_frame()

    def _read_webcam_frame(self) -> npt.NDArray[np.uint8]:
        import cv2
        ret, frame = self._cap.read()
        if not ret or frame is None:
            logger.warning("webcam 讀取失敗，回退到合成畫面")
            return self._generate_synthetic_frame()
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))
        return frame

    def _generate_synthetic_frame(self) -> npt.NDArray[np.uint8]:
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        timestamp_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        try:
            import cv2
            cv2.putText(
                frame, timestamp_str,
                (self.width // 2 - 120, self.height // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2,
            )
            cv2.putText(
                frame, "MockMedia - Simulated Camera",
                (self.width // 2 - 180, self.height // 2 + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1,
            )
        except ImportError:
            cy, cx = self.height // 2, self.width // 2
            frame[cy - 2 : cy + 2, cx - 40 : cx + 40] = 255
        return frame

    def get_output_audio_samplerate(self) -> int:
        return self.sample_rate

    def start_playing(self) -> None:
        self._is_playing = True
        logger.info("MockMedia: 開始音訊播放")

    def stop_playing(self) -> None:
        self._is_playing = False
        logger.info(
            "MockMedia: 停止音訊播放（已推送 %d 個樣本）",
            self._total_audio_samples_pushed,
        )

    def push_audio_sample(self, samples: npt.NDArray[np.float32]) -> None:
        num_samples = len(samples)
        self._total_audio_samples_pushed += num_samples
        duration_ms = num_samples / self.sample_rate * 1000
        logger.debug(
            "MockMedia: 推送 %d 個音訊樣本（%.1f ms）",
            num_samples, duration_ms,
        )

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @property
    def total_audio_samples_pushed(self) -> int:
        return self._total_audio_samples_pushed

    # ── Phase 2A: 音檔播放 ────────────────────────────────────────────

    def play_sound(self, file_path: str) -> None:
        self._sound_playing = True
        self._sound_file = file_path
        self._sound_start_time = time.time()
        logger.info("MockMedia: 播放音檔 %s", file_path)

    def is_sound_playing(self) -> bool:
        if self._sound_playing:
            elapsed = time.time() - self._sound_start_time
            if elapsed >= self._sound_duration:
                self._sound_playing = False
        return self._sound_playing

    def stop_sound(self) -> None:
        self._sound_playing = False
        self._sound_file = None
        logger.info("MockMedia: 停止播放音檔")

    # ── Phase 2B: 錄音 + DoA ─────────────────────────────────────────

    def start_recording(self) -> None:
        self._is_recording = True
        self._recording_samples = []
        self._recording_start_time = time.time()
        logger.info("MockMedia: 開始錄音")

    def stop_recording(self) -> None:
        self._is_recording = False
        logger.info("MockMedia: 停止錄音")

    def get_audio_sample(self) -> npt.NDArray[np.float32] | None:
        if not self._is_recording:
            return None
        # 產生模擬靜音 + 小噪音的音訊樣本（100ms 等效）
        num_samples = self.sample_rate // 10
        samples = np.random.randn(num_samples).astype(np.float32) * 0.001
        return samples

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def get_doa(self) -> float:
        return random.uniform(0.0, 360.0)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("MockMedia: webcam 已釋放")
