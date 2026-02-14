"""Web API 端對端測試 — 語音對話端點。

使用 starlette TestClient 測試 FastAPI 語音相關端點，
包含 /api/voice/start、/api/voice/stop、/api/voice/status，
以及 WebSocket 狀態中的 voice 欄位。
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from reachy_mini_simulator.web_server import app


@pytest.fixture()
def client():
    """建立 TestClient，自動觸發 lifespan 初始化。"""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestVoiceStatusEndpoint:
    """GET /api/voice/status 端點測試。"""

    def test_voice_status_endpoint(self, client: TestClient):
        """GET /api/voice/status 回傳正確格式。"""
        resp = client.get("/api/voice/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "is_listening" in data
        assert "last_transcript" in data
        assert "has_tts" in data

    def test_voice_initial_status(self, client: TestClient):
        """初始狀態為 idle。"""
        resp = client.get("/api/voice/status")
        data = resp.json()
        assert data["status"] == "idle"
        assert data["is_listening"] is False
        assert data["last_transcript"] is None


class TestVoiceStartEndpoint:
    """POST /api/voice/start 端點測試。"""

    def test_voice_start_returns_result(self, client: TestClient):
        """POST /api/voice/start 回傳結果。"""
        resp = client.post("/api/voice/start")
        assert resp.status_code == 200
        data = resp.json()
        # 可能成功（有 AudioInput）或失敗（缺依賴）
        assert "success" in data or "error" in data


class TestVoiceStopEndpoint:
    """POST /api/voice/stop 端點測試。"""

    def test_voice_stop_returns_idle(self, client: TestClient):
        """POST /api/voice/stop 回傳 idle 狀態。"""
        resp = client.post("/api/voice/stop")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["status"] == "idle"

    def test_voice_stop_then_status(self, client: TestClient):
        """停止後 status 確認為 idle。"""
        client.post("/api/voice/stop")
        resp = client.get("/api/voice/status")
        data = resp.json()
        assert data["status"] == "idle"


class TestVoiceStateInWebSocket:
    """WebSocket 狀態推送中的 voice 欄位測試。"""

    def test_state_contains_voice(self, client: TestClient):
        """GET /api/state 回傳包含 voice 欄位。"""
        resp = client.get("/api/state")
        assert resp.status_code == 200
        data = resp.json()
        assert "voice" in data
        voice = data["voice"]
        assert "status" in voice
        assert "is_listening" in voice
        assert "last_transcript" in voice

    def test_voice_state_initial(self, client: TestClient):
        """初始 voice 狀態為 idle。"""
        resp = client.get("/api/state")
        data = resp.json()
        assert data["voice"]["status"] == "idle"
        assert data["voice"]["is_listening"] is False
