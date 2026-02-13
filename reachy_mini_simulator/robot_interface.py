"""RobotInterface / MediaInterface - 機器人與媒體抽象基底類別。

定義 Reachy Mini 機器人的統一介面，讓模擬器（MockReachyMini）和
真實機器人（RealReachyMini）都遵循相同的介面規範。
"""

from __future__ import annotations

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

    # ── Phase 2A: 音檔播放 ────────────────────────────────────────────

    @abstractmethod
    def play_sound(self, file_path: str) -> None:
        """播放音檔。

        Args:
            file_path: 音檔路徑。
        """

    @abstractmethod
    def is_sound_playing(self) -> bool:
        """是否正在播放音檔。"""

    @abstractmethod
    def stop_sound(self) -> None:
        """停止播放音檔。"""

    # ── Phase 2B: 錄音 + DoA ─────────────────────────────────────────

    @abstractmethod
    def start_recording(self) -> None:
        """開始錄音。"""

    @abstractmethod
    def stop_recording(self) -> None:
        """停止錄音。"""

    @abstractmethod
    def get_audio_sample(self) -> npt.NDArray[np.float32] | None:
        """取得錄音樣本。

        Returns:
            float32 格式的音訊樣本陣列，若未錄音則回傳 None。
        """

    @property
    @abstractmethod
    def is_recording(self) -> bool:
        """是否正在錄音。"""

    @abstractmethod
    def get_doa(self) -> float:
        """取得聲源方向角度（Direction of Arrival）。

        Returns:
            聲源方向角度（度），0~360。
        """

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

    # ── Phase 1A: 插值系統 ────────────────────────────────────────────

    @abstractmethod
    def goto_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: list[float] | None = None,
        body_yaw: float | None = None,
        duration: float = 1.0,
        method: str = "MIN_JERK",
    ) -> None:
        """以插值方式平滑移動到目標姿態。

        Args:
            head: 4x4 齊次轉換矩陣，表示頭部目標姿態。
            antennas: 長度為 2 的陣列 [right, left]，天線目標角度（弧度）。
            body_yaw: 身體偏轉目標角度（弧度）。
            duration: 動畫時長（秒）。
            method: 插值方法名稱（MIN_JERK / LINEAR / EASE / CARTOON）。
        """

    @abstractmethod
    def get_current_joint_positions(self) -> dict[str, float]:
        """取得當前所有關節位置。

        Returns:
            關節名稱到角度值的字典。
        """

    # ── Phase 1B: 凝視追蹤 ────────────────────────────────────────────

    @abstractmethod
    def look_at_image(self, u: float, v: float) -> None:
        """看向影像座標。

        Args:
            u: 影像 x 座標（0.0~1.0，0=左，1=右）。
            v: 影像 y 座標（0.0~1.0，0=上，1=下）。
        """

    @abstractmethod
    def look_at_world(self, x: float, y: float, z: float) -> None:
        """看向世界座標。

        Args:
            x: 世界 x 座標（前方為正）。
            y: 世界 y 座標（左方為正）。
            z: 世界 z 座標（上方為正）。
        """

    # ── Phase 1C: 喚醒/睡眠 + 馬達控制 ────────────────────────────────

    @abstractmethod
    def wake_up(self) -> None:
        """喚醒機器人，啟用所有馬達。"""

    @abstractmethod
    def goto_sleep(self) -> None:
        """讓機器人進入睡眠，關閉所有馬達。"""

    @property
    @abstractmethod
    def is_awake(self) -> bool:
        """機器人是否已喚醒。"""

    @abstractmethod
    def set_motor_enabled(self, motor_name: str, enabled: bool) -> None:
        """啟用/停用指定馬達。

        Args:
            motor_name: 馬達名稱。
            enabled: True 啟用，False 停用。
        """

    @abstractmethod
    def is_motor_enabled(self, motor_name: str) -> bool:
        """查詢指定馬達是否啟用。

        Args:
            motor_name: 馬達名稱。

        Returns:
            是否啟用。
        """

    @abstractmethod
    def set_gravity_compensation(self, enabled: bool) -> None:
        """啟用/停用重力補償。

        Args:
            enabled: True 啟用，False 停用。
        """

    # ── Phase 2C: IMU 數據 ────────────────────────────────────────────

    @abstractmethod
    def get_imu_data(self) -> dict:
        """取得 IMU 感測器數據。

        Returns:
            包含以下鍵值的字典：
            - accelerometer: [ax, ay, az] 加速度（m/s^2）
            - gyroscope: [gx, gy, gz] 角速度（rad/s）
            - quaternion: [w, x, y, z] 四元數
        """

    # ── Phase 3: 動作錄製/回放 ────────────────────────────────────────

    @abstractmethod
    def start_motion_recording(self) -> None:
        """開始錄製動作。"""

    @abstractmethod
    def stop_motion_recording(self) -> "Move":
        """停止錄製動作並回傳 Move 物件。"""

    @abstractmethod
    def play_motion(self, move: "Move", speed: float = 1.0) -> None:
        """回放動作序列。

        Args:
            move: Move 物件。
            speed: 播放速度倍率。
        """

    @property
    @abstractmethod
    def is_motion_playing(self) -> bool:
        """是否正在回放動作。"""

    @abstractmethod
    def close(self) -> None:
        """釋放所有資源。"""
