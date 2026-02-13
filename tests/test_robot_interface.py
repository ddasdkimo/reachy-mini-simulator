"""測試 RobotInterface / MediaInterface / PersonDetectorInterface 抽象介面的合規性。

確認 MockReachyMini、MockMedia、MockPersonDetector、YOLOPersonDetector
正確實作了各自抽象介面的所有方法。
"""

from abc import ABC

import numpy as np
import pytest

from reachy_mini_simulator.robot_interface import RobotInterface, MediaInterface
from reachy_mini_simulator.mock_robot import MockReachyMini
from reachy_mini_simulator.mock_media import MockMedia
from reachy_mini_simulator.person_detector import (
    PersonDetectorInterface,
    MockPersonDetector,
    YOLOPersonDetector,
)


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


# ── Phase 1-3 新增介面合規測試 ────────────────────────────────────

class TestNewRobotInterfaceCompliance:
    """測試 MockReachyMini 實作所有 Phase 1-3 新增的 RobotInterface 方法。"""

    def test_goto_target_exists(self):
        """goto_target 方法存在且可呼叫。"""
        robot = MockReachyMini()
        assert hasattr(robot, "goto_target")
        robot.goto_target(antennas=[0.1, 0.2], duration=0.5)

    def test_get_current_joint_positions_exists(self):
        """get_current_joint_positions 回傳 dict。"""
        robot = MockReachyMini()
        result = robot.get_current_joint_positions()
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_look_at_image_exists(self):
        """look_at_image 可呼叫不拋出錯誤。"""
        robot = MockReachyMini()
        robot.look_at_image(0.5, 0.5)

    def test_look_at_world_exists(self):
        """look_at_world 可呼叫不拋出錯誤。"""
        robot = MockReachyMini()
        robot.look_at_world(1.0, 0.0, 0.0)

    def test_wake_up_exists(self):
        """wake_up 後 is_awake 為 True。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        robot.wake_up()
        assert robot.is_awake

    def test_goto_sleep_exists(self):
        """goto_sleep 後 is_awake 為 False。"""
        robot = MockReachyMini()
        robot.goto_sleep()
        assert not robot.is_awake

    def test_motor_control_exists(self):
        """set_motor_enabled / is_motor_enabled 方法存在。"""
        robot = MockReachyMini()
        assert hasattr(robot, "set_motor_enabled")
        assert hasattr(robot, "is_motor_enabled")
        robot.set_motor_enabled("head_yaw", False)
        assert not robot.is_motor_enabled("head_yaw")

    def test_gravity_compensation_exists(self):
        """set_gravity_compensation 可呼叫。"""
        robot = MockReachyMini()
        robot.set_gravity_compensation(True)
        robot.set_gravity_compensation(False)

    def test_get_imu_data_exists(self):
        """get_imu_data 回傳包含必要鍵值的 dict。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        assert isinstance(data, dict)
        assert "accelerometer" in data
        assert "gyroscope" in data
        assert "quaternion" in data

    def test_motion_recording_exists(self):
        """start_motion_recording / stop_motion_recording 存在。"""
        robot = MockReachyMini()
        assert hasattr(robot, "start_motion_recording")
        assert hasattr(robot, "stop_motion_recording")
        robot.start_motion_recording()
        move = robot.stop_motion_recording()
        assert move is not None

    def test_motion_playing_exists(self):
        """play_motion / is_motion_playing 存在。"""
        robot = MockReachyMini()
        assert hasattr(robot, "play_motion")
        assert hasattr(robot, "is_motion_playing")
        assert isinstance(robot.is_motion_playing, bool)


class TestNewMediaInterfaceCompliance:
    """測試 MockMedia 實作所有 Phase 2 新增的 MediaInterface 方法。"""

    def test_play_sound_exists(self):
        """play_sound 方法存在。"""
        media = MockMedia()
        assert hasattr(media, "play_sound")
        media.play_sound("/tmp/test.wav")

    def test_is_sound_playing_exists(self):
        """is_sound_playing 方法存在且回傳 bool。"""
        media = MockMedia()
        result = media.is_sound_playing()
        assert isinstance(result, bool)

    def test_stop_sound_exists(self):
        """stop_sound 方法存在。"""
        media = MockMedia()
        assert hasattr(media, "stop_sound")
        media.stop_sound()

    def test_recording_exists(self):
        """start_recording / stop_recording / is_recording 存在。"""
        media = MockMedia()
        assert hasattr(media, "start_recording")
        assert hasattr(media, "stop_recording")
        assert isinstance(media.is_recording, bool)

    def test_get_audio_sample_exists(self):
        """get_audio_sample 存在。"""
        media = MockMedia()
        assert hasattr(media, "get_audio_sample")
        result = media.get_audio_sample()
        assert result is None  # 未錄音時回傳 None

    def test_get_doa_exists(self):
        """get_doa 回傳 float。"""
        media = MockMedia()
        doa = media.get_doa()
        assert isinstance(doa, float)
        assert 0.0 <= doa <= 360.0


# ── PersonDetectorInterface 合規測試 ─────────────────────────────

class TestPersonDetectorInterfaceCompliance:
    """驗證 PersonDetectorInterface 的所有實作都完整實作了抽象方法。"""

    def test_mock_detector_implements_all_methods(self):
        """MockPersonDetector 實作所有抽象方法。"""
        detector = MockPersonDetector()
        # 生命週期
        detector.start()
        assert detector.is_running
        detector.stop()
        assert not detector.is_running

        # 屬性
        assert isinstance(detector.person_visible, bool)
        assert isinstance(detector.person_count, int)
        assert isinstance(detector.person_positions, list)
        assert isinstance(detector.get_person_absence_duration(), float)

        # 更新
        detector.update(0.1)

    def test_yolo_detector_implements_all_methods(self):
        """YOLOPersonDetector 實作所有抽象方法（不啟動執行緒）。"""
        media = MockMedia()
        detector = YOLOPersonDetector(media=media)

        # 屬性（不需 start 就能查詢）
        assert isinstance(detector.is_running, bool)
        assert isinstance(detector.person_visible, bool)
        assert isinstance(detector.person_count, int)
        assert isinstance(detector.person_positions, list)
        assert isinstance(detector.get_person_absence_duration(), float)

        # 更新（YOLO update 為空操作）
        detector.update(0.1)

        # stop 不報錯（即使未 start）
        detector.stop()
        assert not detector.is_running

    def test_mock_detector_is_subclass(self):
        """MockPersonDetector 是 PersonDetectorInterface 的子類。"""
        assert issubclass(MockPersonDetector, PersonDetectorInterface)

    def test_yolo_detector_is_subclass(self):
        """YOLOPersonDetector 是 PersonDetectorInterface 的子類。"""
        assert issubclass(YOLOPersonDetector, PersonDetectorInterface)

    def test_mock_detector_instance_check(self):
        """MockPersonDetector 實例通過 isinstance 檢查。"""
        detector = MockPersonDetector()
        assert isinstance(detector, PersonDetectorInterface)

    def test_yolo_detector_instance_check(self):
        """YOLOPersonDetector 實例通過 isinstance 檢查。"""
        media = MockMedia()
        detector = YOLOPersonDetector(media=media)
        assert isinstance(detector, PersonDetectorInterface)

    def test_person_detector_interface_abstract(self):
        """PersonDetectorInterface 無法直接實例化。"""
        with pytest.raises(TypeError):
            PersonDetectorInterface()
