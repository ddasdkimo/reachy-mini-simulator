"""MockMedia - 模擬 Reachy Mini 的相機與音訊介面。

提供與 reachy_mini.media 相同的介面，用於在沒有實體機器人的情況下進行開發與測試。
支援兩種影像來源模式：合成測試畫面（預設）或 webcam。
"""

import logging
import time
from datetime import datetime

import numpy as np
import numpy.typing as npt

from .robot_interface import MediaInterface

logger = logging.getLogger(__name__)


class MockMedia(MediaInterface):
    """模擬 Reachy Mini 的 media 介面，提供相機畫面與音訊播放功能。

    Attributes:
        width: 影像寬度（像素）。
        height: 影像高度（像素）。
        sample_rate: 音訊取樣率（Hz）。
        use_webcam: 是否使用 webcam 作為影像來源。
    """

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        sample_rate: int = 16000,
        use_webcam: bool = False,
    ) -> None:
        """初始化 MockMedia。

        Args:
            width: 影像寬度（像素），預設 640。
            height: 影像高度（像素），預設 480。
            sample_rate: 音訊取樣率（Hz），預設 16000。
            use_webcam: 若為 True 則嘗試使用 webcam，否則產生合成測試畫面。
        """
        self.width = width
        self.height = height
        self.sample_rate = sample_rate
        self.use_webcam = use_webcam

        self._is_playing = False
        self._total_audio_samples_pushed = 0
        self._cap = None  # webcam VideoCapture 物件

        if self.use_webcam:
            self._init_webcam()

    def _init_webcam(self) -> None:
        """嘗試開啟 webcam。若失敗則回退到合成畫面模式。"""
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
        """取得一幀影像。

        若使用 webcam 模式，回傳 webcam 的畫面；
        否則回傳黑底帶時間戳的合成測試畫面。

        Returns:
            形狀為 (height, width, 3) 的 uint8 numpy 陣列（BGR 格式）。
        """
        if self.use_webcam and self._cap is not None:
            return self._read_webcam_frame()
        return self._generate_synthetic_frame()

    def _read_webcam_frame(self) -> npt.NDArray[np.uint8]:
        """從 webcam 讀取一幀影像。若失敗則回退到合成畫面。"""
        import cv2

        ret, frame = self._cap.read()
        if not ret or frame is None:
            logger.warning("webcam 讀取失敗，回退到合成畫面")
            return self._generate_synthetic_frame()
        # 統一尺寸
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))
        return frame

    def _generate_synthetic_frame(self) -> npt.NDArray[np.uint8]:
        """產生黑底加時間戳文字的合成測試畫面。"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)

        timestamp_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        try:
            import cv2

            # 主時間戳
            cv2.putText(
                frame,
                timestamp_str,
                (self.width // 2 - 120, self.height // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )
            # 標示文字
            cv2.putText(
                frame,
                "MockMedia - Simulated Camera",
                (self.width // 2 - 180, self.height // 2 + 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (128, 128, 128),
                1,
            )
        except ImportError:
            # 沒有 cv2 時，用簡易方式在畫面中央畫白色像素標記
            cy, cx = self.height // 2, self.width // 2
            frame[cy - 2 : cy + 2, cx - 40 : cx + 40] = 255

        return frame

    def get_output_audio_samplerate(self) -> int:
        """取得音訊輸出的取樣率。

        Returns:
            取樣率（Hz），預設為 16000。
        """
        return self.sample_rate

    def start_playing(self) -> None:
        """開始音訊播放。記錄播放狀態。"""
        self._is_playing = True
        logger.info("MockMedia: 開始音訊播放")

    def stop_playing(self) -> None:
        """停止音訊播放。記錄播放狀態。"""
        self._is_playing = False
        logger.info(
            "MockMedia: 停止音訊播放（已推送 %d 個樣本）",
            self._total_audio_samples_pushed,
        )

    def push_audio_sample(self, samples: npt.NDArray[np.float32]) -> None:
        """推送音訊樣本到播放緩衝區。

        實際上只記錄樣本數量，不進行真正的音訊播放。

        Args:
            samples: float32 格式的音訊樣本陣列。
        """
        num_samples = len(samples)
        self._total_audio_samples_pushed += num_samples
        duration_ms = num_samples / self.sample_rate * 1000
        logger.debug(
            "MockMedia: 推送 %d 個音訊樣本（%.1f ms）",
            num_samples,
            duration_ms,
        )

    @property
    def is_playing(self) -> bool:
        """是否正在播放音訊。"""
        return self._is_playing

    @property
    def total_audio_samples_pushed(self) -> int:
        """已推送的音訊樣本總數。"""
        return self._total_audio_samples_pushed

    def close(self) -> None:
        """釋放資源（webcam 等）。"""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("MockMedia: webcam 已釋放")
