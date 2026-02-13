"""測試喚醒/睡眠與馬達控制功能。"""

import numpy as np
import pytest

from reachy_mini_simulator.mock_robot import MockReachyMini, MOTOR_NAMES


class TestWakeSleep:
    """測試 wake_up / goto_sleep 狀態切換。"""

    def test_initially_awake(self):
        """初始狀態為已喚醒。"""
        robot = MockReachyMini()
        assert robot.is_awake

    def test_goto_sleep(self):
        """goto_sleep 後不再喚醒。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        assert not robot.is_awake

    def test_wake_up_after_sleep(self):
        """睡眠後可重新喚醒。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        robot.wake_up()
        assert robot.is_awake

    def test_sleep_disables_motors(self):
        """進入睡眠後所有馬達停用。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        for name in MOTOR_NAMES:
            assert not robot.is_motor_enabled(name)

    def test_wake_enables_motors(self):
        """喚醒後所有馬達啟用。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        robot.wake_up()
        for name in MOTOR_NAMES:
            assert robot.is_motor_enabled(name)


class TestSetTargetGuard:
    """測試未喚醒時 set_target 不生效。"""

    def test_set_target_skipped_when_asleep(self):
        """睡眠時 set_target 不改變狀態。"""
        robot = MockReachyMini()
        robot.set_target(body_yaw=1.0)
        assert robot.body_yaw == pytest.approx(1.0)

        robot.goto_sleep()
        robot.set_target(body_yaw=2.0)
        # 應維持 1.0（被跳過）
        assert robot.body_yaw == pytest.approx(1.0)

    def test_set_target_works_after_wake(self):
        """重新喚醒後 set_target 正常運作。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        robot.set_target(body_yaw=2.0)
        assert robot.body_yaw == pytest.approx(0.0)  # 沒變

        robot.wake_up()
        robot.set_target(body_yaw=2.0)
        assert robot.body_yaw == pytest.approx(2.0)

    def test_set_target_validation_still_runs(self):
        """即使睡眠，參數驗證仍然執行。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        with pytest.raises(ValueError, match="至少需提供"):
            robot.set_target()


class TestMotorControl:
    """測試馬達啟用/停用。"""

    def test_all_motors_enabled_initially(self):
        """所有馬達初始啟用。"""
        robot = MockReachyMini()
        for name in MOTOR_NAMES:
            assert robot.is_motor_enabled(name)

    def test_disable_motor(self):
        """停用指定馬達。"""
        robot = MockReachyMini()
        robot.set_motor_enabled("head_yaw", False)
        assert not robot.is_motor_enabled("head_yaw")
        # 其他馬達不受影響
        assert robot.is_motor_enabled("head_pitch")

    def test_enable_motor(self):
        """重新啟用馬達。"""
        robot = MockReachyMini()
        robot.set_motor_enabled("head_yaw", False)
        robot.set_motor_enabled("head_yaw", True)
        assert robot.is_motor_enabled("head_yaw")

    def test_unknown_motor_raises(self):
        """未知馬達名稱拋出 ValueError。"""
        robot = MockReachyMini()
        with pytest.raises(ValueError, match="未知的馬達名稱"):
            robot.set_motor_enabled("nonexistent", True)

    def test_is_motor_enabled_unknown_raises(self):
        """查詢未知馬達名稱拋出 ValueError。"""
        robot = MockReachyMini()
        with pytest.raises(ValueError, match="未知的馬達名稱"):
            robot.is_motor_enabled("nonexistent")


class TestGravityCompensation:
    """測試重力補償。"""

    def test_set_gravity_compensation(self):
        """啟用/停用重力補償不拋出錯誤。"""
        robot = MockReachyMini()
        robot.set_gravity_compensation(True)
        robot.set_gravity_compensation(False)
