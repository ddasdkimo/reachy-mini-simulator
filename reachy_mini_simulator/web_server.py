"""Web 伺服器 - FastAPI + WebSocket 即時推送。

提供 REST API 與 WebSocket 介面，讓前端網頁可以即時取得模擬器狀態、
控制機器人導航與說話，並透過 WebSocket 接收即時更新。

REST API:
    GET  /api/state    - 機器人狀態摘要
    GET  /api/map      - 地圖資料（JSON）
    GET  /api/events   - 事件日誌
    POST /api/navigate - 導航到指定位置
    POST /api/speak    - 模擬說話輸入

WebSocket:
    /ws - 即時推送機器人位置、事件、狀態更新

啟動方式::

    python -m reachy_mini_simulator.web_server
    # 或透過 entry point:
    reachy-sim-web
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import math
import threading
import time
from typing import Any

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    raise ImportError(
        "需要安裝 fastapi 與 uvicorn：\n"
        "  pip install 'reachy_mini_simulator[web]'\n"
        "  或 pip install fastapi 'uvicorn[standard]'"
    )

from .ai_brain import AIBrain, BrainResponse
from .expression import ExpressionEngine
from .mock_robot import MockReachyMini
from .scenario import ScenarioEngine, SimEvent, SimPerson
from .office_map import create_default_office, OfficeMap, CellType
from .navigation import Navigator, a_star, create_default_patrol
from .calendar_mock import CalendarMock

# ── 全域模擬器狀態 ────────────────────────────────────────────

_office_map: OfficeMap | None = None
_robot: MockReachyMini | None = None
_scenario: ScenarioEngine | None = None
_navigator: Navigator | None = None
_calendar: CalendarMock | None = None
_brain: AIBrain | None = None
_expression: ExpressionEngine | None = None
_event_log: list[dict[str, Any]] = []
_sim_lock = threading.Lock()

# 模擬時間參數
_OFFICE_START_MINUTES = 8 * 60 + 50  # 08:50
_SIM_TO_OFFICE_RATIO = 6.0  # 1 模擬秒 = 6 辦公分鐘
_SIM_DT = 0.5
_speed_multiplier = 1.0
_paused = False
_sim_running = False

# WebSocket 連線管理
_ws_connections: set[WebSocket] = set()


def _sim_to_office_minutes(sim_time: float) -> float:
    """將模擬時間轉換為辦公時間（分鐘）。"""
    return _OFFICE_START_MINUTES + sim_time * _SIM_TO_OFFICE_RATIO


def _office_minutes_str(minutes: float) -> str:
    """格式化辦公時間為 HH:MM 字串。"""
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"


def _add_event(message: str, category: str = "system") -> None:
    """新增事件到日誌。"""
    sim_time = _scenario.current_time if _scenario else 0.0
    office_min = _sim_to_office_minutes(sim_time)
    _event_log.append({
        "time": _office_minutes_str(office_min),
        "message": message,
        "category": category,
        "sim_time": sim_time,
    })


def _create_demo_scenario() -> list[SimEvent]:
    """建立 demo 用的辦公室一日場景。"""
    return [
        SimEvent(time=5, event_type="idle", data={"message": "早安！"}),
        SimEvent(time=15, event_type="person_appears", data={
            "name": "David", "position": [18, 5], "location": "大門",
        }),
        SimEvent(time=18, event_type="user_speaks", data={
            "name": "David", "text": "早安！今天天氣真好",
        }),
        SimEvent(time=25, event_type="person_moves", data={
            "name": "David", "position": [16, 1], "location": "辦公桌1",
        }),
        SimEvent(time=30, event_type="calendar_event", data={
            "title": "每日站會", "room": "會議室A", "in_minutes": 5,
        }),
        SimEvent(time=40, event_type="person_appears", data={
            "name": "Amy", "position": [18, 5], "location": "大門",
        }),
        SimEvent(time=60, event_type="idle", data={}),
        SimEvent(time=75, event_type="calendar_event", data={
            "title": "週會", "room": "會議室C", "in_minutes": 5,
        }),
        SimEvent(time=95, event_type="person_appears", data={
            "name": "訪客", "position": [18, 6], "location": "大門",
        }),
        SimEvent(time=100, event_type="user_speaks", data={
            "name": "訪客", "text": "請問會議室在哪裡？",
        }),
        SimEvent(time=115, event_type="person_leaves", data={"name": "Amy"}),
        SimEvent(time=130, event_type="idle", data={}),
        SimEvent(time=140, event_type="calendar_event", data={
            "title": "1-on-1", "room": "會議室B", "in_minutes": 5,
        }),
        SimEvent(time=155, event_type="person_leaves", data={"name": "訪客"}),
        SimEvent(time=170, event_type="person_leaves", data={"name": "David"}),
        SimEvent(time=180, event_type="idle", data={
            "message": "大家都走了...回去充電了",
        }),
    ]


def _handle_scenario_event(event: SimEvent) -> None:
    """處理場景事件（在模擬執行緒中呼叫）。"""
    global _navigator, _robot, _brain

    if event.event_type == "person_appears":
        name = event.data["name"]
        loc = event.data.get("location", "")
        _add_event(f"{name} 出現在{loc}", "person")
        if _brain:
            _brain.handle_event("person_appears", event.data)
        if loc == "大門" and _navigator and _robot:
            _navigator.navigate_to("大門", from_pos=_robot.position)

    elif event.event_type == "person_leaves":
        name = event.data["name"]
        _add_event(f"{name} 離開了", "leave")
        if _brain:
            _brain.handle_event("person_leaves", event.data)

    elif event.event_type == "calendar_event":
        title = event.data["title"]
        room = event.data["room"]
        in_min = event.data["in_minutes"]
        _add_event(f"行事曆: {title} @ {room}（{in_min} 分鐘後）", "calendar")
        if _brain:
            _brain.handle_event("calendar_event", event.data)
        if _navigator and _robot:
            _navigator.navigate_to(room, from_pos=_robot.position)

    elif event.event_type == "user_speaks":
        name = event.data.get("name", "???")
        text = event.data.get("text", "")
        _add_event(f'{name}: "{text}"', "user")
        if _brain:
            _brain.handle_event("user_speaks", event.data)

    elif event.event_type == "idle":
        if _brain:
            _brain.handle_event("idle", event.data)
        if _navigator and _robot and not _navigator.is_navigating:
            _navigator.navigate_to("走廊中心", from_pos=_robot.position)

    elif event.event_type == "person_moves":
        name = event.data.get("name", "")
        loc = event.data.get("location", "")
        if name and loc:
            _add_event(f"{name} 移動到{loc}", "system")


def _init_simulation() -> None:
    """初始化模擬器各模組。"""
    global _office_map, _robot, _scenario, _navigator, _calendar
    global _brain, _expression, _event_log

    _office_map = create_default_office()
    charger = _office_map.get_location("充電站")
    _robot = MockReachyMini(
        position=(float(charger.position[0]), float(charger.position[1])),
        speed=3.0,
    )
    _scenario = ScenarioEngine()
    _navigator = Navigator(_office_map)
    _calendar = CalendarMock()
    _brain = AIBrain()
    _expression = ExpressionEngine()

    # AI 回應回呼
    def _on_brain_response(resp: BrainResponse) -> None:
        emotion_tag = f"[{resp.emotion}]" if resp.emotion else ""
        _add_event(f"Robot: {emotion_tag} {resp.text}", "robot")
        if resp.emotion and _expression:
            _expression.trigger_emotion(resp.emotion)

    def _on_processing_start() -> None:
        if _expression:
            _expression.set_state("PROCESSING")

    def _on_processing_end() -> None:
        if _expression:
            _expression.set_state("IDLE")

    _brain.on_response = _on_brain_response
    _brain.on_processing_start = _on_processing_start
    _brain.on_processing_end = _on_processing_end
    _brain.start()

    # 載入場景
    _event_log = []
    events = _create_demo_scenario()
    _scenario.load(events)
    _scenario.on_event = _handle_scenario_event
    _scenario.set_speed(1.0)
    _scenario.start()

    _add_event("系統啟動...", "system")
    logger.info("模擬器初始化完成")


def _simulation_loop() -> None:
    """模擬主迴圈（在背景執行緒中執行）。"""
    global _sim_running, _paused, _speed_multiplier

    _sim_running = True
    while _sim_running:
        if not _paused and _scenario and _robot and _navigator and _calendar:
            with _sim_lock:
                effective_dt = _SIM_DT * _speed_multiplier
                _scenario.tick(effective_dt)

                office_min = _sim_to_office_minutes(_scenario.current_time)
                _calendar.set_current_time(office_min)

                _navigator.update(effective_dt, _robot)

                # 天線呼吸動畫
                t = _scenario.current_time
                breath = 0.15 * math.sin(2 * math.pi * 0.3 * t)
                if _navigator.is_navigating:
                    _robot.set_target(antennas=[0.3 + breath, 0.3 + breath])
                else:
                    _robot.set_target(antennas=[breath, breath])

        time.sleep(0.15)


def _get_full_state() -> dict[str, Any]:
    """取得完整的模擬器狀態快照（供 WebSocket 推送用）。"""
    if not _robot or not _scenario or not _navigator or not _calendar:
        return {}

    state = _robot.get_state_summary()
    office_min = _sim_to_office_minutes(_scenario.current_time)

    persons = {}
    for name, person in _scenario.persons.items():
        if person.is_visible:
            persons[name] = {
                "position": list(person.position),
                "is_visible": True,
            }

    nav_path = []
    if _navigator.is_navigating:
        nav_path = [list(p) for p in _navigator.remaining_path]

    current_meeting = _calendar.get_current()
    next_meeting = _calendar.get_next()

    return {
        "robot": {
            "position": list(state["position"]),
            "heading": state["heading"],
            "antenna_pos": state["antenna_pos"],
            "antenna_pos_deg": state["antenna_pos_deg"],
            "head_yaw_deg": state["head_yaw_deg"],
            "head_pitch_deg": state["head_pitch_deg"],
            "body_yaw_deg": state["body_yaw_deg"],
            "is_moving": state["is_moving"],
            "move_target": list(state["move_target"]) if state["move_target"] else None,
        },
        "nav_target": _navigator.current_target,
        "nav_path": nav_path,
        "persons": persons,
        "time": {
            "office_time": _office_minutes_str(office_min),
            "office_minutes": office_min,
            "sim_time": _scenario.current_time,
            "speed": _speed_multiplier,
            "paused": _paused,
            "finished": _scenario.is_finished and not _navigator.is_navigating,
        },
        "calendar": {
            "current": str(current_meeting) if current_meeting else None,
            "next": str(next_meeting) if next_meeting else None,
            "meetings": [
                {
                    "title": m.title,
                    "start": m.start_time_str(),
                    "end": m.end_time_str(),
                    "room": m.room,
                    "participants": m.participants,
                }
                for m in _calendar.meetings
            ],
        },
    }


# ── FastAPI 應用 ────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(application: FastAPI):
    """應用生命週期管理。"""
    # 啟動
    _init_simulation()
    sim_thread = threading.Thread(target=_simulation_loop, daemon=True)
    sim_thread.start()
    asyncio.create_task(_ws_broadcast_loop())
    logger.info("Web 伺服器已啟動")
    yield
    # 關閉
    global _sim_running
    _sim_running = False
    if _brain:
        _brain.stop()
    if _robot:
        _robot.close()
    logger.info("Web 伺服器已關閉")


app = FastAPI(
    title="Reachy Mini 模擬器 Web API",
    version="0.1.0",
    lifespan=_lifespan,
)


# ── REST API ────────────────────────────────────────────────────

@app.get("/api/state")
async def get_state() -> dict[str, Any]:
    """取得機器人及模擬器狀態摘要。"""
    with _sim_lock:
        return _get_full_state()


@app.get("/api/map")
async def get_map() -> dict[str, Any]:
    """取得地圖資料（JSON 格式）。"""
    if not _office_map:
        return {"error": "地圖尚未初始化"}

    named_locs = {}
    for name, loc in _office_map.named_locations.items():
        named_locs[name] = {
            "position": list(loc.position),
            "cell_type": loc.cell_type,
        }

    return {
        "width": _office_map.width,
        "height": _office_map.height,
        "grid": _office_map.grid.tolist(),
        "cell_types": {
            "EMPTY": int(CellType.EMPTY),
            "WALL": int(CellType.WALL),
            "DOOR": int(CellType.DOOR),
            "DESK": int(CellType.DESK),
            "CHAIR": int(CellType.CHAIR),
            "CHARGER": int(CellType.CHARGER),
        },
        "named_locations": named_locs,
    }


@app.get("/api/events")
async def get_events() -> dict[str, Any]:
    """取得事件日誌。"""
    return {"events": list(_event_log[-100:])}


@app.post("/api/navigate")
async def navigate(body: dict[str, Any]) -> dict[str, Any]:
    """導航到指定位置。

    body 格式：
        {"x": int, "y": int}  -- grid 座標
        或 {"location": str}  -- 具名位置名稱
    """
    if not _office_map or not _robot or not _navigator:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        if "location" in body:
            location_name = body["location"]
            success = _navigator.navigate_to(
                location_name, from_pos=_robot.position
            )
            if success:
                _add_event(f"使用者導航: → {location_name}", "robot")
                return {"success": True, "target": location_name}
            return {"success": False, "error": f"無法導航到 {location_name}"}

        gx = int(body.get("x", 0))
        gy = int(body.get("y", 0))

        if not _office_map.is_walkable(gx, gy):
            return {"success": False, "error": f"({gx},{gy}) 不可通行"}

        start = (
            int(round(_robot.position[0])),
            int(round(_robot.position[1])),
        )
        path = a_star(_office_map, start, (gx, gy))
        if path is None:
            return {"success": False, "error": f"找不到前往 ({gx},{gy}) 的路徑"}

        _navigator._path = path
        _navigator._path_index = 0
        _navigator._current_target = f"({gx},{gy})"
        _add_event(f"使用者導航: → ({gx},{gy})（{len(path)} 步）", "robot")

        return {"success": True, "target": f"({gx},{gy})", "steps": len(path)}


@app.post("/api/speak")
async def speak(body: dict[str, Any]) -> dict[str, Any]:
    """模擬使用者說話。

    body 格式：
        {"text": str, "name": str (可選)}
    """
    text = body.get("text", "").strip()
    if not text:
        return {"success": False, "error": "文字不可為空"}

    name = body.get("name", "使用者")

    with _sim_lock:
        _add_event(f'{name}: "{text}"', "user")
        if _brain:
            _brain.handle_event("user_speaks", {"name": name, "text": text})

    return {"success": True}


@app.post("/api/control")
async def control(body: dict[str, Any]) -> dict[str, Any]:
    """模擬控制指令。

    body 格式：
        {"action": "pause" | "resume" | "speed", "value": float (僅 speed)}
    """
    global _paused, _speed_multiplier

    action = body.get("action", "")

    if action == "pause":
        _paused = True
        return {"success": True, "paused": True}
    elif action == "resume":
        _paused = False
        return {"success": True, "paused": False}
    elif action == "speed":
        val = float(body.get("value", 1.0))
        _speed_multiplier = max(0.5, min(5.0, val))
        return {"success": True, "speed": _speed_multiplier}
    elif action == "reset":
        with _sim_lock:
            _init_simulation()
        return {"success": True}

    return {"success": False, "error": f"未知的動作: {action}"}


# ── WebSocket ────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """WebSocket 端點，即時推送模擬器狀態。"""
    await ws.accept()
    _ws_connections.add(ws)
    logger.info("WebSocket 連線建立，目前 %d 個連線", len(_ws_connections))

    try:
        while True:
            # 接收客戶端訊息（保持連線活躍）
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "navigate":
                    result = await navigate(msg)
                    await ws.send_json({"type": "navigate_result", **result})
                elif msg_type == "speak":
                    result = await speak(msg)
                    await ws.send_json({"type": "speak_result", **result})
                elif msg_type == "control":
                    result = await control(msg)
                    await ws.send_json({"type": "control_result", **result})

            except (json.JSONDecodeError, KeyError):
                pass

    except WebSocketDisconnect:
        pass
    finally:
        _ws_connections.discard(ws)
        logger.info("WebSocket 連線關閉，剩餘 %d 個連線", len(_ws_connections))


async def _ws_broadcast_loop() -> None:
    """定時廣播模擬器狀態到所有 WebSocket 連線。"""
    global _ws_connections
    last_event_count = 0

    while True:
        await asyncio.sleep(0.5)  # 每 500ms 推送

        if not _ws_connections:
            continue

        with _sim_lock:
            state = _get_full_state()
            # 檢查是否有新事件
            current_event_count = len(_event_log)
            new_events = []
            if current_event_count > last_event_count:
                new_events = _event_log[last_event_count:]
                last_event_count = current_event_count

        payload = json.dumps({
            "type": "state_update",
            "state": state,
            "new_events": new_events,
        })

        disconnected: set[WebSocket] = set()
        for ws in _ws_connections:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.add(ws)

        _ws_connections -= disconnected


# ── 靜態檔案與入口頁面 ──────────────────────────────────────────

from pathlib import Path

_WEB_DIR = Path(__file__).parent / "web"


@app.get("/")
async def index() -> HTMLResponse:
    """提供前端首頁。"""
    index_path = _WEB_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Reachy Mini 模擬器</h1><p>web/index.html 尚未建立</p>")


# 掛載靜態檔案（若目錄存在）
if _WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")


# ── 入口點 ────────────────────────────────────────────────────

def main() -> None:
    """啟動 Web 伺服器入口點。"""
    print("\n  Reachy Mini 辦公室助手模擬器 - Web 版\n")
    print("  開啟瀏覽器前往 http://localhost:8765\n")
    uvicorn.run(
        "reachy_mini_simulator.web_server:app",
        host="0.0.0.0",
        port=8765,
        log_level="info",
    )


if __name__ == "__main__":
    main()
