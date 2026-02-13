"""AIBrain.inject() 單元測試。"""

from __future__ import annotations

import threading
import time

import pytest

from reachy_mini_simulator.ai_brain import AIBrain, BrainResponse


@pytest.fixture()
def brain() -> AIBrain:
    """建立無 API key 的 AIBrain（fallback 模式）。"""
    b = AIBrain(api_key="")
    b.start()
    yield b
    b.stop()


class TestInjectCreatesResponse:
    """inject() 產生回應。"""

    def test_inject_creates_response(self, brain: AIBrain) -> None:
        """inject() 應透過 on_response 回呼產生 BrainResponse。"""
        results: list[BrainResponse] = []
        event = threading.Event()

        def on_resp(resp: BrainResponse) -> None:
            results.append(resp)
            event.set()

        brain.on_response = on_resp
        brain.inject("有人出現在附近，請主動友善地打招呼。", "proactive_greet")

        event.wait(timeout=5.0)
        assert len(results) == 1
        assert isinstance(results[0], BrainResponse)
        assert results[0].text  # 非空文字


class TestInjectEventType:
    """inject() 回應的 event_type 正確。"""

    def test_inject_event_type(self, brain: AIBrain) -> None:
        """回應的 event_type 應與 inject 傳入的一致。"""
        results: list[BrainResponse] = []
        event = threading.Event()

        def on_resp(resp: BrainResponse) -> None:
            results.append(resp)
            event.set()

        brain.on_response = on_resp
        brain.inject("測試", "proactive_farewell")

        event.wait(timeout=5.0)
        assert len(results) == 1
        assert results[0].event_type == "proactive_farewell"

    def test_inject_default_event_type(self, brain: AIBrain) -> None:
        """不指定 event_type 時預設為 proactive。"""
        results: list[BrainResponse] = []
        event = threading.Event()

        def on_resp(resp: BrainResponse) -> None:
            results.append(resp)
            event.set()

        brain.on_response = on_resp
        brain.inject("測試")

        event.wait(timeout=5.0)
        assert len(results) == 1
        assert results[0].event_type == "proactive"


class TestInjectWithFallback:
    """無 API key 時 inject 也能產生 fallback 回應。"""

    def test_inject_with_fallback(self) -> None:
        """無 API key 時 inject() 仍產生回應。"""
        brain = AIBrain(api_key="")
        brain.start()

        results: list[BrainResponse] = []
        event = threading.Event()

        def on_resp(resp: BrainResponse) -> None:
            results.append(resp)
            event.set()

        brain.on_response = on_resp
        brain.inject("有人出現在附近。", "proactive_greet")

        event.wait(timeout=5.0)
        brain.stop()

        assert len(results) == 1
        assert results[0].text  # 有文字內容
        assert results[0].emotion is not None  # fallback 含情緒標籤


class TestInjectDoesNotBreakExistingEvents:
    """inject 後一般事件仍正常。"""

    def test_inject_does_not_break_existing_events(self, brain: AIBrain) -> None:
        """inject 後 handle_event 仍能正常產生回應。"""
        results: list[BrainResponse] = []
        done = threading.Event()

        def on_resp(resp: BrainResponse) -> None:
            results.append(resp)
            if len(results) >= 2:
                done.set()

        brain.on_response = on_resp

        # 先 inject
        brain.inject("你好", "proactive_greet")
        # 再送一般事件
        brain.handle_event("person_appears", {"name": "Alice", "location": "大門"})

        done.wait(timeout=5.0)

        assert len(results) >= 2
        event_types = [r.event_type for r in results]
        assert "proactive_greet" in event_types
        assert "person_appears" in event_types
