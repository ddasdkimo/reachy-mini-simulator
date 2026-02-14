"""RealReachyMini - 封裝真實 Reachy Mini SDK 的介面實作。

將 RobotInterface 的呼叫轉發給 reachy_mini.ReachyMini SDK，
讓應用程式碼能透過統一介面操控真實機器人。

底盤移動透過 ChassisInterface 控制，若未提供底盤控制器，
則以 stub 模式運作（僅記錄日誌，不執行實際移動）。

SDK v1.3.0 對應：
- set_target / goto_target 直接轉發
- InterpolationTechnique enum 映射
- is_awake / motor states 內部追蹤（SDK 無對應 property）
- stop_recording() 回傳 List[Dict]，需轉換為 Move
- get_DoA() 大小寫注意
"""

from __future__ import annotations

import logging
import math
from typing import Any, List

import numpy as np
import numpy.typing as npt

from .robot_interface import RobotInterface, MediaInterface
from .chassis_controller import ChassisInterface
from .motion import Move, JointFrame

logger = logging.getLogger(__name__)

# SDK InterpolationTechnique enum（try/except 避免未安裝 SDK 時出錯）
try:
    from reachy_mini import ReachyMini
    from reachy_mini.config import InterpolationTechnique

    _HAS_SDK = True
except ImportError:
    _HAS_SDK = False

# 介面層的插值方法字串 → SDK InterpolationTechnique 映射
_INTERP_MAP: dict[str, str] = {
    "MIN_JERK": "MIN_JERK",
    "LINEAR": "LINEAR",
    "EASE": "EASE_IN_OUT",
    "EASE_IN_OUT": "EASE_IN_OUT",
    "CARTOON": "CARTOON",
}

# SDK 馬達 ID（用於 enable_motors / disable_motors）
_MOTOR_IDS = [
    "body_rotation",
    "stewart_1", "stewart_2", "stewart_3",
    "stewart_4", "stewart_5", "stewart_6",
    "right_antenna", "left_antenna",
]

# 關節位置回傳的 key 對應（head tuple 有 7 個值）
_HEAD_JOINT_NAMES = [
    "body_rotation",
    "stewart_1", "stewart_2", "stewart_3",
    "stewart_4", "stewart_5", "stewart_6",
]


class RealMedia(MediaInterface):
    """封裝真實 Reachy Mini SDK 的 media 介面。

    SDK MediaManager 方法與介面的差異：
    - get_DoA() 大小寫不同，回傳 tuple[float, bool] | None
    - is_sound_playing() SDK 無此方法，內部追蹤
    """

    def __init__(self, sdk_media: Any) -> None:
        self._sdk_media = sdk_media
        self._sound_playing = False

    def get_frame(self) -> npt.NDArray[np.uint8]:
        """取得一幀影像（BGR）。"""
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
        """播放音檔。SDK 有 play_sound() 但無 is_sound_playing()，需內部追蹤。"""
        self._sdk_media.play_sound(file_path)
        self._sound_playing = True

    def is_sound_playing(self) -> bool:
        """SDK 無此方法，以內部旗標追蹤。"""
        return self._sound_playing

    def stop_sound(self) -> None:
        """停止音檔播放。SDK 無 stop_sound()，透過 stop_playing() 替代。"""
        self._sdk_media.stop_playing()
        self._sound_playing = False

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
        """取得聲源方向角度。

        SDK 方法為 get_DoA()（注意大小寫），
        回傳 tuple[float, bool] | None，取 tuple[0] 為角度。
        """
        result = self._sdk_media.get_DoA()
        if result is None:
            return 0.0
        return float(result[0])

    def close(self) -> None:
        """關閉 media 資源。"""
        self._sdk_media.close()


class RealReachyMini(RobotInterface):
    """封裝真實 reachy_mini.ReachyMini SDK 的介面實作。

    SDK v1.3.0 與介面層的主要差異：
    - SDK 無 is_awake property → 內部 _is_awake 追蹤
    - SDK 無 is_motor_enabled() → 內部 _motor_states dict 追蹤
    - SDK 的 enable_motors/disable_motors 接受 ids list
    - SDK 的 get_current_joint_positions() 回傳 tuple(head[7], antenna[2])
    - SDK 的 goto_target() method 參數為 InterpolationTechnique enum
    - SDK 的 stop_recording() 回傳 List[Dict]，需轉換為 Move
    - SDK 的 look_at_image/look_at_world 有 duration/perform_movement 額外參數
    """

    def __init__(
        self,
        sdk_robot: Any,
        chassis: ChassisInterface | None = None,
    ) -> None:
        self._sdk = sdk_robot

        # 自動把 sounddevice 輸出裝置切到 Reachy Mini Audio
        self._set_reachy_audio_output()

        self._media = RealMedia(sdk_robot.media)
        self._chassis = chassis

        # 底盤移動狀態
        self._move_target: tuple[float, float] | None = None
        self._move_speed: float = 0.5

        # SDK 無 is_awake property，內部追蹤
        self._is_awake: bool = True

        # SDK 無 is_motor_enabled()，內部 dict 追蹤
        self._motor_states: dict[str, bool] = {mid: True for mid in _MOTOR_IDS}

        # SDK 無 is_motion_playing property，內部追蹤
        self._is_motion_playing: bool = False

        if chassis is not None:
            logger.info("RealReachyMini 已初始化（使用 %s 底盤）", type(chassis).__name__)
        else:
            logger.info("RealReachyMini 已初始化（底盤移動為 stub）")

    @staticmethod
    def _set_reachy_audio_output() -> None:
        """自動尋找 Reachy Mini Audio 裝置並設為 sounddevice 預設輸出。"""
        try:
            import sounddevice as sd
            for i, d in enumerate(sd.query_devices()):
                if "Reachy Mini" in d["name"] and d["max_output_channels"] > 0:
                    sd.default.device = (sd.default.device[0], i)
                    logger.info("音訊輸出裝置已切換至: [%d] %s", i, d["name"])
                    return
            logger.warning("未找到 Reachy Mini Audio 輸出裝置，使用系統預設")
        except ImportError:
            pass

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
        """當前天線角度 [right, left]。

        SDK: get_present_antenna_joint_positions() -> list[float]
        """
        return list(self._sdk.get_present_antenna_joint_positions())

    @property
    def head_pose(self) -> npt.NDArray[np.float64]:
        """當前頭部姿態 4x4 矩陣。

        SDK: get_current_head_pose() -> npt.NDArray[np.float64]
        """
        return np.array(self._sdk.get_current_head_pose(), dtype=np.float64)

    @property
    def body_yaw(self) -> float:
        """當前身體偏轉角度（弧度）。

        SDK: get_current_joint_positions() -> tuple(head[7], antenna[2])
        head[0] 為 body_rotation。
        """
        head_joints, _antenna_joints = self._sdk.get_current_joint_positions()
        return float(head_joints[0])

    def set_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: npt.NDArray[np.float64] | list[float] | None = None,
        body_yaw: float | None = None,
    ) -> None:
        """設定目標姿態。SDK set_target 簽名相容，直接轉發。"""
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
        """以插值方式平滑移動到目標。

        將介面層的 method 字串映射到 SDK InterpolationTechnique enum：
        - "MIN_JERK" -> InterpolationTechnique.MIN_JERK
        - "LINEAR"   -> InterpolationTechnique.LINEAR
        - "EASE"     -> InterpolationTechnique.EASE_IN_OUT
        - "CARTOON"  -> InterpolationTechnique.CARTOON
        """
        kwargs: dict[str, Any] = {"duration": duration}
        if head is not None:
            kwargs["head"] = head
        if antennas is not None:
            kwargs["antennas"] = antennas
        if body_yaw is not None:
            kwargs["body_yaw"] = body_yaw

        # 映射插值方法字串到 SDK enum
        if _HAS_SDK:
            sdk_method_name = _INTERP_MAP.get(method, "MIN_JERK")
            kwargs["method"] = InterpolationTechnique[sdk_method_name]
        else:
            kwargs["method"] = method

        self._sdk.goto_target(**kwargs)

    def get_current_joint_positions(self) -> dict[str, float]:
        """取得當前所有關節位置。

        SDK 回傳 tuple(head_joints[7], antenna_joints[2])，
        轉換為 dict：body_rotation, stewart_1~6, right_antenna, left_antenna。
        """
        head_joints, antenna_joints = self._sdk.get_current_joint_positions()
        result: dict[str, float] = {}
        for i, name in enumerate(_HEAD_JOINT_NAMES):
            result[name] = float(head_joints[i])
        result["right_antenna"] = float(antenna_joints[0])
        result["left_antenna"] = float(antenna_joints[1])
        return result

    # ── Phase 1B: 凝視追蹤 ────────────────────────────────────────────

    def look_at_image(self, u: float, v: float) -> None:
        """看向影像座標。

        SDK: look_at_image(u, v, duration=1.0, perform_movement=True) -> ndarray
        介面層不需要回傳值。
        """
        self._sdk.look_at_image(int(u), int(v), duration=1.0, perform_movement=True)

    def look_at_world(self, x: float, y: float, z: float) -> None:
        """看向世界座標。

        SDK: look_at_world(x, y, z, duration=1.0, perform_movement=True) -> ndarray
        介面層不需要回傳值。
        """
        self._sdk.look_at_world(x, y, z, duration=1.0, perform_movement=True)

    # ── Phase 1C: 喚醒/睡眠 + 馬達控制 ────────────────────────────────

    def wake_up(self) -> None:
        """喚醒機器人。SDK 有 wake_up() 但無 is_awake property。"""
        self._sdk.wake_up()
        self._is_awake = True
        for mid in _MOTOR_IDS:
            self._motor_states[mid] = True
        logger.info("RealReachyMini 已喚醒")

    def goto_sleep(self) -> None:
        """讓機器人進入睡眠。SDK 有 goto_sleep() 但無 is_awake property。"""
        self._sdk.goto_sleep()
        self._is_awake = False
        for mid in _MOTOR_IDS:
            self._motor_states[mid] = False
        logger.info("RealReachyMini 已進入睡眠")

    @property
    def is_awake(self) -> bool:
        """SDK 無 is_awake property，以內部旗標追蹤。"""
        return self._is_awake

    def set_motor_enabled(self, motor_name: str, enabled: bool) -> None:
        """啟用/停用指定馬達。

        SDK: enable_motors(ids=[name]) / disable_motors(ids=[name])
        """
        if enabled:
            self._sdk.enable_motors(ids=[motor_name])
        else:
            self._sdk.disable_motors(ids=[motor_name])
        self._motor_states[motor_name] = enabled

    def is_motor_enabled(self, motor_name: str) -> bool:
        """SDK 無此方法，以內部 dict 追蹤。"""
        return self._motor_states.get(motor_name, False)

    def set_gravity_compensation(self, enabled: bool) -> None:
        """啟用/停用重力補償。

        SDK: enable_gravity_compensation() / disable_gravity_compensation()
        """
        if enabled:
            self._sdk.enable_gravity_compensation()
        else:
            self._sdk.disable_gravity_compensation()

    # ── Phase 2C: IMU 數據 ────────────────────────────────────────────

    def get_imu_data(self) -> dict:
        """取得 IMU 數據。

        SDK: imu property -> Dict[str, List[float] | float] | None
        """
        data = self._sdk.imu
        if data is None:
            return {}
        return dict(data)

    # ── Phase 3: 動作錄製/回放 ────────────────────────────────────────

    def start_motion_recording(self) -> None:
        """開始錄製動作。SDK: start_recording()。"""
        self._sdk.start_recording()
        logger.info("RealReachyMini 開始錄製動作")

    def stop_motion_recording(self) -> Move:
        """停止錄製並回傳 Move 物件。

        SDK: stop_recording() -> Optional[List[Dict]]
        需要將 List[Dict] 轉換為 Move 物件。
        """
        raw_frames = self._sdk.stop_recording()
        if raw_frames is None:
            return Move(frames=[])

        frames: list[JointFrame] = []
        for i, frame_dict in enumerate(raw_frames):
            frames.append(JointFrame(
                timestamp=frame_dict.get("timestamp", float(i) / 100.0),
                head_pose=frame_dict.get("head_pose"),
                antennas=frame_dict.get("antennas"),
                body_yaw=frame_dict.get("body_yaw"),
            ))
        move = Move(frames=frames)
        logger.info("RealReachyMini 停止錄製（%d 幀）", len(frames))
        return move

    def play_motion(self, move: Move, speed: float = 1.0) -> None:
        """回放動作序列。

        SDK: play_move(move, play_frequency=100.0, initial_goto_duration=0.0, sound=True)
        speed 透過調整 play_frequency 實現。
        """
        self._is_motion_playing = True
        try:
            self._sdk.play_move(
                move,
                play_frequency=100.0 * speed,
                initial_goto_duration=0.0,
                sound=True,
            )
        finally:
            self._is_motion_playing = False
        logger.info("RealReachyMini 回放動作完成（速度 %.1fx）", speed)

    @property
    def is_motion_playing(self) -> bool:
        """SDK 無此 property，以內部旗標追蹤。"""
        return self._is_motion_playing

    def close(self) -> None:
        if self._chassis is not None:
            self._chassis.close()
        self._media.close()
        logger.info("RealReachyMini 已關閉")
