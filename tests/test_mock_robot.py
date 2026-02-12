"""測試 MockReachyMini 機器人模擬。

涵蓋 set_target 驗證、move_to + update_position 移動計算、
狀態摘要、以及 MockMedia 基本功能。
"""

import math

import numpy as np
import pytest

from reachy_mini_simulator.mock_robot import MockReachyMini


# ── 初始化 ────────────────────────────────────────────────────────

class TestInitialization:
    """測試 MockReachyMini 初始化。"""

    def test_default_position(self):
        """預設位置為 (0, 0)。"""
        robot = MockReachyMini()
        assert robot.position == (0.0, 0.0)

    def test_custom_position(self):
        """自訂初始位置。"""
        robot = MockReachyMini(position=(5.0, 3.0))
        assert robot.position == (5.0, 3.0)

    def test_default_heading(self):
        """預設朝向為 0 度。"""
        robot = MockReachyMini()
        assert robot.heading == 0.0

    def test_default_speed(self):
        """預設速度為 0.5。"""
        robot = MockReachyMini()
        assert robot.speed == 0.5

    def test_not_moving_initially(self):
        """初始狀態不在移動中。"""
        robot = MockReachyMini()
        assert not robot.is_moving

    def test_antenna_initial(self):
        """天線初始角度為 [0, 0]。"""
        robot = MockReachyMini()
        assert robot.antenna_pos == [0.0, 0.0]

    def test_head_pose_initial(self):
        """頭部姿態初始為單位矩陣。"""
        robot = MockReachyMini()
        np.testing.assert_array_equal(robot.head_pose, np.eye(4))

    def test_body_yaw_initial(self):
        """身體偏轉初始為 0。"""
        robot = MockReachyMini()
        assert robot.body_yaw == 0.0


# ── set_target 驗證 ───────────────────────────────────────────────

class TestSetTarget:
    """測試 set_target 參數驗證與狀態更新。"""

    def test_set_antennas(self):
        """設定天線角度。"""
        robot = MockReachyMini()
        robot.set_target(antennas=[0.5, -0.3])
        assert robot.antenna_pos == pytest.approx([0.5, -0.3])

    def test_set_body_yaw(self):
        """設定身體偏轉角度。"""
        robot = MockReachyMini()
        robot.set_target(body_yaw=1.2)
        assert robot.body_yaw == pytest.approx(1.2)

    def test_set_head(self):
        """設定頭部姿態矩陣。"""
        robot = MockReachyMini()
        head = np.eye(4) * 2.0
        head[3, 3] = 1.0
        robot.set_target(head=head)
        np.testing.assert_array_equal(robot.head_pose, head)

    def test_set_all_at_once(self):
        """同時設定所有部位。"""
        robot = MockReachyMini()
        robot.set_target(
            head=np.eye(4),
            antennas=[0.1, 0.2],
            body_yaw=0.5,
        )
        assert robot.antenna_pos == pytest.approx([0.1, 0.2])
        assert robot.body_yaw == pytest.approx(0.5)

    def test_no_args_raises(self):
        """三個參數皆為 None 時拋出 ValueError。"""
        robot = MockReachyMini()
        with pytest.raises(ValueError, match="至少需提供"):
            robot.set_target()

    def test_wrong_head_shape_raises(self):
        """head 形狀不是 4x4 時拋出 ValueError。"""
        robot = MockReachyMini()
        with pytest.raises(ValueError, match="4x4"):
            robot.set_target(head=np.eye(3))

    def test_wrong_antennas_length_raises(self):
        """antennas 長度不是 2 時拋出 ValueError。"""
        robot = MockReachyMini()
        with pytest.raises(ValueError, match="長度 2"):
            robot.set_target(antennas=[1.0])

    def test_wrong_body_yaw_type_raises(self):
        """body_yaw 型別不正確時拋出 ValueError。"""
        robot = MockReachyMini()
        with pytest.raises(ValueError, match="數值"):
            robot.set_target(body_yaw="abc")

    def test_state_log_records(self):
        """每次 set_target 都記錄到 state_log。"""
        robot = MockReachyMini()
        assert len(robot.state_log) == 0
        robot.set_target(antennas=[0.1, 0.2])
        assert len(robot.state_log) == 1
        robot.set_target(body_yaw=0.5)
        assert len(robot.state_log) == 2


# ── move_to + update_position 移動計算 ────────────────────────────

class TestMovement:
    """測試底盤移動計算。"""

    def test_move_to_sets_target(self):
        """move_to 設定移動目標。"""
        robot = MockReachyMini(position=(0.0, 0.0))
        robot.move_to(5.0, 0.0)
        assert robot.is_moving

    def test_move_to_updates_heading(self):
        """move_to 更新朝向至目標方向。"""
        robot = MockReachyMini(position=(0.0, 0.0))
        robot.move_to(1.0, 0.0)  # 朝右
        assert robot.heading == pytest.approx(0.0, abs=1.0)

        robot.move_to(0.0, 1.0)  # 朝下（正 y 方向）
        assert robot.heading == pytest.approx(90.0, abs=1.0)

    def test_update_position_moves_toward_target(self):
        """update_position 朝目標移動。"""
        robot = MockReachyMini(position=(0.0, 0.0), speed=1.0)
        robot.move_to(10.0, 0.0)
        robot.update_position(1.0)  # 移動 1 秒

        assert robot.position[0] == pytest.approx(1.0)
        assert robot.position[1] == pytest.approx(0.0)

    def test_update_position_arrives(self):
        """update_position 到達目標後停止。"""
        robot = MockReachyMini(position=(0.0, 0.0), speed=10.0)
        robot.move_to(5.0, 0.0)
        result = robot.update_position(1.0)  # 10 * 1 = 10 > 5，直接到達

        assert result is False
        assert robot.position == (5.0, 0.0)
        assert not robot.is_moving

    def test_update_position_no_target(self):
        """無移動目標時回傳 False。"""
        robot = MockReachyMini()
        result = robot.update_position(1.0)
        assert result is False

    def test_update_position_still_moving(self):
        """尚未到達目標時回傳 True。"""
        robot = MockReachyMini(position=(0.0, 0.0), speed=1.0)
        robot.move_to(10.0, 0.0)
        result = robot.update_position(1.0)
        assert result is True
        assert robot.is_moving

    def test_diagonal_movement(self):
        """斜向移動正確。"""
        robot = MockReachyMini(position=(0.0, 0.0), speed=math.sqrt(2))
        robot.move_to(1.0, 1.0)
        robot.update_position(1.0)  # 速度剛好移動 sqrt(2)，應到達

        assert robot.position[0] == pytest.approx(1.0, abs=0.01)
        assert robot.position[1] == pytest.approx(1.0, abs=0.01)

    def test_multiple_steps_reach_target(self):
        """分多步移動最終到達目標。"""
        robot = MockReachyMini(position=(0.0, 0.0), speed=1.0)
        robot.move_to(3.0, 4.0)

        for _ in range(100):
            moving = robot.update_position(0.1)
            if not moving:
                break

        assert robot.position[0] == pytest.approx(3.0, abs=0.01)
        assert robot.position[1] == pytest.approx(4.0, abs=0.01)
        assert not robot.is_moving

    def test_speed_affects_movement(self):
        """速度影響移動距離。"""
        robot_slow = MockReachyMini(position=(0.0, 0.0), speed=1.0)
        robot_fast = MockReachyMini(position=(0.0, 0.0), speed=3.0)

        robot_slow.move_to(10.0, 0.0)
        robot_fast.move_to(10.0, 0.0)

        robot_slow.update_position(1.0)
        robot_fast.update_position(1.0)

        assert robot_fast.position[0] > robot_slow.position[0]


# ── 狀態摘要 ──────────────────────────────────────────────────────

class TestStateSummary:
    """測試 get_state_summary。"""

    def test_summary_keys(self):
        """摘要包含必要欄位。"""
        robot = MockReachyMini()
        summary = robot.get_state_summary()
        required_keys = [
            "position", "heading", "antenna_pos", "antenna_pos_deg",
            "head_yaw_deg", "head_pitch_deg", "body_yaw", "body_yaw_deg",
            "move_target", "is_moving", "audio_playing", "log_count",
        ]
        for key in required_keys:
            assert key in summary, f"缺少欄位: {key}"

    def test_summary_position(self):
        """摘要中的位置正確。"""
        robot = MockReachyMini(position=(3.0, 7.0))
        summary = robot.get_state_summary()
        assert summary["position"] == (3.0, 7.0)

    def test_summary_not_moving(self):
        """初始摘要顯示未移動。"""
        robot = MockReachyMini()
        summary = robot.get_state_summary()
        assert summary["is_moving"] is False
        assert summary["move_target"] is None


# ── MockMedia ─────────────────────────────────────────────────────

class TestMockMedia:
    """測試 MockMedia 基本功能。"""

    def test_media_property(self):
        """media 屬性回傳 MockMedia 實例。"""
        robot = MockReachyMini()
        assert robot.media is not None

    def test_get_frame_shape(self):
        """get_frame 回傳正確形狀的影像。"""
        robot = MockReachyMini()
        frame = robot.media.get_frame()
        assert frame.shape == (480, 640, 3)
        assert frame.dtype == np.uint8

    def test_audio_samplerate(self):
        """音訊取樣率正確。"""
        robot = MockReachyMini()
        assert robot.media.get_output_audio_samplerate() == 16000

    def test_audio_playback(self):
        """音訊播放狀態管理。"""
        robot = MockReachyMini()
        assert not robot.media.is_playing
        robot.media.start_playing()
        assert robot.media.is_playing
        robot.media.stop_playing()
        assert not robot.media.is_playing

    def test_push_audio_sample(self):
        """push_audio_sample 記錄樣本數。"""
        robot = MockReachyMini()
        robot.media.start_playing()
        samples = np.zeros(1600, dtype=np.float32)
        robot.media.push_audio_sample(samples)
        assert robot.media.total_audio_samples_pushed == 1600


# ── close ─────────────────────────────────────────────────────────

class TestClose:
    """測試資源釋放。"""

    def test_close_does_not_raise(self):
        """close 不應拋出例外。"""
        robot = MockReachyMini()
        robot.close()  # 不應拋出
