"""整合測試 - 模擬完整使用場景。

驗證多個模組之間的協作，包含喚醒/睡眠、凝視追蹤、IMU、馬達控制、
動作錄製/回放、媒體功能、表情引擎、人物感知、主動對話，以及向後相容性。
"""

import time

import numpy as np
import pytest

from reachy_mini_simulator.mock_robot import MockReachyMini
from reachy_mini_simulator.expression import ExpressionEngine
from reachy_mini_simulator.motion import Move, JointFrame
from reachy_mini_simulator.person_detector import (
    MockPersonDetector,
    PersonDetectorInterface,
    create_person_detector,
)
from reachy_mini_simulator.proactive import ProactiveTrigger
from reachy_mini_simulator.ai_brain import AIBrain


class TestFullScenario:
    """模擬完整場景：喚醒 -> 動作 -> 凝視 -> IMU -> 馬達 -> 睡眠。"""

    def test_wake_move_gaze_sleep(self):
        """完整場景流程測試。"""
        robot = MockReachyMini()

        # 1. 喚醒
        robot.wake_up()
        assert robot.is_awake

        # 2. 設定目標姿態
        robot.set_target(antennas=[0.3, 0.3])
        assert robot.antenna_pos[0] == pytest.approx(0.3)

        # 3. 凝視追蹤
        robot.look_at_world(1.0, 0.0, 0.0)
        # 前方 yaw=0, pitch=0 -> 接近單位矩陣
        np.testing.assert_array_almost_equal(robot.head_pose, np.eye(4), decimal=3)

        robot.look_at_world(0.0, 1.0, 0.0)
        # 看向左方，頭部應旋轉
        assert not np.allclose(robot.head_pose, np.eye(4))

        # 4. IMU 數據
        imu = robot.get_imu_data()
        assert "accelerometer" in imu
        assert "gyroscope" in imu
        assert "quaternion" in imu
        assert len(imu["accelerometer"]) == 3

        # 5. 關節位置
        joints = robot.get_current_joint_positions()
        assert isinstance(joints, dict)
        assert len(joints) > 0
        assert "head_yaw" in joints
        assert "antenna_right" in joints

        # 6. 馬達控制
        robot.set_motor_enabled("head_yaw", False)
        assert not robot.is_motor_enabled("head_yaw")
        robot.set_motor_enabled("head_yaw", True)
        assert robot.is_motor_enabled("head_yaw")

        # 7. 重力補償
        robot.set_gravity_compensation(True)
        robot.set_gravity_compensation(False)

        # 8. 睡眠
        robot.goto_sleep()
        assert not robot.is_awake

    def test_sleep_blocks_set_target(self):
        """睡眠後 set_target 不生效，喚醒後恢復。"""
        robot = MockReachyMini()
        robot.set_target(body_yaw=1.0)
        assert robot.body_yaw == pytest.approx(1.0)

        robot.goto_sleep()
        robot.set_target(body_yaw=2.0)
        # 值應維持不變
        assert robot.body_yaw == pytest.approx(1.0)

        robot.wake_up()
        robot.set_target(body_yaw=2.0)
        assert robot.body_yaw == pytest.approx(2.0)


class TestMotionRecordAndPlayback:
    """測試動作錄製與回放的完整流程。"""

    def test_record_and_playback(self):
        """錄製 -> 序列化 -> 反序列化 -> 回放。"""
        robot = MockReachyMini()
        robot.wake_up()

        # 錄製
        robot.start_motion_recording()
        robot._motion_recorder.capture(robot)
        robot.set_target(antennas=[0.3, 0.3])
        robot._motion_recorder.capture(robot)
        move = robot.stop_motion_recording()

        assert isinstance(move, Move)
        assert len(move.frames) == 2

        # 序列化往返
        json_str = move.to_json()
        restored = Move.from_json(json_str)
        assert len(restored.frames) == 2

        # 回放
        robot.play_motion(restored)
        assert robot.is_motion_playing

    def test_empty_recording(self):
        """空錄製不會出錯。"""
        robot = MockReachyMini()
        robot.start_motion_recording()
        move = robot.stop_motion_recording()
        assert isinstance(move, Move)
        assert len(move.frames) == 0


class TestMediaSoundAndRecording:
    """測試媒體音訊與錄音的完整流程。"""

    def test_sound_playback_cycle(self):
        """播放 -> 確認播放中 -> 停止 -> 確認已停止。"""
        robot = MockReachyMini()
        media = robot.media

        assert not media.is_sound_playing()

        media.play_sound("/tmp/test.wav")
        assert media.is_sound_playing()

        media.stop_sound()
        assert not media.is_sound_playing()

    def test_recording_cycle(self):
        """錄音 -> 取樣 -> 停止。"""
        robot = MockReachyMini()
        media = robot.media

        assert not media.is_recording
        assert media.get_audio_sample() is None

        media.start_recording()
        assert media.is_recording

        sample = media.get_audio_sample()
        assert sample is not None
        assert sample.dtype == np.float32
        assert len(sample) > 0

        media.stop_recording()
        assert not media.is_recording

    def test_doa_returns_valid_range(self):
        """DoA 回傳合理範圍。"""
        robot = MockReachyMini()
        for _ in range(10):
            doa = robot.media.get_doa()
            assert isinstance(doa, float)
            assert 0.0 <= doa <= 360.0


class TestExpressionWithNewFeatures:
    """測試表情引擎與新功能的整合。"""

    def test_expression_state_and_emotion(self):
        """設定狀態 -> 觸發情緒 -> 更新天線。"""
        robot = MockReachyMini()
        robot.wake_up()
        expr = ExpressionEngine()

        # 設定 LISTENING 狀態
        expr.set_state("LISTENING")
        expr.update(robot)

        # 天線應有變化（LISTENING 狀態天線會豎起）
        # 由於動畫依賴 time，至少確認不會拋出錯誤

        # 觸發情緒
        expr.trigger_emotion("高興")
        expr.update(robot)

    def test_all_states(self):
        """所有狀態都不會拋出錯誤。"""
        robot = MockReachyMini()
        robot.wake_up()
        expr = ExpressionEngine()

        for state in ["IDLE", "LISTENING", "PROCESSING", "SPEAKING"]:
            expr.set_state(state)
            expr.update(robot)

    def test_all_emotions(self):
        """所有情緒都不會拋出錯誤。"""
        robot = MockReachyMini()
        robot.wake_up()
        expr = ExpressionEngine()

        emotions = ["高興", "驚訝", "思考", "同意", "不同意", "興奮", "撒嬌", "好奇"]
        for emotion in emotions:
            expr.trigger_emotion(emotion)
            expr.update(robot)


class TestBackwardCompatibility:
    """確認舊有的介面仍然正常工作。"""

    def test_basic_operations(self):
        """基本操作向後相容。"""
        robot = MockReachyMini(position=(1.0, 2.0), heading=45.0)

        # 基本屬性
        assert robot.position == (1.0, 2.0)
        assert robot.heading == 45.0

        # set_target
        head = np.eye(4)
        robot.set_target(head=head)
        np.testing.assert_array_equal(robot.head_pose, head)

        # move_to
        robot.move_to(3.0, 4.0)
        assert robot.is_moving

        # update_position
        still_moving = robot.update_position(0.1)
        assert isinstance(still_moving, bool)

        # media
        assert robot.media is not None
        frame = robot.media.get_frame()
        assert frame.shape == (480, 640, 3)
        assert frame.dtype == np.uint8

        # audio
        assert robot.media.get_output_audio_samplerate() == 16000
        robot.media.start_playing()
        assert robot.media.is_playing
        robot.media.stop_playing()

        # state summary
        summary = robot.get_state_summary()
        assert isinstance(summary, dict)
        assert "position" in summary
        assert "heading" in summary
        assert "antenna_pos" in summary
        assert "is_moving" in summary

        # close
        robot.close()

    def test_position_setter(self):
        """position setter 仍然正常。"""
        robot = MockReachyMini()
        robot.position = (5.0, 6.0)
        assert robot.position == (5.0, 6.0)

    def test_heading_setter(self):
        """heading setter 仍然正常。"""
        robot = MockReachyMini()
        robot.heading = 90.0
        assert robot.heading == 90.0

    def test_set_target_validation(self):
        """set_target 參數驗證仍然正常。"""
        robot = MockReachyMini()
        with pytest.raises(ValueError):
            robot.set_target()
        with pytest.raises(ValueError):
            robot.set_target(head=np.eye(3))
        with pytest.raises(ValueError):
            robot.set_target(antennas=[1.0])


class TestInterpolationIntegration:
    """測試插值系統與機器人的整合。"""

    def test_goto_target_with_different_methods(self):
        """goto_target 支援所有插值方法。"""
        robot = MockReachyMini()
        methods = ["MIN_JERK", "LINEAR", "EASE", "CARTOON"]
        for method in methods:
            robot.goto_target(antennas=[0.5, 0.5], duration=1.0, method=method)

    def test_goto_target_updates_engine(self):
        """goto_target 啟動插值引擎。"""
        robot = MockReachyMini()
        robot.goto_target(body_yaw=1.0, duration=1.0, method="LINEAR")
        assert robot._interp_engine.is_active

    def test_joint_positions_reflect_state(self):
        """get_current_joint_positions 反映當前狀態。"""
        robot = MockReachyMini()
        robot.set_target(antennas=[0.5, -0.3], body_yaw=0.1)
        joints = robot.get_current_joint_positions()
        assert "antenna_right" in joints
        assert "antenna_left" in joints
        assert "body_yaw" in joints


class TestGazeIntegration:
    """測試凝視追蹤整合。"""

    def test_look_at_image_updates_head(self):
        """look_at_image 更新頭部姿態。"""
        robot = MockReachyMini()

        # 看左上角
        robot.look_at_image(0.0, 0.0)
        pose_tl = robot.head_pose.copy()

        # 看右下角
        robot.look_at_image(1.0, 1.0)
        pose_br = robot.head_pose.copy()

        # 兩個姿態應不同
        assert not np.allclose(pose_tl, pose_br)

    def test_look_at_world_then_read_joints(self):
        """look_at_world 後能從 joints 讀到變化。"""
        robot = MockReachyMini()
        joints_before = robot.get_current_joint_positions()

        robot.look_at_world(0.0, 1.0, 0.0)  # 看向左方
        joints_after = robot.get_current_joint_positions()

        # head_yaw 應有變化
        assert joints_after["head_yaw"] != pytest.approx(joints_before["head_yaw"], abs=1.0)


# ── 感知 → 主動觸發 → 對話 完整管線測試 ──────────────────────────

class TestPerceptionConversationPipeline:
    """感知 → 主動觸發 → 對話 完整管線測試。"""

    def test_full_pipeline_greet(self):
        """模擬人物出現 → ProactiveTrigger 觸發 greet → AIBrain inject → 回應。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0)
        brain = AIBrain()  # fallback 模式

        triggered = []

        def on_trigger(trigger_type: str, prompt_text: str) -> None:
            triggered.append((trigger_type, prompt_text))
            brain.inject(prompt_text, f"proactive_{trigger_type}")

        responses = []
        brain.on_response = lambda resp: responses.append(resp)

        trigger.on_trigger = on_trigger
        detector.start()
        trigger.start()
        brain.start()

        try:
            detector.inject_person("Alice")

            # 等待 brain 背景執行緒處理完成
            deadline = time.time() + 3.0
            while len(responses) == 0 and time.time() < deadline:
                time.sleep(0.05)

            assert len(triggered) == 1
            assert triggered[0][0] == "greet"
            assert len(responses) >= 1
            assert responses[0].text  # 有回應文字
        finally:
            brain.stop()

    def test_full_pipeline_farewell(self):
        """模擬人物離開 → farewell 觸發。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        trigger.start()

        # 先注入人物再移除
        detector.inject_person("Bob")
        detector.remove_person("Bob")

        farewell_types = [t for t in triggered if t == "farewell"]
        assert len(farewell_types) == 1

    def test_full_pipeline_idle(self):
        """模擬有人在場但閒置 → idle 觸發。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0, idle_timeout=1.0)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        trigger.start()

        detector.inject_person("Charlie")

        # 連續 update 累積超過 idle_timeout
        for _ in range(15):
            trigger.update(0.1)

        idle_types = [t for t in triggered if t == "idle"]
        assert len(idle_types) == 1

    def test_multiple_persons_scenario(self):
        """多人出現/離開場景。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        trigger.start()

        # 注入 3 人
        detector.inject_person("A")
        detector.inject_person("B")
        detector.inject_person("C")

        # 移除 2 人 — 仍有 1 人，不觸發 farewell
        detector.remove_person("A")
        detector.remove_person("B")

        farewell_count = sum(1 for t in triggered if t == "farewell")
        assert farewell_count == 0

        # 移除最後 1 人 → 觸發 farewell
        detector.remove_person("C")
        farewell_count = sum(1 for t in triggered if t == "farewell")
        assert farewell_count == 1

    def test_cooldown_boundary(self):
        """冷卻期邊界：快速出現/消失不重複觸發。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=30.0)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        trigger.start()

        # 第一次注入 → 觸發 greet
        detector.inject_person("D")
        detector.remove_person("D")

        # 在冷卻期內再次注入 → 不應觸發第二次 greet
        detector.inject_person("D")

        greet_count = sum(1 for t in triggered if t == "greet")
        assert greet_count == 1

    def test_mode_switch_mock(self):
        """確認 create_person_detector("mock") 正常運作。"""
        detector = create_person_detector("mock")
        assert isinstance(detector, MockPersonDetector)
        assert isinstance(detector, PersonDetectorInterface)

        detector.start()
        assert detector.is_running
        detector.stop()
        assert not detector.is_running

    def test_create_person_detector_invalid_mode(self):
        """無效模式應拋出 ValueError。"""
        with pytest.raises(ValueError):
            create_person_detector("invalid")

    def test_trigger_disabled(self):
        """停用觸發器時不應觸發。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        trigger.start()
        trigger.enabled = False

        detector.inject_person("E")
        assert len(triggered) == 0

    def test_trigger_not_started(self):
        """未啟動觸發器時不應觸發。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        # trigger 未 start

        detector.inject_person("F")
        assert len(triggered) == 0

    def test_idle_not_triggered_without_person(self):
        """無人在場時 idle 不觸發。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0, idle_timeout=0.5)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        trigger.start()

        # 沒有注入人物，累積 update
        for _ in range(20):
            trigger.update(0.1)

        idle_count = sum(1 for t in triggered if t == "idle")
        assert idle_count == 0

    def test_reset_idle_timer(self):
        """reset_idle_timer 可正確重置閒置計時。"""
        detector = MockPersonDetector()
        trigger = ProactiveTrigger(detector, greet_cooldown=0.0, idle_timeout=1.0)

        triggered = []
        trigger.on_trigger = lambda t, p: triggered.append(t)

        detector.start()
        trigger.start()
        detector.inject_person("G")

        # 累積到接近超時
        for _ in range(9):
            trigger.update(0.1)

        # 重置計時器
        trigger.reset_idle_timer()

        # 再累積但未超過超時
        for _ in range(5):
            trigger.update(0.1)

        idle_count = sum(1 for t in triggered if t == "idle")
        assert idle_count == 0


# ── WebSocket 狀態驗證 ───────────────────────────────────────────

class TestWebSocketPerceptionState:
    """WebSocket 廣播驗證 — 包含新的 perception/proactive/conversation 欄位。"""

    def test_state_includes_perception(self):
        """_get_full_state() 回傳包含 perception 欄位。"""
        from reachy_mini_simulator import web_server

        # 保存原始全域狀態
        orig_robot = web_server._robot
        orig_scenario = web_server._scenario
        orig_navigator = web_server._navigator
        orig_calendar = web_server._calendar
        orig_detector = web_server._detector
        orig_proactive = web_server._proactive
        orig_brain_resp = web_server._last_brain_response

        try:
            # 設定最小可用狀態
            web_server._robot = MockReachyMini()
            from reachy_mini_simulator.scenario import ScenarioEngine
            from reachy_mini_simulator.navigation import Navigator
            from reachy_mini_simulator.office_map import create_default_office
            from reachy_mini_simulator.calendar_mock import CalendarMock

            office = create_default_office()
            web_server._scenario = ScenarioEngine()
            web_server._navigator = Navigator(office)
            web_server._calendar = CalendarMock()
            web_server._detector = MockPersonDetector()
            web_server._proactive = ProactiveTrigger(web_server._detector)
            web_server._last_brain_response = None

            state = web_server._get_full_state()

            assert "perception" in state
            assert "mode" in state["perception"]
            assert "person_visible" in state["perception"]
            assert "person_count" in state["perception"]
            assert "is_running" in state["perception"]
        finally:
            web_server._robot = orig_robot
            web_server._scenario = orig_scenario
            web_server._navigator = orig_navigator
            web_server._calendar = orig_calendar
            web_server._detector = orig_detector
            web_server._proactive = orig_proactive
            web_server._last_brain_response = orig_brain_resp

    def test_state_includes_proactive(self):
        """_get_full_state() 回傳包含 proactive 欄位。"""
        from reachy_mini_simulator import web_server

        orig_robot = web_server._robot
        orig_scenario = web_server._scenario
        orig_navigator = web_server._navigator
        orig_calendar = web_server._calendar
        orig_detector = web_server._detector
        orig_proactive = web_server._proactive
        orig_brain_resp = web_server._last_brain_response

        try:
            web_server._robot = MockReachyMini()
            from reachy_mini_simulator.scenario import ScenarioEngine
            from reachy_mini_simulator.navigation import Navigator
            from reachy_mini_simulator.office_map import create_default_office
            from reachy_mini_simulator.calendar_mock import CalendarMock

            office = create_default_office()
            web_server._scenario = ScenarioEngine()
            web_server._navigator = Navigator(office)
            web_server._calendar = CalendarMock()
            web_server._detector = MockPersonDetector()
            web_server._proactive = ProactiveTrigger(web_server._detector)
            web_server._last_brain_response = None

            state = web_server._get_full_state()

            assert "proactive" in state
            assert "enabled" in state["proactive"]
            assert "is_running" in state["proactive"]
        finally:
            web_server._robot = orig_robot
            web_server._scenario = orig_scenario
            web_server._navigator = orig_navigator
            web_server._calendar = orig_calendar
            web_server._detector = orig_detector
            web_server._proactive = orig_proactive
            web_server._last_brain_response = orig_brain_resp

    def test_state_includes_conversation(self):
        """_get_full_state() 回傳包含 conversation 欄位。"""
        from reachy_mini_simulator import web_server

        orig_robot = web_server._robot
        orig_scenario = web_server._scenario
        orig_navigator = web_server._navigator
        orig_calendar = web_server._calendar
        orig_detector = web_server._detector
        orig_proactive = web_server._proactive
        orig_brain_resp = web_server._last_brain_response

        try:
            web_server._robot = MockReachyMini()
            from reachy_mini_simulator.scenario import ScenarioEngine
            from reachy_mini_simulator.navigation import Navigator
            from reachy_mini_simulator.office_map import create_default_office
            from reachy_mini_simulator.calendar_mock import CalendarMock

            office = create_default_office()
            web_server._scenario = ScenarioEngine()
            web_server._navigator = Navigator(office)
            web_server._calendar = CalendarMock()
            web_server._detector = MockPersonDetector()
            web_server._proactive = ProactiveTrigger(web_server._detector)
            web_server._last_brain_response = None

            state = web_server._get_full_state()

            assert "conversation" in state
            assert "last_response" in state["conversation"]
            assert "last_emotion" in state["conversation"]
            assert "history_count" in state["conversation"]
        finally:
            web_server._robot = orig_robot
            web_server._scenario = orig_scenario
            web_server._navigator = orig_navigator
            web_server._calendar = orig_calendar
            web_server._detector = orig_detector
            web_server._proactive = orig_proactive
            web_server._last_brain_response = orig_brain_resp
