"""測試 RobotInterface / MediaInterface 抽象介面的合規性。

確認 MockReachyMini 和 MockMedia 正確實作了抽象介面的所有方法。
"""

from abc import ABC

import numpy as np
import pytest

from reachy_mini_simulator.robot_interface import RobotInterface, MediaInterface
from reachy_mini_simulator.mock_robot import MockReachyMini
from reachy_mini_simulator.mock_media import MockMedia


# ── 介面繼承檢查 ──────────────────────────────────────────────────

class TestInterfaceInheritance:
    """測試繼承關係。"""

    def test_mock_robot_is_robot_interface(self):
        """MockReachyMini 是 RobotInterface 的子類別。"""
        assert issubclass(MockReachyMini, RobotInterface)

    def test_mock_robot_instance(self):
        """MockReachyMini 實例通過 isinstance 檢查。"""
        robot = MockReachyMini()
        assert isinstance(robot, RobotInterface)

    def test_mock_media_is_media_interface(self):
        """MockMedia 是 MediaInterface 的子類別。"""
        assert issubclass(MockMedia, MediaInterface)

    def test_mock_media_instance(self):
        """MockMedia 實例通過 isinstance 檢查。"""
        media = MockMedia()
        assert isinstance(media, MediaInterface)


# ── RobotInterface 方法合規性 ─────────────────────────────────────

class TestRobotInterfaceCompliance:
    """測試 MockReachyMini 是否正確實作 RobotInterface 的所有方法。"""

    def test_set_target_exists(self):
        """set_target 方法存在且可呼叫。"""
        robot = MockReachyMini()
        robot.set_target(antennas=[0.1, 0.2])

    def test_move_to_exists(self):
        """move_to 方法存在且可呼叫。"""
        robot = MockReachyMini()
        robot.move_to(1.0, 2.0)

    def test_update_position_exists(self):
        """update_position 方法存在且回傳 bool。"""
        robot = MockReachyMini()
        result = robot.update_position(0.1)
        assert isinstance(result, bool)

    def test_is_moving_property(self):
        """is_moving 是 property 且回傳 bool。"""
        robot = MockReachyMini()
        assert isinstance(robot.is_moving, bool)

    def test_position_property(self):
        """position 是可讀寫的 property。"""
        robot = MockReachyMini()
        pos = robot.position
        assert isinstance(pos, tuple)
        assert len(pos) == 2

        robot.position = (5.0, 3.0)
        assert robot.position == (5.0, 3.0)

    def test_heading_property(self):
        """heading 是可讀寫的 property。"""
        robot = MockReachyMini()
        h = robot.heading
        assert isinstance(h, float)

        robot.heading = 45.0
        assert robot.heading == 45.0

    def test_media_property(self):
        """media property 回傳 MediaInterface 實例。"""
        robot = MockReachyMini()
        assert isinstance(robot.media, MediaInterface)

    def test_antenna_pos_property(self):
        """antenna_pos 回傳長度 2 的 list。"""
        robot = MockReachyMini()
        ant = robot.antenna_pos
        assert isinstance(ant, list)
        assert len(ant) == 2

    def test_head_pose_property(self):
        """head_pose 回傳 4x4 numpy array。"""
        robot = MockReachyMini()
        pose = robot.head_pose
        assert pose.shape == (4, 4)

    def test_body_yaw_property(self):
        """body_yaw 回傳 float。"""
        robot = MockReachyMini()
        assert isinstance(robot.body_yaw, float)

    def test_get_state_summary_returns_dict(self):
        """get_state_summary 回傳字典。"""
        robot = MockReachyMini()
        summary = robot.get_state_summary()
        assert isinstance(summary, dict)

    def test_close_exists(self):
        """close 方法存在且可呼叫。"""
        robot = MockReachyMini()
        robot.close()


# ── MediaInterface 方法合規性 ─────────────────────────────────────

class TestMediaInterfaceCompliance:
    """測試 MockMedia 是否正確實作 MediaInterface 的所有方法。"""

    def test_get_frame_returns_array(self):
        """get_frame 回傳 numpy array。"""
        media = MockMedia()
        frame = media.get_frame()
        assert isinstance(frame, np.ndarray)
        assert frame.ndim == 3

    def test_get_output_audio_samplerate_returns_int(self):
        """get_output_audio_samplerate 回傳 int。"""
        media = MockMedia()
        rate = media.get_output_audio_samplerate()
        assert isinstance(rate, int)
        assert rate > 0

    def test_start_stop_playing(self):
        """start_playing 和 stop_playing 可呼叫。"""
        media = MockMedia()
        media.start_playing()
        assert media.is_playing
        media.stop_playing()
        assert not media.is_playing

    def test_push_audio_sample(self):
        """push_audio_sample 接受 float32 array。"""
        media = MockMedia()
        media.start_playing()
        samples = np.zeros(100, dtype=np.float32)
        media.push_audio_sample(samples)

    def test_is_playing_property(self):
        """is_playing 是 property 且回傳 bool。"""
        media = MockMedia()
        assert isinstance(media.is_playing, bool)

    def test_close(self):
        """close 可呼叫。"""
        media = MockMedia()
        media.close()


# ── 不可直接實例化抽象類別 ────────────────────────────────────────

class TestAbstractCannotInstantiate:
    """確認抽象類別無法直接實例化。"""

    def test_robot_interface_abstract(self):
        """RobotInterface 無法直接實例化。"""
        with pytest.raises(TypeError):
            RobotInterface()

    def test_media_interface_abstract(self):
        """MediaInterface 無法直接實例化。"""
        with pytest.raises(TypeError):
            MediaInterface()
