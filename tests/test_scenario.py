"""測試場景引擎 - 事件排序、tick 觸發、暫停/倍速。

涵蓋 ScenarioEngine 的事件載入、排序、tick 觸發、暫停/恢復、倍速、
以及人物狀態管理等功能。
"""

import json
import tempfile
from pathlib import Path

import pytest

from reachy_mini_simulator.scenario import ScenarioEngine, SimEvent, SimPerson


# ── 事件載入與排序 ────────────────────────────────────────────────

class TestEventLoading:
    """測試事件載入與排序。"""

    def test_load_sorts_by_time(self):
        """載入事件後依 time 排序。"""
        engine = ScenarioEngine()
        events = [
            SimEvent(time=10, event_type="a"),
            SimEvent(time=5, event_type="b"),
            SimEvent(time=15, event_type="c"),
        ]
        engine.load(events)
        assert engine.total_events == 3

    def test_load_resets_state(self):
        """重新載入事件會重置狀態。"""
        engine = ScenarioEngine()
        events = [SimEvent(time=1, event_type="a")]
        engine.load(events)
        engine.start()
        engine.tick(2.0)
        assert engine.triggered_count == 1

        # 重新載入
        engine.load(events)
        assert engine.triggered_count == 0
        assert engine.current_time == 0.0

    def test_load_from_json(self, tmp_path):
        """從 JSON 檔案載入場景。"""
        data = [
            {"time": 5, "event_type": "person_appears", "data": {"name": "A"}},
            {"time": 10, "event_type": "idle", "data": {}},
        ]
        json_path = str(tmp_path / "scenario.json")
        Path(json_path).write_text(json.dumps(data), encoding="utf-8")

        engine = ScenarioEngine()
        engine.load_from_json(json_path)
        assert engine.total_events == 2


# ── tick 觸發 ─────────────────────────────────────────────────────

class TestTick:
    """測試 tick 推進與事件觸發。"""

    def _make_engine(self, events=None):
        """建立已載入事件的引擎。"""
        engine = ScenarioEngine()
        if events is None:
            events = [
                SimEvent(time=5, event_type="a"),
                SimEvent(time=10, event_type="b"),
                SimEvent(time=20, event_type="c"),
            ]
        engine.load(events)
        engine.start()
        return engine

    def test_tick_advances_time(self):
        """tick 推進模擬時間。"""
        engine = self._make_engine()
        engine.tick(3.0)
        assert engine.current_time == pytest.approx(3.0)

    def test_tick_triggers_events(self):
        """tick 觸發到期的事件。"""
        engine = self._make_engine()
        triggered = engine.tick(6.0)
        assert len(triggered) == 1
        assert triggered[0].event_type == "a"

    def test_tick_triggers_multiple_events(self):
        """單次 tick 可觸發多個事件。"""
        engine = self._make_engine()
        triggered = engine.tick(15.0)
        assert len(triggered) == 2
        assert triggered[0].event_type == "a"
        assert triggered[1].event_type == "b"

    def test_tick_all_events(self):
        """tick 足夠時間後觸發所有事件。"""
        engine = self._make_engine()
        engine.tick(100.0)
        assert engine.triggered_count == 3
        assert engine.is_finished

    def test_no_double_trigger(self):
        """事件不會被重複觸發。"""
        engine = self._make_engine()
        engine.tick(6.0)
        assert engine.triggered_count == 1

        triggered = engine.tick(1.0)
        assert len(triggered) == 0
        assert engine.triggered_count == 1

    def test_tick_returns_empty_when_not_running(self):
        """未啟動時 tick 不觸發事件。"""
        engine = ScenarioEngine()
        engine.load([SimEvent(time=1, event_type="a")])
        # 沒有呼叫 start()
        triggered = engine.tick(10.0)
        assert len(triggered) == 0

    def test_on_event_callback(self):
        """事件觸發時呼叫 on_event 回呼。"""
        engine = self._make_engine()
        received = []
        engine.on_event = lambda e: received.append(e.event_type)
        engine.tick(6.0)
        assert received == ["a"]

    def test_is_finished(self):
        """所有事件觸發後 is_finished 為 True。"""
        engine = self._make_engine()
        assert not engine.is_finished
        engine.tick(100.0)
        assert engine.is_finished


# ── 暫停與恢復 ────────────────────────────────────────────────────

class TestPauseResume:
    """測試暫停與恢復。"""

    def test_pause_stops_tick(self):
        """暫停後 tick 不推進時間。"""
        engine = ScenarioEngine()
        engine.load([SimEvent(time=5, event_type="a")])
        engine.start()
        engine.pause()
        engine.tick(10.0)
        assert engine.current_time == 0.0
        assert engine.triggered_count == 0

    def test_resume_continues(self):
        """恢復後繼續推進。"""
        engine = ScenarioEngine()
        engine.load([SimEvent(time=5, event_type="a")])
        engine.start()
        engine.pause()
        engine.tick(10.0)
        engine.resume()
        engine.tick(6.0)
        assert engine.triggered_count == 1


# ── 倍速 ─────────────────────────────────────────────────────────

class TestSpeed:
    """測試倍速控制。"""

    def test_default_speed(self):
        """預設倍速為 1.0。"""
        engine = ScenarioEngine()
        assert engine.speed == 1.0

    def test_set_speed(self):
        """設定倍速後影響時間推進。"""
        engine = ScenarioEngine()
        engine.load([SimEvent(time=10, event_type="a")])
        engine.start()
        engine.set_speed(2.0)
        assert engine.speed == 2.0

        # dt=3 * speed=2 = 實際推進 6
        engine.tick(3.0)
        assert engine.current_time == pytest.approx(6.0)

    def test_set_speed_triggers_event(self):
        """倍速加快後事件提前觸發。"""
        engine = ScenarioEngine()
        engine.load([SimEvent(time=10, event_type="a")])
        engine.start()
        engine.set_speed(5.0)
        triggered = engine.tick(3.0)  # 3 * 5 = 15 > 10
        assert len(triggered) == 1

    def test_invalid_speed(self):
        """無效倍速值應拋出 ValueError。"""
        engine = ScenarioEngine()
        with pytest.raises(ValueError):
            engine.set_speed(0)
        with pytest.raises(ValueError):
            engine.set_speed(-1.0)


# ── 人物狀態管理 ──────────────────────────────────────────────────

class TestPersonState:
    """測試場景引擎的人物狀態管理。"""

    def test_person_appears(self):
        """person_appears 事件新增人物。"""
        engine = ScenarioEngine()
        engine.load([
            SimEvent(time=1, event_type="person_appears", data={
                "name": "Alice", "position": [3, 4],
            }),
        ])
        engine.start()
        engine.tick(2.0)
        assert "Alice" in engine.persons
        assert engine.persons["Alice"].is_visible
        assert engine.persons["Alice"].position == (3, 4)

    def test_person_leaves(self):
        """person_leaves 事件讓人物消失。"""
        engine = ScenarioEngine()
        engine.load([
            SimEvent(time=1, event_type="person_appears", data={
                "name": "Bob", "position": [5, 5],
            }),
            SimEvent(time=5, event_type="person_leaves", data={"name": "Bob"}),
        ])
        engine.start()
        engine.tick(2.0)
        assert engine.persons["Bob"].is_visible

        engine.tick(5.0)
        assert not engine.persons["Bob"].is_visible

    def test_person_moves(self):
        """person_moves 事件更新人物位置。"""
        engine = ScenarioEngine()
        engine.load([
            SimEvent(time=1, event_type="person_appears", data={
                "name": "Carol", "position": [1, 1],
            }),
            SimEvent(time=5, event_type="person_moves", data={
                "name": "Carol", "position": [8, 8],
            }),
        ])
        engine.start()
        engine.tick(2.0)
        assert engine.persons["Carol"].position == (1, 1)

        engine.tick(5.0)
        assert engine.persons["Carol"].position == (8, 8)

    def test_person_moves_auto_creates(self):
        """person_moves 事件在人物不存在時自動建立。"""
        engine = ScenarioEngine()
        engine.load([
            SimEvent(time=1, event_type="person_moves", data={
                "name": "Dave", "position": [2, 3],
            }),
        ])
        engine.start()
        engine.tick(2.0)
        assert "Dave" in engine.persons
        assert engine.persons["Dave"].position == (2, 3)


# ── SimEvent / SimPerson dataclass ────────────────────────────────

class TestDataclasses:
    """測試 SimEvent 和 SimPerson 資料類別。"""

    def test_sim_event_defaults(self):
        """SimEvent 的 data 預設為空字典。"""
        ev = SimEvent(time=5, event_type="test")
        assert ev.data == {}

    def test_sim_person_defaults(self):
        """SimPerson 的預設值正確。"""
        p = SimPerson(name="Test")
        assert p.position == (0.0, 0.0)
        assert p.is_visible is True


# ── 停止 ─────────────────────────────────────────────────────────

class TestStop:
    """測試停止功能。"""

    def test_stop_resets_running(self):
        """stop 後 is_running 為 False。"""
        engine = ScenarioEngine()
        engine.load([SimEvent(time=1, event_type="a")])
        engine.start()
        assert engine.is_running
        engine.stop()
        assert not engine.is_running

    def test_tick_after_stop(self):
        """stop 後 tick 不推進時間。"""
        engine = ScenarioEngine()
        engine.load([SimEvent(time=1, event_type="a")])
        engine.start()
        engine.stop()
        engine.tick(10.0)
        assert engine.triggered_count == 0
