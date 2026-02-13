"""插值引擎 - 提供多種插值方法與動畫管理。"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass

import numpy as np


class InterpolationMethod(Enum):
    MIN_JERK = "MIN_JERK"
    LINEAR = "LINEAR"
    EASE = "EASE"
    CARTOON = "CARTOON"


def interpolate(t: float, method: InterpolationMethod) -> float:
    """計算插值進度值 0.0~1.0。

    Args:
        t: 原始進度值 0.0~1.0。
        method: 插值方法。

    Returns:
        經過插值曲線轉換後的進度值。
    """
    t = max(0.0, min(1.0, t))
    if method == InterpolationMethod.LINEAR:
        return t
    elif method == InterpolationMethod.MIN_JERK:
        # 最小急動度（最平滑）: 10t^3 - 15t^4 + 6t^5
        return 10 * t**3 - 15 * t**4 + 6 * t**5
    elif method == InterpolationMethod.EASE:
        # 緩入緩出
        return t * t * (3 - 2 * t)
    elif method == InterpolationMethod.CARTOON:
        # 過衝後回彈
        if t < 0.7:
            return 1.2 * (t / 0.7) ** 2
        else:
            p = (t - 0.7) / 0.3
            return 1.2 - 0.2 * p
    return t


@dataclass
class InterpolationTarget:
    """插值目標。"""

    start_head: np.ndarray | None = None
    end_head: np.ndarray | None = None
    start_antennas: list[float] | None = None
    end_antennas: list[float] | None = None
    start_body_yaw: float | None = None
    end_body_yaw: float | None = None
    duration: float = 1.0
    method: InterpolationMethod = InterpolationMethod.MIN_JERK
    elapsed: float = 0.0

    @property
    def is_done(self) -> bool:
        return self.elapsed >= self.duration

    @property
    def progress(self) -> float:
        if self.duration <= 0:
            return 1.0
        return min(self.elapsed / self.duration, 1.0)


class InterpolationEngine:
    """管理進行中的插值動畫。"""

    def __init__(self) -> None:
        self._active: InterpolationTarget | None = None

    def start(self, target: InterpolationTarget) -> None:
        """開始新的插值動畫。"""
        self._active = target

    def tick(self, dt: float) -> dict | None:
        """推進插值，回傳當前插值結果或 None（無動畫）。

        Args:
            dt: 時間差（秒）。

        Returns:
            包含 head / antennas / body_yaw 的字典，或 None。
        """
        if self._active is None or self._active.is_done:
            self._active = None
            return None

        self._active.elapsed += dt
        t = interpolate(self._active.progress, self._active.method)

        result: dict = {}
        if self._active.start_head is not None and self._active.end_head is not None:
            result["head"] = (1 - t) * self._active.start_head + t * self._active.end_head
        if self._active.start_antennas is not None and self._active.end_antennas is not None:
            result["antennas"] = [
                (1 - t) * s + t * e
                for s, e in zip(self._active.start_antennas, self._active.end_antennas)
            ]
        if self._active.start_body_yaw is not None and self._active.end_body_yaw is not None:
            result["body_yaw"] = (1 - t) * self._active.start_body_yaw + t * self._active.end_body_yaw

        return result if result else None

    @property
    def is_active(self) -> bool:
        return self._active is not None and not self._active.is_done

    def cancel(self) -> None:
        """取消當前動畫。"""
        self._active = None
