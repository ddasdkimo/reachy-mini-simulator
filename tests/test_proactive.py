"""ProactiveTrigger 單元測試。"""

from __future__ import annotations

import time

import pytest

from reachy_mini_simulator.person_detector import MockPersonDetector
from reachy_mini_simulator.proactive import (
    FAREWELL_PROMPT,
    GREET_PROMPT,
    IDLE_PROMPT,
    ProactiveTrigger,
)


@pytest.fixture()
def detector() -> MockPersonDetector:
    d = MockPersonDetector()
    d.start()
    return d


@pytest.fixture()
def trigger(detector: MockPersonDetector) -> ProactiveTrigger:
    return ProactiveTrigger(detector, greet_cooldown=1.0, idle_timeout=5.0)


class TestGreetTrigger:
    """打招呼觸發。"""

    def test_greet_trigger(self, trigger: ProactiveTrigger, detector: MockPersonDetector) -> None:
        """注入人物後觸發 greet。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        detector.inject_person("Alice")

        assert len(results) == 1
        assert results[0][0] == "greet"
        assert results[0][1] == GREET_PROMPT

    def test_greet_cooldown(self, trigger: ProactiveTrigger, detector: MockPersonDetector) -> None:
        """快速連續出現不重複觸發。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        detector.inject_person("Alice")
        detector.remove_person("Alice")
        detector.inject_person("Bob")

        greet_count = sum(1 for t, _ in results if t == "greet")
        assert greet_count == 1, f"冷卻期內不應重複打招呼，got {greet_count}"


class TestFarewellTrigger:
    """道別觸發。"""

    def test_farewell_trigger(self, trigger: ProactiveTrigger, detector: MockPersonDetector) -> None:
        """人物離開時觸發 farewell。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        detector.inject_person("Alice")
        results.clear()  # 清除 greet

        detector.remove_person("Alice")

        assert len(results) == 1
        assert results[0][0] == "farewell"
        assert results[0][1] == FAREWELL_PROMPT


class TestIdleTrigger:
    """閒置觸發。"""

    def test_idle_trigger(self, trigger: ProactiveTrigger, detector: MockPersonDetector) -> None:
        """update() 累計足夠 dt 後觸發 idle（需 person_visible）。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        detector.inject_person("Alice")
        results.clear()

        # 模擬 6 秒閒置（idle_timeout=5.0）
        for _ in range(60):
            trigger.update(0.1)

        idle_results = [r for r in results if r[0] == "idle"]
        assert len(idle_results) == 1
        assert idle_results[0][1] == IDLE_PROMPT

    def test_idle_not_trigger_when_no_person(
        self, trigger: ProactiveTrigger, detector: MockPersonDetector
    ) -> None:
        """無人在場時不觸發 idle。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        # 沒有人在場，累計時間
        for _ in range(100):
            trigger.update(0.1)

        assert len(results) == 0

    def test_idle_reset(self, trigger: ProactiveTrigger, detector: MockPersonDetector) -> None:
        """reset_idle_timer() 重置後重新計時。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        detector.inject_person("Alice")
        results.clear()

        # 累計 3 秒
        for _ in range(30):
            trigger.update(0.1)

        # 重置
        trigger.reset_idle_timer()

        # 再累計 3 秒 — 總共不到 idle_timeout
        for _ in range(30):
            trigger.update(0.1)

        idle_results = [r for r in results if r[0] == "idle"]
        assert len(idle_results) == 0

    def test_idle_only_triggers_once(
        self, trigger: ProactiveTrigger, detector: MockPersonDetector
    ) -> None:
        """閒置只觸發一次，直到 reset。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        detector.inject_person("Alice")
        results.clear()

        # 超過 idle_timeout 兩倍
        for _ in range(120):
            trigger.update(0.1)

        idle_results = [r for r in results if r[0] == "idle"]
        assert len(idle_results) == 1


class TestEnabledToggle:
    """啟用/停用切換。"""

    def test_enabled_toggle(self, trigger: ProactiveTrigger, detector: MockPersonDetector) -> None:
        """disabled 時不觸發。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()
        trigger.enabled = False

        detector.inject_person("Alice")

        assert len(results) == 0

    def test_re_enable(self, trigger: ProactiveTrigger, detector: MockPersonDetector) -> None:
        """重新啟用後可觸發。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()
        trigger.enabled = False

        detector.inject_person("Alice")
        assert len(results) == 0

        # 清除偵測器中的人，重新觸發流程
        detector.remove_person("Alice")
        trigger.enabled = True
        trigger._last_greet_time = 0.0  # 重置冷卻以便測試
        detector.inject_person("Bob")

        greet_results = [r for r in results if r[0] == "greet"]
        assert len(greet_results) == 1


class TestStartStop:
    """啟動/停止狀態。"""

    def test_start_stop(self, trigger: ProactiveTrigger) -> None:
        """is_running 狀態切換。"""
        assert not trigger.is_running

        trigger.start()
        assert trigger.is_running

        trigger.stop()
        assert not trigger.is_running

    def test_not_running_no_trigger(
        self, trigger: ProactiveTrigger, detector: MockPersonDetector
    ) -> None:
        """未啟動時不觸發。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))

        # 未呼叫 start()
        detector.inject_person("Alice")

        assert len(results) == 0


class TestCallbackArgs:
    """回呼參數驗證。"""

    def test_callback_receives_correct_args(
        self, trigger: ProactiveTrigger, detector: MockPersonDetector
    ) -> None:
        """驗證 trigger_type 和 prompt 文字正確。"""
        results: list[tuple[str, str]] = []
        trigger.on_trigger = lambda t, p: results.append((t, p))
        trigger.start()

        # 測試 greet
        detector.inject_person("Alice")
        assert results[-1] == ("greet", GREET_PROMPT)

        # 測試 farewell
        detector.remove_person("Alice")
        assert results[-1] == ("farewell", FAREWELL_PROMPT)

        # 測試 idle（需要重新加入人物）
        detector.inject_person("Bob")
        results.clear()
        for _ in range(60):
            trigger.update(0.1)
        idle_results = [r for r in results if r[0] == "idle"]
        assert len(idle_results) == 1
        assert idle_results[0] == ("idle", IDLE_PROMPT)
