"""動作錄製與回放引擎。"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class JointFrame:
    """一幀關節數據。"""

    timestamp: float
    head_pose: list[list[float]] | None = None  # 4x4 as nested list
    antennas: list[float] | None = None
    body_yaw: float | None = None


@dataclass
class Move:
    """動作序列。"""

    name: str = ""
    frames: list[JointFrame] = field(default_factory=list)

    @property
    def duration(self) -> float:
        if len(self.frames) < 2:
            return 0.0
        return self.frames[-1].timestamp - self.frames[0].timestamp

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "frames": [
                {
                    "timestamp": f.timestamp,
                    "head_pose": f.head_pose,
                    "antennas": f.antennas,
                    "body_yaw": f.body_yaw,
                }
                for f in self.frames
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Move:
        frames = [
            JointFrame(
                timestamp=f["timestamp"],
                head_pose=f.get("head_pose"),
                antennas=f.get("antennas"),
                body_yaw=f.get("body_yaw"),
            )
            for f in data.get("frames", [])
        ]
        return cls(name=data.get("name", ""), frames=frames)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str) -> Move:
        return cls.from_dict(json.loads(s))


class MotionRecorder:
    """動作錄製器。"""

    def __init__(self) -> None:
        self._frames: list[JointFrame] = []
        self._recording = False
        self._start_time = 0.0

    def start(self) -> None:
        """開始錄製。"""
        self._frames = []
        self._recording = True
        self._start_time = time.time()

    def capture(self, robot) -> None:
        """擷取當前機器人狀態為一幀。"""
        if not self._recording:
            return
        frame = JointFrame(
            timestamp=time.time() - self._start_time,
            head_pose=robot.head_pose.tolist(),
            antennas=robot.antenna_pos,
            body_yaw=robot.body_yaw,
        )
        self._frames.append(frame)

    def stop(self) -> Move:
        """停止錄製並回傳 Move。"""
        self._recording = False
        return Move(frames=self._frames.copy())

    @property
    def is_recording(self) -> bool:
        return self._recording


class MotionPlayer:
    """動作回放器。"""

    def __init__(self) -> None:
        self._move: Move | None = None
        self._playing = False
        self._elapsed = 0.0
        self._speed = 1.0
        self._frame_index = 0

    def play(self, move: Move, speed: float = 1.0) -> None:
        """開始回放動作序列。"""
        self._move = move
        self._speed = speed
        self._elapsed = 0.0
        self._frame_index = 0
        self._playing = True if move.frames else False

    def tick(self, dt: float, robot) -> None:
        """推進回放，套用幀到機器人。"""
        if not self._playing or not self._move or not self._move.frames:
            return

        self._elapsed += dt * self._speed

        # 找到當前時間對應的幀
        while (
            self._frame_index < len(self._move.frames) - 1
            and self._move.frames[self._frame_index + 1].timestamp <= self._elapsed
        ):
            self._frame_index += 1

        frame = self._move.frames[self._frame_index]

        kwargs: dict = {}
        if frame.head_pose is not None:
            kwargs["head"] = np.array(frame.head_pose)
        if frame.antennas is not None:
            kwargs["antennas"] = frame.antennas
        if frame.body_yaw is not None:
            kwargs["body_yaw"] = frame.body_yaw

        if kwargs:
            robot.set_target(**kwargs)

        # 檢查是否播放完畢
        if self._elapsed >= self._move.duration:
            self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    def stop(self) -> None:
        """停止回放。"""
        self._playing = False
