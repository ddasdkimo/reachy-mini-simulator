"""表情引擎 - 以情緒標籤驅動天線與頭部動畫。

將 AI 大腦產生的情緒標籤（高興、驚訝、思考等）映射到
MockReachyMini 的天線角度與頭部姿態，產生生動的表情動作。

支援兩層動畫：
1. 底層狀態動畫（IDLE / LISTENING / PROCESSING / SPEAKING）持續播放
2. 情緒動畫覆蓋層：由 trigger_emotion() 觸發，播放一段固定時長後回到狀態動畫

參考自 reachy_mini_chat/expression.py，適配 MockReachyMini 的 set_target 介面。
"""

from __future__ import annotations

import math
import time

import numpy as np

# 天線最大角度（度），轉換為弧度
ANTENNA_MAX_DEG = 35.0
ANTENNA_MAX_RAD = math.radians(ANTENNA_MAX_DEG)


def _create_head_pose(
    yaw: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
    degrees: bool = True,
) -> np.ndarray:
    """建立 4x4 齊次轉換矩陣表示頭部姿態。

    這是 reachy_mini.utils.create_head_pose 的簡化版本，
    不依賴 scipy，直接用旋轉矩陣計算。

    Args:
        yaw: 偏轉角（繞 z 軸）。
        pitch: 俯仰角（繞 y 軸）。
        roll: 翻滾角（繞 x 軸）。
        degrees: 若為 True，角度以度為單位。

    Returns:
        4x4 齊次轉換矩陣。
    """
    if degrees:
        roll = math.radians(roll)
        pitch = math.radians(pitch)
        yaw = math.radians(yaw)

    # Rz(yaw) * Ry(pitch) * Rx(roll)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    rot = np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp,     cp * sr,                cp * cr               ],
    ])

    pose = np.eye(4)
    pose[:3, :3] = rot
    return pose


class ExpressionEngine:
    """表情引擎 - 根據狀態與情緒驅動天線和頭部動畫。

    用法::

        expr = ExpressionEngine()
        expr.set_state("LISTENING")
        expr.trigger_emotion("高興")

        # 在主迴圈中每幀呼叫 update
        expr.update(robot)  # robot 為 MockReachyMini 實例

    Attributes:
        state: 當前機器人狀態（IDLE / LISTENING / PROCESSING / SPEAKING）。
    """

    def __init__(self) -> None:
        self.state: str = "IDLE"
        self._emotion: str | None = None
        self._emotion_start: float = 0.0
        self._emotion_duration: float = 1.5  # 秒
        self._start_time: float = time.time()

    def set_state(self, state: str) -> None:
        """設定底層動畫狀態。

        Args:
            state: 狀態名稱，可為 "IDLE"、"LISTENING"、
                   "PROCESSING"、"SPEAKING"。
        """
        self.state = state

    def trigger_emotion(self, emotion: str) -> None:
        """觸發情緒動畫覆蓋。

        播放一段對應情緒的動畫（約 1.5 秒），結束後自動回到狀態動畫。

        Args:
            emotion: 情緒名稱，如 "高興"、"驚訝"、"思考" 等。
        """
        self._emotion = emotion
        self._emotion_start = time.time()

    def update(self, robot) -> None:
        """每幀更新，計算並套用天線與頭部目標。

        根據當前狀態或情緒覆蓋計算動畫值，並透過
        robot.set_target() 套用到 MockReachyMini。

        Args:
            robot: MockReachyMini 實例（或任何具有 set_target 方法的物件）。
        """
        now = time.time()
        t = now - self._start_time

        # 檢查情緒動畫是否仍在播放
        emotion_active = (
            self._emotion is not None
            and (now - self._emotion_start) < self._emotion_duration
        )

        if emotion_active:
            left, right, yaw, pitch = self._emotion_animation(
                self._emotion, now - self._emotion_start
            )
        else:
            self._emotion = None
            left, right, yaw, pitch = self._state_animation(t)

        head = _create_head_pose(yaw=yaw, pitch=pitch, degrees=True)
        robot.set_target(antennas=[left, right], head=head)

    def _state_animation(self, t: float) -> tuple[float, float, float, float]:
        """底層狀態動畫。

        Args:
            t: 自引擎啟動以來的經過時間（秒）。

        Returns:
            (left_antenna, right_antenna, yaw_deg, pitch_deg) 元組。
            天線值為弧度，yaw/pitch 為度。
        """
        amp = ANTENNA_MAX_RAD

        if self.state == "IDLE":
            # 呼吸效果：緩慢、微幅擺動
            angle = amp * 0.15 * math.sin(2 * math.pi * 0.3 * t)
            return (angle, angle, 0.0, 0.0)

        elif self.state == "LISTENING":
            # 警覺：天線豎起，微微前傾
            angle = amp * 0.4 + amp * 0.1 * math.sin(2 * math.pi * 2.0 * t)
            return (angle, angle, 0.0, -5.0)

        elif self.state == "PROCESSING":
            # 思考：天線交替傾斜
            left = amp * 0.3 * math.sin(2 * math.pi * 0.8 * t)
            right = amp * 0.3 * math.sin(2 * math.pi * 0.8 * t + math.pi)
            yaw = 5.0 * math.sin(2 * math.pi * 0.4 * t)
            return (left, right, yaw, -3.0)

        elif self.state == "SPEAKING":
            # 節奏：隨說話輕微擺動
            left = amp * 0.25 * math.sin(2 * math.pi * 1.5 * t)
            right = -left
            pitch = 3.0 * math.sin(2 * math.pi * 1.0 * t)
            return (left, right, 0.0, pitch)

        return (0.0, 0.0, 0.0, 0.0)

    def _emotion_animation(
        self, emotion: str, elapsed: float
    ) -> tuple[float, float, float, float]:
        """情緒覆蓋動畫。

        Args:
            emotion: 情緒名稱。
            elapsed: 自情緒觸發以來的經過時間（秒）。

        Returns:
            (left_antenna, right_antenna, yaw_deg, pitch_deg) 元組。
        """
        amp = ANTENNA_MAX_RAD
        # 正規化進度 0..1
        p = min(elapsed / self._emotion_duration, 1.0)

        if emotion == "高興":
            # 開心彈跳
            bounce = math.sin(math.pi * p * 4) * (1 - p)
            angle = amp * 0.6 * bounce
            return (angle, angle, 0.0, -5.0 * bounce)

        elif emotion == "驚訝":
            # 驚訝：天線彈起再回落
            spring = math.exp(-3 * p) * math.sin(8 * math.pi * p)
            angle = amp * 0.8 * (1 - p + 0.3 * spring)
            return (angle, angle, 0.0, -8.0 * (1 - p))

        elif emotion == "思考":
            # 思考：歪頭、單邊天線抬起
            tilt = 15.0 * math.sin(math.pi * p * 0.5)
            left = amp * 0.2
            right = amp * 0.5 * math.sin(math.pi * p)
            return (left, right, tilt, -5.0)

        elif emotion == "同意":
            # 點頭
            nod = -10.0 * abs(math.sin(math.pi * p * 3))
            angle = amp * 0.3
            return (angle, angle, 0.0, nod)

        elif emotion == "不同意":
            # 搖頭
            shake = 15.0 * math.sin(math.pi * p * 4)
            angle = amp * 0.2
            return (angle, -angle, shake, 0.0)

        elif emotion == "興奮":
            # 興奮：天線快速搖擺
            speed = 6.0
            left = amp * 0.7 * math.sin(2 * math.pi * speed * p)
            right = amp * 0.7 * math.sin(2 * math.pi * speed * p + math.pi * 0.5)
            return (left, right, 0.0, -3.0 * math.sin(math.pi * p * 2))

        elif emotion == "撒嬌":
            # 撒嬌：輕微歪頭搖擺
            tilt = 12.0 * math.sin(math.pi * p)
            angle = amp * 0.4 * math.sin(2 * math.pi * 1.5 * p)
            return (angle, -angle, tilt, -5.0 * math.sin(math.pi * p))

        elif emotion == "好奇":
            # 好奇：頭前傾、天線豎起
            perk = amp * 0.6 * (1 - math.exp(-5 * p))
            tilt = 8.0 * math.sin(math.pi * p * 0.5)
            return (perk, perk, tilt, -8.0 * (1 - math.exp(-3 * p)))

        # 預設：中性
        return (0.0, 0.0, 0.0, 0.0)
