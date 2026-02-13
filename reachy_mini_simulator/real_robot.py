"""RealReachyMini - 封裝真實 Reachy Mini SDK 的介面實作。

將 RobotInterface 的呼叫轉發給 reachy_mini.ReachyMini SDK，
讓應用程式碼能透過統一介面操控真實機器人。

底盤移動透過 ChassisInterface 控制，若未提供底盤控制器，
則以 stub 模式運作（僅記錄日誌，不執行實際移動）。
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
import numpy.typing as npt

from .robot_interface import RobotInterface, MediaInterface
from .chassis_controller import ChassisInterface
from .motion import Move

logger = logging.getLogger(__name__)


class RealMedia(MediaInterface):
    """封裝真實 Reachy Mini SDK 的 media 介面。"""

    def __init__(self, sdk_media: Any) -> None:
        self._sdk_media = sdk_media

    def get_frame(self) -> npt.NDArray[np.uint8]:
        return self._sdk_media.get_frame()

    def get_output_audio_samplerate(self) -> int:
        return self._sdk_media.get_output_audio_samplerate()

    def start_playing(self) -> None:
        self._sdk_media.start_playing()

    def stop_playing(self) -> None:
        self._sdk_media.stop_playing()

    def push_audio_sample(self, samples: npt.NDArray[np.float32]) -> None:
        self._sdk_media.push_audio_sample(samples)

    @property
    def is_playing(self) -> bool:
        return self._sdk_media.is_playing

    # ── Phase 2A: 音檔播放 ────────────────────────────────────────────

    def play_sound(self, file_path: str) -> None:
        self._sdk_media.play_sound(file_path)

    def is_sound_playing(self) -> bool:
        return self._sdk_media.is_sound_playing()

    def stop_sound(self) -> None:
        self._sdk_media.stop_sound()

    # ── Phase 2B: 錄音 + DoA ─────────────────────────────────────────

    def start_recording(self) -> None:
        self._sdk_media.start_recording()

    def stop_recording(self) -> None:
        self._sdk_media.stop_recording()

    def get_audio_sample(self) -> npt.NDArray[np.float32] | None:
        return self._sdk_media.get_audio_sample()

    @property
    def is_recording(self) -> bool:
        return self._sdk_media.is_recording

    def get_doa(self) -> float:
        return self._sdk_media.get_doa()

    def close(self) -> None:
        pass


class RealReachyMini(RobotInterface):
    """封裝真實 reachy_mini.ReachyMini SDK 的介面實作。"""

    def __init__(
        self,
        sdk_robot: Any,
        chassis: ChassisInterface | None = None,
    ) -> None:
        self._sdk = sdk_robot
        self._media = RealMedia(sdk_robot.media)
        self._chassis = chassis

        # 底盤移動狀態
        self._move_target: tuple[float, float] | None = None
        self._move_speed: float = 0.5

        if chassis is not None:
            logger.info("RealReachyMini 已初始化（使用 %s 底盤）", type(chassis).__name__)
        else:
            logger.info("RealReachyMini 已初始化（底盤移動為 stub）")

    @property
    def position(self) -> tuple[float, float]:
        if self._chassis is not None and self._chassis.is_connected:
            x, y, _ = self._chassis.get_odometry()
            return (x, y)
        return self._fallback_position

    @position.setter
    def position(self, value: tuple[float, float]) -> None:
        self._fallback_position = value

    @property
    def _fallback_position(self) -> tuple[float, float]:
        return getattr(self, "_pos_cache", (0.0, 0.0))

    @_fallback_position.setter
    def _fallback_position(self, value: tuple[float, float]) -> None:
        self._pos_cache = value

    @property
    def heading(self) -> float:
        if self._chassis is not None and self._chassis.is_connected:
            _, _, heading_rad = self._chassis.get_odometry()
            return math.degrees(heading_rad)
        return self._fallback_heading

    @heading.setter
    def heading(self, value: float) -> None:
        self._fallback_heading = value

    @property
    def _fallback_heading(self) -> float:
        return getattr(self, "_heading_cache", 0.0)

    @_fallback_heading.setter
    def _fallback_heading(self, value: float) -> None:
        self._heading_cache = value

    @property
    def media(self) -> RealMedia:
        return self._media

    @property
    def antenna_pos(self) -> list[float]:
        return list(self._sdk.antenna_pos)

    @property
    def head_pose(self) -> npt.NDArray[np.float64]:
        return np.array(self._sdk.head_pose, dtype=np.float64)

    @property
    def body_yaw(self) -> float:
        return float(self._sdk.body_yaw)

    def set_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: npt.NDArray[np.float64] | list[float] | None = None,
        body_yaw: float | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if head is not None:
            kwargs["head"] = head
        if antennas is not None:
            kwargs["antennas"] = antennas
        if body_yaw is not None:
            kwargs["body_yaw"] = body_yaw
        self._sdk.set_target(**kwargs)

    def move_to(self, x: float, y: float) -> None:
        if self._chassis is None or not self._chassis.is_connected:
            logger.warning(
                "RealReachyMini.move_to(%.2f, %.2f) 被呼叫，但底盤未連線",
                x, y,
            )
            return
        self._move_target = (x, y)
        logger.info("RealReachyMini.move_to: 目標=(%.2f, %.2f)", x, y)

    def update_position(self, dt: float) -> bool:
        if self._move_target is None:
            return False
        if self._chassis is None or not self._chassis.is_connected:
            return False

        tx, ty = self._move_target
        px, py = self.position

        dx = tx - px
        dy = ty - py
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 0.05:
            self._chassis.stop()
            self._move_target = None
            logger.info("RealReachyMini 已到達目標 (%.2f, %.2f)", tx, ty)
            return False

        target_heading = math.atan2(dy, dx)
        _, _, current_heading = self._chassis.get_odometry()
        angle_diff = math.atan2(
            math.sin(target_heading - current_heading),
            math.cos(target_heading - current_heading),
        )

        angular_speed = max(-2.0, min(2.0, angle_diff * 2.0))

        if abs(angle_diff) > 0.3:
            self._chassis.set_velocity(0.0, angular_speed)
        else:
            self._chassis.set_velocity(self._move_speed, angular_speed * 0.5)

        return True

    @property
    def is_moving(self) -> bool:
        return self._move_target is not None

    def get_state_summary(self) -> dict[str, Any]:
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
            "is_awake": self.is_awake,
        }

    # ── Phase 1A: 插值系統 ────────────────────────────────────────────

    def goto_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: list[float] | None = None,
        body_yaw: float | None = None,
        duration: float = 1.0,
        method: str = "MIN_JERK",
    ) -> None:
        self._sdk.goto_target(
            head=head,
            antennas=antennas,
            body_yaw=body_yaw,
            duration=duration,
            method=method,
        )

    def get_current_joint_positions(self) -> dict[str, float]:
        return self._sdk.get_current_joint_positions()

    # ── Phase 1B: 凝視追蹤 ────────────────────────────────────────────

    def look_at_image(self, u: float, v: float) -> None:
        self._sdk.look_at_image(u, v)

    def look_at_world(self, x: float, y: float, z: float) -> None:
        self._sdk.look_at_world(x, y, z)

    # ── Phase 1C: 喚醒/睡眠 + 馬達控制 ────────────────────────────────

    def wake_up(self) -> None:
        self._sdk.wake_up()

    def goto_sleep(self) -> None:
        self._sdk.goto_sleep()

    @property
    def is_awake(self) -> bool:
        return self._sdk.is_awake

    def set_motor_enabled(self, motor_name: str, enabled: bool) -> None:
        self._sdk.set_motor_enabled(motor_name, enabled)

    def is_motor_enabled(self, motor_name: str) -> bool:
        return self._sdk.is_motor_enabled(motor_name)

    def set_gravity_compensation(self, enabled: bool) -> None:
        self._sdk.set_gravity_compensation(enabled)

    # ── Phase 2C: IMU 數據 ────────────────────────────────────────────

    def get_imu_data(self) -> dict:
        return self._sdk.get_imu_data()

    # ── Phase 3: 動作錄製/回放 ────────────────────────────────────────

    def start_motion_recording(self) -> None:
        self._sdk.start_motion_recording()

    def stop_motion_recording(self) -> Move:
        return self._sdk.stop_motion_recording()

    def play_motion(self, move: Move, speed: float = 1.0) -> None:
        self._sdk.play_motion(move, speed)

    @property
    def is_motion_playing(self) -> bool:
        return self._sdk.is_motion_playing

    def close(self) -> None:
        if self._chassis is not None:
            self._chassis.close()
        self._media.close()
        logger.info("RealReachyMini 已關閉")
