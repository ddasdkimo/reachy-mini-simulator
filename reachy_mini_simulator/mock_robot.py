"""MockReachyMini - 模擬 Reachy Mini 機器人介面。

提供與 reachy_mini.ReachyMini 相容的介面，包含頭部姿態、天線角度、身體旋轉、
以及底盤移動模擬，讓應用程式碼能在沒有實體機器人的情況下運作。
"""

import logging
import math
import time
from typing import Any

import numpy as np
import numpy.typing as npt

from .robot_interface import RobotInterface
from .mock_media import MockMedia

logger = logging.getLogger(__name__)


class MockReachyMini(RobotInterface):
    """模擬 Reachy Mini 機器人，相容於 reachy_mini.ReachyMini 的介面。

    記錄所有指令到內部狀態和歷史日誌，並提供 2D 底盤移動模擬。

    Attributes:
        position: 機器人在 2D 地圖上的座標 (x, y)，單位為公尺。
        heading: 機器人朝向角度，單位為度（0 度為正 x 方向，逆時針為正）。
        speed: 底盤移動速度，單位為 m/s。
    """

    def __init__(
        self,
        position: tuple[float, float] = (0.0, 0.0),
        heading: float = 0.0,
        speed: float = 0.5,
        use_webcam: bool = False,
    ) -> None:
        """初始化 MockReachyMini。

        Args:
            position: 初始 2D 座標 (x, y)，單位為公尺。
            heading: 初始朝向角度，單位為度。
            speed: 底盤移動速度，單位為 m/s。
            use_webcam: 是否讓 MockMedia 使用 webcam。
        """
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

        logger.info(
            "MockReachyMini 已初始化：位置=(%.2f, %.2f)，朝向=%.1f°",
            position[0],
            position[1],
            heading,
        )

    @property
    def position(self) -> tuple[float, float]:
        """機器人在 2D 地圖上的座標 (x, y)，單位為公尺。"""
        return self._position

    @position.setter
    def position(self, value: tuple[float, float]) -> None:
        self._position = value

    @property
    def heading(self) -> float:
        """機器人朝向角度，單位為度（0 度為正 x 方向，逆時針為正）。"""
        return self._heading

    @heading.setter
    def heading(self, value: float) -> None:
        self._heading = value

    @property
    def media(self) -> MockMedia:
        """取得 MockMedia 實例，用於存取相機和音訊介面。"""
        return self._media

    @property
    def antenna_pos(self) -> list[float]:
        """當前天線角度 [right, left]，單位為弧度。"""
        return self._antenna_pos.copy()

    @property
    def head_pose(self) -> npt.NDArray[np.float64]:
        """當前頭部姿態，4x4 齊次轉換矩陣。"""
        return self._head_pose.copy()

    @property
    def body_yaw(self) -> float:
        """當前身體偏轉角度，單位為弧度。"""
        return self._body_yaw

    def set_target(
        self,
        head: npt.NDArray[np.float64] | None = None,
        antennas: npt.NDArray[np.float64] | list[float] | None = None,
        body_yaw: float | None = None,
    ) -> None:
        """設定機器人各部位的目標姿態。

        與 reachy_mini.ReachyMini.set_target 介面相容。
        所有參數皆為可選，至少需提供一個。

        Args:
            head: 4x4 齊次轉換矩陣，表示頭部目標姿態。
            antennas: 長度為 2 的陣列 [right, left]，天線目標角度（弧度）。
            body_yaw: 身體偏轉目標角度（弧度）。

        Raises:
            ValueError: 若三個參數皆為 None，或參數格式不正確。
        """
        if head is None and antennas is None and body_yaw is None:
            raise ValueError(
                "至少需提供 head、antennas 或 body_yaw 其中之一。"
            )

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
        """設定底盤移動目標座標。

        機器人會在 update_position() 呼叫時朝目標直線移動。
        到達目標後會自動清除移動目標。

        Args:
            x: 目標 x 座標（公尺）。
            y: 目標 y 座標（公尺）。
        """
        self._move_target = (x, y)
        # 計算朝向角度（朝向目標方向）
        dx = x - self.position[0]
        dy = y - self.position[1]
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            self.heading = math.degrees(math.atan2(dy, dx))
        logger.info(
            "move_to: 目標=(%.2f, %.2f)，朝向=%.1f°",
            x,
            y,
            self.heading,
        )

    def update_position(self, dt: float) -> bool:
        """更新底盤位置，模擬等速直線移動。

        根據時間差 dt 和目前速度，將機器人朝目標方向移動。
        若無移動目標或已到達，回傳 False。

        Args:
            dt: 時間差（秒）。

        Returns:
            True 表示仍在移動中，False 表示已到達或無目標。
        """
        if self._move_target is None:
            return False

        tx, ty = self._move_target
        px, py = self.position

        dx = tx - px
        dy = ty - py
        distance = math.sqrt(dx * dx + dy * dy)

        step = self.speed * dt

        if distance <= step:
            # 已到達目標
            self.position = (tx, ty)
            self._move_target = None
            logger.info("已到達目標座標 (%.2f, %.2f)", tx, ty)
            return False

        # 朝目標等速移動
        ratio = step / distance
        new_x = px + dx * ratio
        new_y = py + dy * ratio
        self.position = (new_x, new_y)
        self.heading = math.degrees(math.atan2(dy, dx))
        return True

    @property
    def is_moving(self) -> bool:
        """機器人是否正在移動中。"""
        return self._move_target is not None

    def get_state_summary(self) -> dict[str, Any]:
        """取得機器人所有狀態的摘要。

        回傳包含各部位狀態、底盤位置、以及歷史紀錄數量的字典，
        適合用於終端顯示或偵錯。

        Returns:
            包含以下鍵值的字典：
            - position: (x, y) 座標
            - heading: 朝向角度（度）
            - antenna_pos: [right, left] 天線角度（弧度）
            - antenna_pos_deg: [right, left] 天線角度（度）
            - head_yaw_deg: 頭部偏轉角度（度）
            - head_pitch_deg: 頭部俯仰角度（度）
            - body_yaw: 身體偏轉角度（弧度）
            - body_yaw_deg: 身體偏轉角度（度）
            - move_target: 移動目標座標或 None
            - is_moving: 是否正在移動
            - audio_playing: 是否正在播放音訊
            - log_count: 歷史紀錄數量
        """
        # 從 4x4 齊次矩陣中提取 yaw 和 pitch（歐拉角）
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
        }

    def _extract_head_angles(self) -> tuple[float, float]:
        """從頭部 4x4 齊次矩陣中提取 yaw 和 pitch 角度（度）。

        Returns:
            (yaw_deg, pitch_deg) 元組。
        """
        try:
            from scipy.spatial.transform import Rotation as R

            rot_matrix = self._head_pose[:3, :3]
            euler = R.from_matrix(rot_matrix).as_euler("xyz", degrees=True)
            # euler = [roll, pitch, yaw]
            return float(euler[2]), float(euler[1])
        except (ImportError, ValueError):
            # 若無 scipy，使用簡易方式估算
            # 從旋轉矩陣直接提取近似值
            r = self._head_pose[:3, :3]
            yaw = math.degrees(math.atan2(r[1, 0], r[0, 0]))
            pitch = math.degrees(math.asin(-r[2, 0]))
            return yaw, pitch

    def close(self) -> None:
        """釋放所有資源。"""
        self._media.close()
        logger.info("MockReachyMini 已關閉")
