"""Web API 端對端測試 — 人物感知 + 主動對話端點。

使用 starlette TestClient 測試 FastAPI 應用，不需啟動伺服器。
注意：TestClient 會自動觸發 lifespan（呼叫 _init_simulation），
因此不需要手動初始化。
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


# ── 人物感知端點 ─────────────────────────────────────────────────


class TestGetPerceptionEndpoint:
    """GET /api/perception 端點測試。"""

    def test_get_perception_endpoint(self, client: TestClient):
        """GET /api/perception 回傳正確格式。"""
        resp = client.get("/api/perception")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        assert data["mode"] == "mock"
        assert "person_visible" in data
        assert isinstance(data["person_visible"], bool)
        assert "person_count" in data
        assert isinstance(data["person_count"], int)
        assert "person_positions" in data
        assert "is_running" in data

    def test_perception_initial_state(self, client: TestClient):
        """初始狀態：無人可見。"""
        resp = client.get("/api/perception")
        data = resp.json()
        assert data["person_visible"] is False
        assert data["person_count"] == 0


class TestInjectPersonEndpoint:
    """POST /api/perception/inject 端點測試。"""

    def test_inject_person_endpoint(self, client: TestClient):
        """POST /api/perception/inject 注入人物。"""
        resp = client.post(
            "/api/perception/inject",
            json={"name": "TestUser", "position": [0.3, 0.7]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["name"] == "TestUser"
        assert data["position"] == [0.3, 0.7]

    def test_inject_then_get(self, client: TestClient):
        """注入後 GET 可見人物。"""
        client.post(
            "/api/perception/inject",
            json={"name": "Alice", "position": [0.5, 0.5]},
        )
        resp = client.get("/api/perception")
        data = resp.json()
        assert data["person_visible"] is True
        assert data["person_count"] >= 1

    def test_inject_empty_name(self, client: TestClient):
        """name 為空應回傳錯誤。"""
        resp = client.post(
            "/api/perception/inject",
            json={"name": "", "position": [0.5, 0.5]},
        )
        data = resp.json()
        assert data["success"] is False


class TestRemovePersonEndpoint:
    """POST /api/perception/remove 端點測試。"""

    def test_remove_person_endpoint(self, client: TestClient):
        """POST /api/perception/remove 移除人物。"""
        client.post("/api/perception/inject", json={"name": "Bob"})
        resp = client.post("/api/perception/remove", json={"name": "Bob"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["name"] == "Bob"

    def test_remove_then_check(self, client: TestClient):
        """移除後 GET 無人可見。"""
        client.post("/api/perception/inject", json={"name": "C"})
        client.post("/api/perception/remove", json={"name": "C"})
        resp = client.get("/api/perception")
        data = resp.json()
        assert data["person_count"] == 0

    def test_remove_empty_name(self, client: TestClient):
        """name 為空應回傳錯誤。"""
        resp = client.post("/api/perception/remove", json={"name": ""})
        data = resp.json()
        assert data["success"] is False


# ── 主動觸發端點 ─────────────────────────────────────────────────


class TestProactiveStatusEndpoint:
    """GET /api/proactive/status 端點測試。"""

    def test_proactive_status_endpoint(self, client: TestClient):
        """GET /api/proactive/status 回傳狀態。"""
        resp = client.get("/api/proactive/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "is_running" in data
        assert "greet_cooldown" in data
        assert "idle_timeout" in data


class TestProactiveConfigEndpoint:
    """POST /api/proactive/config 端點測試。"""

    def test_proactive_config_endpoint(self, client: TestClient):
        """POST /api/proactive/config 更新設定。"""
        resp = client.post(
            "/api/proactive/config",
            json={"enabled": False, "greet_cooldown": 60, "idle_timeout": 300},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["enabled"] is False
        assert data["greet_cooldown"] == 60.0
        assert data["idle_timeout"] == 300.0

    def test_proactive_partial_config(self, client: TestClient):
        """只更新部分欄位。"""
        resp = client.post(
            "/api/proactive/config",
            json={"enabled": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["enabled"] is True


# ── 對話端點 ─────────────────────────────────────────────────────


class TestChatEndpoint:
    """POST /api/chat 端點測試。"""

    def test_chat_endpoint(self, client: TestClient):
        """POST /api/chat 發送對話。"""
        resp = client.post("/api/chat", json={"message": "你好"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_chat_empty_message(self, client: TestClient):
        """空訊息應回傳錯誤。"""
        resp = client.post("/api/chat", json={"message": ""})
        data = resp.json()
        assert data["success"] is False

    def test_chat_with_name(self, client: TestClient):
        """帶名字的對話。"""
        resp = client.post(
            "/api/chat",
            json={"message": "早安", "name": "David"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


class TestChatHistoryEndpoint:
    """GET /api/chat/history 端點測試。"""

    def test_chat_history_endpoint(self, client: TestClient):
        """GET /api/chat/history 回傳歷史。"""
        resp = client.get("/api/chat/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_chat_history_after_send(self, client: TestClient):
        """發送後歷史有記錄。"""
        client.post("/api/chat", json={"message": "測試訊息"})
        resp = client.get("/api/chat/history")
        data = resp.json()
        assert len(data["history"]) >= 1
        # 找到最後一筆 user 訊息
        user_msgs = [h for h in data["history"] if h.get("role") == "user"]
        assert len(user_msgs) >= 1
        assert user_msgs[-1]["text"] == "測試訊息"
