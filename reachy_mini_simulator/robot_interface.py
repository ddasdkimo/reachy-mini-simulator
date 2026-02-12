"""RobotInterface / MediaInterface - 機器人與媒體抽象基底類別。

定義 Reachy Mini 機器人的統一介面，讓模擬器（MockReachyMini）和
真實機器人（RealReachyMini）都遵循相同的介面規範。
"""

from abc import ABC, abstractmethod

import numpy as np
import numpy.typing as npt


class MediaInterface(ABC):
    """媒體介面抽象基底類別。

    定義相機影像擷取與音訊播放的統一介面，
    供 MockMedia 和真實 SDK media 實作。
    """

    @abstractmethod
    def get_frame(self) -> npt.NDArray[np.uint8]:
        """取得一幀影像。

        Returns:
            形狀為 (height, width, 3) 的 uint8 numpy 陣列（BGR 格式）。
        """

    @abstractmethod
    def get_output_audio_samplerate(self) -> int:
        """取得音訊輸出的取樣率。

        Returns:
            取樣率（Hz）。
        """

    @abstractmethod
    def start_playing(self) -> None:
        """開始音訊播放。"""

    @abstractmethod
    def stop_playing(self) -> None:
        """停止音訊播放。"""

    @abstractmethod
    def push_audio_sample(self, samples: npt.NDArray[np.float32]) -> None:
        """推送音訊樣本到播放緩衝區。

        Args:
            samples: float32 格式的音訊樣本陣列。
        """

    @property
    @abstractmethod
    def is_playing(self) -> bool:
        """是否正在播放音訊。"""

    @abstractmethod
    def close(self) -> None:
        """釋放資源。"""


class RobotInterface(ABC):
    """機器人介面抽象基底類別。

    定義 Reachy Mini 機器人的統一操控介面，包含頭部姿態、天線角度、
    身體旋轉、底盤移動、以及媒體存取。
    """

    @abstractmethod
    def set_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: npt.NDArray[np.float64] | list[float] | None = None,
        body_yaw: float | None = None,
    ) -> None:
        """設定機器人各部位的目標姿態。

        所有參數皆為可選，至少需提供一個。

        Args:
            head: 4x4 齊次轉換矩陣，表示頭部目標姿態。
            antennas: 長度為 2 的陣列 [right, left]，天線目標角度（弧度）。
            body_yaw: 身體偏轉目標角度（弧度）。
        """

    @abstractmethod
    def move_to(self, x: float, y: float) -> None:
        """設定底盤移動目標座標。

        Args:
            x: 目標 x 座標（公尺）。
            y: 目標 y 座標（公尺）。
        """

    @abstractmethod
    def update_position(self, dt: float) -> bool:
        """更新底盤位置。

        Args:
            dt: 時間差（秒）。

        Returns:
            True 表示仍在移動中，False 表示已到達或無目標。
        """

    @property
    @abstractmethod
    def is_moving(self) -> bool:
        """機器人是否正在移動中。"""

    @property
    @abstractmethod
    def position(self) -> tuple[float, float]:
        """機器人在 2D 地圖上的座標 (x, y)。"""

    @position.setter
    @abstractmethod
    def position(self, value: tuple[float, float]) -> None: ...

    @property
    @abstractmethod
    def heading(self) -> float:
        """機器人朝向角度，單位為度。"""

    @heading.setter
    @abstractmethod
    def heading(self, value: float) -> None: ...

    @property
    @abstractmethod
    def media(self) -> MediaInterface:
        """取得媒體介面實例。"""

    @property
    @abstractmethod
    def antenna_pos(self) -> list[float]:
        """當前天線角度 [right, left]，單位為弧度。"""

    @property
    @abstractmethod
    def head_pose(self) -> npt.NDArray[np.float64]:
        """當前頭部姿態，4x4 齊次轉換矩陣。"""

    @property
    @abstractmethod
    def body_yaw(self) -> float:
        """當前身體偏轉角度，單位為弧度。"""

    @abstractmethod
    def get_state_summary(self) -> dict:
        """取得機器人所有狀態的摘要。

        Returns:
            包含各部位狀態、底盤位置等資訊的字典。
        """

    @abstractmethod
    def close(self) -> None:
        """釋放所有資源。"""
