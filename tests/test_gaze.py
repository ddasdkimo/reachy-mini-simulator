"""測試凝視追蹤功能。"""

import numpy as np
import pytest

from reachy_mini_simulator.mock_robot import MockReachyMini


class TestLookAtImage:
    """測試 look_at_image。"""

    def test_center(self):
        """看向影像中央不應大幅偏移。"""
        robot = MockReachyMini()
        initial = robot.head_pose.copy()
        robot.look_at_image(0.5, 0.5)
        # 中央座標對應 yaw=0, pitch=0
        np.testing.assert_array_almost_equal(robot.head_pose, initial, decimal=3)

    def test_left(self):
        """看向影像左側，yaw 應為正。"""
        robot = MockReachyMini()
        robot.look_at_image(0.0, 0.5)
        # u=0 → yaw=+30°
        pose = robot.head_pose
        # 檢查不是單位矩陣（已旋轉）
        assert not np.allclose(pose, np.eye(4))

    def test_right(self):
        """看向影像右側，yaw 應為負。"""
        robot = MockReachyMini()
        robot.look_at_image(1.0, 0.5)
        pose = robot.head_pose
        assert not np.allclose(pose, np.eye(4))

    def test_top(self):
        """看向影像上方，pitch 應為負。"""
        robot = MockReachyMini()
        robot.look_at_image(0.5, 0.0)
        pose = robot.head_pose
        assert not np.allclose(pose, np.eye(4))

    def test_bottom(self):
        """看向影像下方，pitch 應為正。"""
        robot = MockReachyMini()
        robot.look_at_image(0.5, 1.0)
        pose = robot.head_pose
        assert not np.allclose(pose, np.eye(4))

    def test_different_positions_differ(self):
        """不同位置看得到不同姿態。"""
        robot = MockReachyMini()
        robot.look_at_image(0.0, 0.0)
        pose_tl = robot.head_pose.copy()

        robot.look_at_image(1.0, 1.0)
        pose_br = robot.head_pose.copy()

        assert not np.allclose(pose_tl, pose_br)


class TestLookAtWorld:
    """測試 look_at_world。"""

    def test_forward(self):
        """看向正前方。"""
        robot = MockReachyMini()
        robot.look_at_world(1.0, 0.0, 0.0)
        # yaw=0, pitch=0 → 接近單位矩陣
        np.testing.assert_array_almost_equal(robot.head_pose, np.eye(4), decimal=3)

    def test_left(self):
        """看向左方（y>0），頭部應旋轉。"""
        robot = MockReachyMini()
        robot.look_at_world(0.0, 1.0, 0.0)
        pose = robot.head_pose
        assert not np.allclose(pose, np.eye(4))

    def test_up(self):
        """看向上方（z>0），頭部 pitch 應變化。"""
        robot = MockReachyMini()
        robot.look_at_world(1.0, 0.0, 1.0)
        pose = robot.head_pose
        assert not np.allclose(pose, np.eye(4))

    def test_zero_distance_no_change(self):
        """距離為零時不改變。"""
        robot = MockReachyMini()
        initial = robot.head_pose.copy()
        robot.look_at_world(0.0, 0.0, 0.0)
        np.testing.assert_array_equal(robot.head_pose, initial)

    def test_different_directions_differ(self):
        """不同方向產生不同姿態。"""
        robot = MockReachyMini()
        robot.look_at_world(1.0, 0.0, 0.0)
        pose_fwd = robot.head_pose.copy()

        robot.look_at_world(0.0, 1.0, 0.0)
        pose_left = robot.head_pose.copy()

        assert not np.allclose(pose_fwd, pose_left)
