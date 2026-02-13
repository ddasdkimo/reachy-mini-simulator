"""MockReachyMini - 模擬 Reachy Mini 機器人介面。

提供與 reachy_mini.ReachyMini 相容的介面，包含頭部姿態、天線角度、身體旋轉、
以及底盤移動模擬，讓應用程式碼能在沒有實體機器人的情況下運作。
"""

from __future__ import annotations

import logging
import math
import random
import time
from typing import Any

import numpy as np
import numpy.typing as npt

from .robot_interface import RobotInterface
from .mock_media import MockMedia
from .interpolation import InterpolationEngine, InterpolationTarget, InterpolationMethod
from .motion import Move, MotionRecorder, MotionPlayer
from .utils import create_head_pose

logger = logging.getLogger(__name__)

# 馬達名稱列表
MOTOR_NAMES = [
    "head_roll", "head_pitch", "head_yaw",
    "antenna_right", "antenna_left", "body_yaw",
]


class MockReachyMini(RobotInterface):
    """模擬 Reachy Mini 機器人，相容於 reachy_mini.ReachyMini 的介面。

    記錄所有指令到內部狀態和歷史日誌，並提供 2D 底盤移動模擬。
    """

    def __init__(
        self,
        position: tuple[float, float] = (0.0, 0.0),
        heading: float = 0.0,
        speed: float = 0.5,
        use_webcam: bool = False,
    ) -> None:
        # 底盤狀態
        self._position: tuple[float, float] = position
        self._heading: float = heading
        self.speed: float = speed

        # 機器人各部位狀態
        self._antenna_pos: list[float] = [0.0, 0.0]  # [right, left]，弧度
        self._head_pose: npt.NDArray[np.float64] = np.eye(4)  # 4x4 齊次矩陣
        self._body_yaw: float = 0.0  # 弧度

        # 移動目標
        self._move_target: tuple[float, float] | None = None

        # Media 介面
        self._media = MockMedia(use_webcam=use_webcam)

        # 指令歷史日誌
        self.state_log: list[dict[str, Any]] = []

        # Phase 1A: 插值引擎
        self._interp_engine = InterpolationEngine()

        # Phase 1C: 喚醒/睡眠 + 馬達控制
        self._is_awake: bool = True
        self._motor_states: dict[str, bool] = {name: True for name in MOTOR_NAMES}
        self._gravity_compensation: bool = False

        # Phase 3: 動作錄製/回放
        self._motion_recorder = MotionRecorder()
        self._motion_player = MotionPlayer()

        logger.info(
            "MockReachyMini 已初始化：位置=(%.2f, %.2f)，朝向=%.1f°",
            position[0],
            position[1],
            heading,
        )

    @property
    def position(self) -> tuple[float, float]:
        return self._position

    @position.setter
    def position(self, value: tuple[float, float]) -> None:
        self._position = value

    @property
    def heading(self) -> float:
        return self._heading

    @heading.setter
    def heading(self, value: float) -> None:
        self._heading = value

    @property
    def media(self) -> MockMedia:
        return self._media

    @property
    def antenna_pos(self) -> list[float]:
        return self._antenna_pos.copy()

    @property
    def head_pose(self) -> npt.NDArray[np.float64]:
        return self._head_pose.copy()

    @property
    def body_yaw(self) -> float:
        return self._body_yaw

    def set_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: npt.NDArray[np.float64] | list[float] | None = None,
        body_yaw: float | None = None,
    ) -> None:
        if head is None and antennas is None and body_yaw is None:
            raise ValueError(
                "至少需提供 head、antennas 或 body_yaw 其中之一。"
            )

        # 未喚醒時跳過，不拋出錯誤
        if not self._is_awake:
            return

        if head is not None:
            head = np.asarray(head, dtype=np.float64)
            if head.shape != (4, 4):
                raise ValueError(
                    f"head 必須為 4x4 矩陣，收到形狀 {head.shape}。"
                )
            self._head_pose = head

        if antennas is not None:
            if len(antennas) != 2:
                raise ValueError(
                    "antennas 必須為長度 2 的陣列 [right, left]。"
                )
            self._antenna_pos = [float(antennas[0]), float(antennas[1])]

        if body_yaw is not None:
            if not isinstance(body_yaw, (int, float)):
                raise ValueError("body_yaw 必須為數值。")
            self._body_yaw = float(body_yaw)

        # 記錄到歷史日誌
        log_entry: dict[str, Any] = {"timestamp": time.time()}
        if head is not None:
            log_entry["head"] = head.tolist()
        if antennas is not None:
            log_entry["antennas"] = self._antenna_pos.copy()
        if body_yaw is not None:
            log_entry["body_yaw"] = self._body_yaw
        self.state_log.append(log_entry)

        logger.debug("set_target: %s", log_entry)

    def move_to(self, x: float, y: float) -> None:
        self._move_target = (x, y)
        dx = x - self.position[0]
        dy = y - self.position[1]
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            self.heading = math.degrees(math.atan2(dy, dx))
        logger.info(
            "move_to: 目標=(%.2f, %.2f)，朝向=%.1f°",
            x, y, self.heading,
        )

    def update_position(self, dt: float) -> bool:
        if self._move_target is None:
            return False

        tx, ty = self._move_target
        px, py = self.position

        dx = tx - px
        dy = ty - py
        distance = math.sqrt(dx * dx + dy * dy)

        step = self.speed * dt

        if distance <= step:
            self.position = (tx, ty)
            self._move_target = None
            logger.info("已到達目標座標 (%.2f, %.2f)", tx, ty)
            return False

        ratio = step / distance
        new_x = px + dx * ratio
        new_y = py + dy * ratio
        self.position = (new_x, new_y)
        self.heading = math.degrees(math.atan2(dy, dx))
        return True

    @property
    def is_moving(self) -> bool:
        return self._move_target is not None

    def get_state_summary(self) -> dict[str, Any]:
        head_yaw_deg, head_pitch_deg = self._extract_head_angles()

        return {
            "position": self.position,
            "heading": round(self.heading, 1),
            "antenna_pos": self._antenna_pos.copy(),
            "antenna_pos_deg": [
                round(math.degrees(a), 1) for a in self._antenna_pos
            ],
            "head_yaw_deg": round(head_yaw_deg, 1),
            "head_pitch_deg": round(head_pitch_deg, 1),
            "body_yaw": round(self._body_yaw, 4),
            "body_yaw_deg": round(math.degrees(self._body_yaw), 1),
            "move_target": self._move_target,
            "is_moving": self._move_target is not None,
            "audio_playing": self._media.is_playing,
            "log_count": len(self.state_log),
            "is_awake": self._is_awake,
        }

    def _extract_head_angles(self) -> tuple[float, float]:
        try:
            from scipy.spatial.transform import Rotation as R
            rot_matrix = self._head_pose[:3, :3]
            euler = R.from_matrix(rot_matrix).as_euler("xyz", degrees=True)
            return float(euler[2]), float(euler[1])
        except (ImportError, ValueError):
            r = self._head_pose[:3, :3]
            yaw = math.degrees(math.atan2(r[1, 0], r[0, 0]))
            pitch = math.degrees(math.asin(max(-1.0, min(1.0, -r[2, 0]))))
            return yaw, pitch

    # ── Phase 1A: 插值系統 ────────────────────────────────────────────

    def goto_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: list[float] | None = None,
        body_yaw: float | None = None,
        duration: float = 1.0,
        method: str = "MIN_JERK",
    ) -> None:
        interp_method = InterpolationMethod(method)
        target = InterpolationTarget(
            start_head=self._head_pose.copy() if head is not None else None,
            end_head=np.asarray(head, dtype=np.float64) if head is not None else None,
            start_antennas=self._antenna_pos.copy() if antennas is not None else None,
            end_antennas=list(antennas) if antennas is not None else None,
            start_body_yaw=self._body_yaw if body_yaw is not None else None,
            end_body_yaw=body_yaw,
            duration=duration,
            method=interp_method,
        )
        self._interp_engine.start(target)

    def get_current_joint_positions(self) -> dict[str, float]:
        yaw_deg, pitch_deg = self._extract_head_angles()
        # 從旋轉矩陣提取 roll
        r = self._head_pose[:3, :3]
        roll_deg = math.degrees(math.atan2(r[2, 1], r[2, 2]))

        return {
            "head_roll": roll_deg,
            "head_pitch": pitch_deg,
            "head_yaw": yaw_deg,
            "antenna_right": math.degrees(self._antenna_pos[0]),
            "antenna_left": math.degrees(self._antenna_pos[1]),
            "body_yaw": math.degrees(self._body_yaw),
        }

    # ── Phase 1B: 凝視追蹤 ────────────────────────────────────────────

    def look_at_image(self, u: float, v: float) -> None:
        """將影像座標 (0~1) 轉為頭部 yaw/pitch。"""
        # u: 0=左, 1=右 → yaw: +30 到 -30 度
        # v: 0=上, 1=下 → pitch: -20 到 +20 度
        yaw = 30.0 - u * 60.0
        pitch = -20.0 + v * 40.0
        head = create_head_pose(yaw=yaw, pitch=pitch, degrees=True)
        self.set_target(head=head)

    def look_at_world(self, x: float, y: float, z: float) -> None:
        """將世界座標轉為頭部 yaw/pitch。"""
        dist = math.sqrt(x * x + y * y + z * z)
        if dist < 1e-6:
            return
        yaw = math.degrees(math.atan2(y, x))
        pitch = math.degrees(math.atan2(-z, math.sqrt(x * x + y * y)))
        head = create_head_pose(yaw=yaw, pitch=pitch, degrees=True)
        self.set_target(head=head)

    # ── Phase 1C: 喚醒/睡眠 + 馬達控制 ────────────────────────────────

    def wake_up(self) -> None:
        self._is_awake = True
        for name in MOTOR_NAMES:
            self._motor_states[name] = True
        logger.info("MockReachyMini 已喚醒")

    def goto_sleep(self) -> None:
        self._is_awake = False
        for name in MOTOR_NAMES:
            self._motor_states[name] = False
        logger.info("MockReachyMini 已進入睡眠")

    @property
    def is_awake(self) -> bool:
        return self._is_awake

    def set_motor_enabled(self, motor_name: str, enabled: bool) -> None:
        if motor_name not in self._motor_states:
            raise ValueError(f"未知的馬達名稱: {motor_name}")
        self._motor_states[motor_name] = enabled

    def is_motor_enabled(self, motor_name: str) -> bool:
        if motor_name not in self._motor_states:
            raise ValueError(f"未知的馬達名稱: {motor_name}")
        return self._motor_states[motor_name]

    def set_gravity_compensation(self, enabled: bool) -> None:
        self._gravity_compensation = enabled
        logger.info("重力補償: %s", "啟用" if enabled else "停用")

    # ── Phase 2C: IMU 數據 ────────────────────────────────────────────

    def get_imu_data(self) -> dict:
        noise = 0.01
        return {
            "accelerometer": [
                random.gauss(0.0, noise),
                random.gauss(0.0, noise),
                9.81 + random.gauss(0.0, noise),
            ],
            "gyroscope": [
                random.gauss(0.0, noise),
                random.gauss(0.0, noise),
                random.gauss(0.0, noise),
            ],
            "quaternion": [1.0, 0.0, 0.0, 0.0],
        }

    # ── Phase 3: 動作錄製/回放 ────────────────────────────────────────

    def start_motion_recording(self) -> None:
        self._motion_recorder.start()
        logger.info("開始錄製動作")

    def stop_motion_recording(self) -> Move:
        move = self._motion_recorder.stop()
        logger.info("停止錄製動作（%d 幀）", len(move.frames))
        return move

    def play_motion(self, move: Move, speed: float = 1.0) -> None:
        self._motion_player.play(move, speed)
        logger.info("開始回放動作（速度 %.1fx）", speed)

    @property
    def is_motion_playing(self) -> bool:
        return self._motion_player.is_playing

    def close(self) -> None:
        self._media.close()
        logger.info("MockReachyMini 已關閉")
