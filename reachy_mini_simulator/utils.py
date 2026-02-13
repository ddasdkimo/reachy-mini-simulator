"""工具函式 - 共用的數學與轉換工具。"""

import math

import numpy as np


def create_head_pose(
    yaw: float = 0.0,
    pitch: float = 0.0,
    roll: float = 0.0,
    degrees: bool = True,
) -> np.ndarray:
    """建立 4x4 齊次轉換矩陣表示頭部姿態。

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
