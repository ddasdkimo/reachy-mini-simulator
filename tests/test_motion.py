"""測試動作錄製與回放。"""

import json
import time

import numpy as np
import pytest

from reachy_mini_simulator.motion import JointFrame, Move, MotionRecorder, MotionPlayer
from reachy_mini_simulator.mock_robot import MockReachyMini


class TestJointFrame:
    """測試 JointFrame dataclass。"""

    def test_create(self):
        frame = JointFrame(timestamp=0.0)
        assert frame.timestamp == 0.0
        assert frame.head_pose is None
        assert frame.antennas is None
        assert frame.body_yaw is None

    def test_create_with_data(self):
        frame = JointFrame(
            timestamp=1.0,
            head_pose=np.eye(4).tolist(),
            antennas=[0.1, 0.2],
            body_yaw=0.5,
        )
        assert frame.timestamp == 1.0
        assert frame.antennas == [0.1, 0.2]
        assert frame.body_yaw == 0.5


class TestMove:
    """測試 Move class。"""

    def test_empty_duration(self):
        """空 Move 的 duration 為 0。"""
        move = Move()
        assert move.duration == 0.0

    def test_single_frame_duration(self):
        """單幀 Move 的 duration 為 0。"""
        move = Move(frames=[JointFrame(timestamp=0.0)])
        assert move.duration == 0.0

    def test_multi_frame_duration(self):
        """多幀 Move 的 duration 正確。"""
        move = Move(frames=[
            JointFrame(timestamp=0.0),
            JointFrame(timestamp=1.0),
            JointFrame(timestamp=2.5),
        ])
        assert move.duration == pytest.approx(2.5)

    def test_to_dict(self):
        """to_dict 正確序列化。"""
        move = Move(
            name="test",
            frames=[JointFrame(timestamp=0.0, body_yaw=1.0)],
        )
        d = move.to_dict()
        assert d["name"] == "test"
        assert len(d["frames"]) == 1
        assert d["frames"][0]["body_yaw"] == 1.0

    def test_from_dict(self):
        """from_dict 正確反序列化。"""
        data = {
            "name": "wave",
            "frames": [
                {"timestamp": 0.0, "antennas": [0.1, 0.2]},
                {"timestamp": 0.5, "antennas": [0.3, 0.4]},
            ],
        }
        move = Move.from_dict(data)
        assert move.name == "wave"
        assert len(move.frames) == 2
        assert move.frames[1].antennas == [0.3, 0.4]

    def test_json_roundtrip(self):
        """to_json / from_json 往返一致。"""
        move = Move(
            name="nod",
            frames=[
                JointFrame(timestamp=0.0, body_yaw=0.0),
                JointFrame(timestamp=1.0, body_yaw=0.5),
            ],
        )
        json_str = move.to_json()
        restored = Move.from_json(json_str)
        assert restored.name == "nod"
        assert len(restored.frames) == 2
        assert restored.frames[1].body_yaw == pytest.approx(0.5)

    def test_from_dict_missing_fields(self):
        """缺少欄位不會報錯。"""
        data = {"frames": [{"timestamp": 0.0}]}
        move = Move.from_dict(data)
        assert move.name == ""
        assert move.frames[0].head_pose is None


class TestMotionRecorder:
    """測試動作錄製器。"""

    def test_not_recording_initially(self):
        recorder = MotionRecorder()
        assert not recorder.is_recording

    def test_start_recording(self):
        recorder = MotionRecorder()
        recorder.start()
        assert recorder.is_recording

    def test_capture_when_not_recording(self):
        """未錄製時 capture 不記錄。"""
        recorder = MotionRecorder()
        robot = MockReachyMini()
        recorder.capture(robot)
        move = recorder.stop()
        assert len(move.frames) == 0

    def test_record_and_stop(self):
        """錄製多幀後停止。"""
        recorder = MotionRecorder()
        robot = MockReachyMini()

        recorder.start()
        recorder.capture(robot)
        robot.set_target(body_yaw=0.5)
        recorder.capture(robot)
        move = recorder.stop()

        assert not recorder.is_recording
        assert len(move.frames) == 2

    def test_start_motion_recording_on_robot(self):
        """透過 MockReachyMini 的 start/stop_motion_recording。"""
        robot = MockReachyMini()
        robot.start_motion_recording()
        # 手動觸發 capture（通常由 tick loop 呼叫）
        robot._motion_recorder.capture(robot)
        move = robot.stop_motion_recording()
        assert len(move.frames) == 1


class TestMotionPlayer:
    """測試動作回放器。"""

    def test_not_playing_initially(self):
        player = MotionPlayer()
        assert not player.is_playing

    def test_play_empty_move(self):
        """回放空 Move 不會啟動。"""
        player = MotionPlayer()
        player.play(Move())
        assert not player.is_playing

    def test_play_and_tick(self):
        """回放帶幀的 Move。"""
        robot = MockReachyMini()
        move = Move(frames=[
            JointFrame(timestamp=0.0, body_yaw=0.0),
            JointFrame(timestamp=1.0, body_yaw=1.0),
        ])

        player = MotionPlayer()
        player.play(move)
        assert player.is_playing

        player.tick(0.5, robot)
        assert player.is_playing

        player.tick(0.6, robot)
        # elapsed=1.1 >= duration=1.0 → 停止
        assert not player.is_playing

    def test_stop(self):
        """手動停止回放。"""
        player = MotionPlayer()
        move = Move(frames=[
            JointFrame(timestamp=0.0, body_yaw=0.0),
            JointFrame(timestamp=10.0, body_yaw=1.0),
        ])
        player.play(move)
        player.stop()
        assert not player.is_playing

    def test_robot_play_motion(self):
        """透過 MockReachyMini 的 play_motion。"""
        robot = MockReachyMini()
        move = Move(frames=[
            JointFrame(timestamp=0.0, body_yaw=0.0),
            JointFrame(timestamp=1.0, body_yaw=1.0),
        ])
        robot.play_motion(move)
        assert robot.is_motion_playing
