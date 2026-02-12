"""RealReachyMini - 封裝真實 Reachy Mini SDK 的介面實作。

將 RobotInterface 的呼叫轉發給 reachy_mini.ReachyMini SDK，
讓應用程式碼能透過統一介面操控真實機器人。

底盤移動透過 ChassisInterface 控制，若未提供底盤控制器，
則以 stub 模式運作（僅記錄日誌，不執行實際移動）。
"""

import logging
import math
from typing import Any

import numpy as np
import numpy.typing as npt

from .robot_interface import RobotInterface, MediaInterface
from .chassis_controller import ChassisInterface

logger = logging.getLogger(__name__)


class RealMedia(MediaInterface):
    """封裝真實 Reachy Mini SDK 的 media 介面。"""

    def __init__(self, sdk_media: Any) -> None:
        """初始化 RealMedia。

        Args:
            sdk_media: reachy_mini.ReachyMini 實例的 media 屬性。
        """
        self._sdk_media = sdk_media

    def get_frame(self) -> npt.NDArray[np.uint8]:
        """從真實相機取得一幀影像。"""
        return self._sdk_media.get_frame()

    def get_output_audio_samplerate(self) -> int:
        """取得真實音訊輸出的取樣率。"""
        return self._sdk_media.get_output_audio_samplerate()

    def start_playing(self) -> None:
        """開始真實音訊播放。"""
        self._sdk_media.start_playing()

    def stop_playing(self) -> None:
        """停止真實音訊播放。"""
        self._sdk_media.stop_playing()

    def push_audio_sample(self, samples: npt.NDArray[np.float32]) -> None:
        """推送音訊樣本到真實播放裝置。"""
        self._sdk_media.push_audio_sample(samples)

    @property
    def is_playing(self) -> bool:
        """是否正在播放音訊。"""
        return self._sdk_media.is_playing

    def close(self) -> None:
        """釋放資源。"""
        # SDK media 的生命週期由 SDK 自行管理
        pass


class RealReachyMini(RobotInterface):
    """封裝真實 reachy_mini.ReachyMini SDK 的介面實作。

    將 set_target 等呼叫直接轉發給 SDK。
    底盤移動透過 ChassisInterface 控制：
    - 若提供了 chassis 參數，move_to/update_position 會驅動底盤。
    - 若未提供，則以 stub 模式運作（僅記錄日誌）。
    """

    def __init__(
        self,
        sdk_robot: Any,
        chassis: ChassisInterface | None = None,
    ) -> None:
        """初始化 RealReachyMini。

        Args:
            sdk_robot: reachy_mini.ReachyMini 的實例。
            chassis: 底盤控制器，若為 None 則以 stub 模式運作。
        """
        self._sdk = sdk_robot
        self._media = RealMedia(sdk_robot.media)
        self._chassis = chassis

        # 底盤移動狀態
        self._move_target: tuple[float, float] | None = None
        self._move_speed: float = 0.5  # 預設移動速度 m/s

        if chassis is not None:
            logger.info("RealReachyMini 已初始化（使用 %s 底盤）", type(chassis).__name__)
        else:
            logger.info("RealReachyMini 已初始化（底盤移動為 stub）")

    @property
    def position(self) -> tuple[float, float]:
        """機器人在 2D 地圖上的座標 (x, y)。

        若有底盤控制器，從里程計讀取；否則回傳內部快取。
        """
        if self._chassis is not None and self._chassis.is_connected:
            x, y, _ = self._chassis.get_odometry()
            return (x, y)
        return self._fallback_position

    @position.setter
    def position(self, value: tuple[float, float]) -> None:
        self._fallback_position = value

    @property
    def _fallback_position(self) -> tuple[float, float]:
        """內部備用位置（無底盤時使用）。"""
        return getattr(self, "_pos_cache", (0.0, 0.0))

    @_fallback_position.setter
    def _fallback_position(self, value: tuple[float, float]) -> None:
        self._pos_cache = value

    @property
    def heading(self) -> float:
        """機器人朝向角度，單位為度。

        若有底盤控制器，從里程計讀取並轉換為度數。
        """
        if self._chassis is not None and self._chassis.is_connected:
            _, _, heading_rad = self._chassis.get_odometry()
            return math.degrees(heading_rad)
        return self._fallback_heading

    @heading.setter
    def heading(self, value: float) -> None:
        self._fallback_heading = value

    @property
    def _fallback_heading(self) -> float:
        """內部備用朝向（無底盤時使用）。"""
        return getattr(self, "_heading_cache", 0.0)

    @_fallback_heading.setter
    def _fallback_heading(self, value: float) -> None:
        self._heading_cache = value

    @property
    def media(self) -> RealMedia:
        """取得 RealMedia 實例。"""
        return self._media

    @property
    def antenna_pos(self) -> list[float]:
        """當前天線角度 [right, left]，單位為弧度。"""
        return list(self._sdk.antenna_pos)

    @property
    def head_pose(self) -> npt.NDArray[np.float64]:
        """當前頭部姿態，4x4 齊次轉換矩陣。"""
        return np.array(self._sdk.head_pose, dtype=np.float64)

    @property
    def body_yaw(self) -> float:
        """當前身體偏轉角度，單位為弧度。"""
        return float(self._sdk.body_yaw)

    def set_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: npt.NDArray[np.float64] | list[float] | None = None,
        body_yaw: float | None = None,
    ) -> None:
        """轉發給 SDK 的 set_target。"""
        kwargs: dict[str, Any] = {}
        if head is not None:
            kwargs["head"] = head
        if antennas is not None:
            kwargs["antennas"] = antennas
        if body_yaw is not None:
            kwargs["body_yaw"] = body_yaw
        self._sdk.set_target(**kwargs)

    def move_to(self, x: float, y: float) -> None:
        """設定底盤移動目標座標。

        若有底盤控制器，計算朝向並設定速度；
        否則僅記錄日誌。

        Args:
            x: 目標 x 座標（公尺）。
            y: 目標 y 座標（公尺）。
        """
        if self._chassis is None or not self._chassis.is_connected:
            logger.warning(
                "RealReachyMini.move_to(%.2f, %.2f) 被呼叫，但底盤未連線",
                x, y,
            )
            return

        self._move_target = (x, y)
        logger.info("RealReachyMini.move_to: 目標=(%.2f, %.2f)", x, y)

    def update_position(self, dt: float) -> bool:
        """更新底盤位置。

        根據目標座標計算需要的速度指令，發送給底盤控制器。
        到達目標後自動停止。

        Args:
            dt: 時間差（秒）。

        Returns:
            True 表示仍在移動中，False 表示已到達或無目標。
        """
        if self._move_target is None:
            return False

        if self._chassis is None or not self._chassis.is_connected:
            return False

        tx, ty = self._move_target
        px, py = self.position

        dx = tx - px
        dy = ty - py
        distance = math.sqrt(dx * dx + dy * dy)

        # 到達閾值（0.05 公尺）
        if distance < 0.05:
            self._chassis.stop()
            self._move_target = None
            logger.info("RealReachyMini 已到達目標 (%.2f, %.2f)", tx, ty)
            return False

        # 計算目標朝向與當前朝向的角度差
        target_heading = math.atan2(dy, dx)
        _, _, current_heading = self._chassis.get_odometry()
        angle_diff = math.atan2(
            math.sin(target_heading - current_heading),
            math.cos(target_heading - current_heading),
        )

        # 簡易比例控制器
        angular_speed = max(-2.0, min(2.0, angle_diff * 2.0))

        # 若朝向偏差太大，先轉向再前進
        if abs(angle_diff) > 0.3:
            self._chassis.set_velocity(0.0, angular_speed)
        else:
            self._chassis.set_velocity(self._move_speed, angular_speed * 0.5)

        return True

    @property
    def is_moving(self) -> bool:
        """機器人是否正在移動中。"""
        return self._move_target is not None

    def get_state_summary(self) -> dict[str, Any]:
        """取得機器人狀態摘要。"""
        chassis_info = "none"
        if self._chassis is not None:
            chassis_info = type(self._chassis).__name__
            if self._chassis.is_connected:
                chassis_info += " (已連線)"
            else:
                chassis_info += " (已斷線)"

        return {
            "position": self.position,
            "heading": self.heading,
            "antenna_pos": self.antenna_pos,
            "body_yaw": self.body_yaw,
            "is_moving": self.is_moving,
            "mode": "real",
            "chassis": chassis_info,
        }

    def close(self) -> None:
        """釋放資源。"""
        if self._chassis is not None:
            self._chassis.close()
        self._media.close()
        logger.info("RealReachyMini 已關閉")
