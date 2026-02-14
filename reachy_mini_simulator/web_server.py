"""Web 伺服器 - FastAPI + WebSocket 即時推送。

提供 REST API 與 WebSocket 介面，讓前端網頁可以即時取得模擬器狀態、
控制機器人導航與說話，並透過 WebSocket 接收即時更新。

REST API:
    GET  /api/state    - 機器人狀態摘要
    GET  /api/map      - 地圖資料（JSON）
    GET  /api/events   - 事件日誌
    POST /api/navigate - 導航到指定位置
    POST /api/speak    - 模擬說話輸入
    POST /api/voice/start  - 啟動語音監聽
    POST /api/voice/stop   - 停止語音監聽
    GET  /api/voice/status - 語音狀態

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
import os
import threading
import time
from typing import Any

from dotenv import load_dotenv
load_dotenv()

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
from .robot_interface import RobotInterface
from .mock_robot import MockReachyMini
from .person_detector import MockPersonDetector, PersonDetectorInterface, create_person_detector
from .proactive import ProactiveTrigger
from .scenario import ScenarioEngine, SimEvent, SimPerson
from .office_map import create_default_office, OfficeMap, CellType
from .navigation import Navigator, a_star, create_default_patrol
from .calendar_mock import CalendarMock
from .motion import Move

try:
    from .audio_input import AudioInput
    _HAS_AUDIO_INPUT = True
except ImportError:
    _HAS_AUDIO_INPUT = False

try:
    from .tts_engine import TTSEngine
    _HAS_TTS = True
except ImportError:
    _HAS_TTS = False

# ── 全域模擬器狀態 ────────────────────────────────────────────

_office_map: OfficeMap | None = None
_robot: RobotInterface | None = None
_robot_mode: str = "mock"  # "mock" 或 "real"
_scenario: ScenarioEngine | None = None
_navigator: Navigator | None = None
_calendar: CalendarMock | None = None
_brain: AIBrain | None = None
_expression: ExpressionEngine | None = None
_detector: PersonDetectorInterface | None = None
_proactive: ProactiveTrigger | None = None
_event_log: list[dict[str, Any]] = []
_last_recorded_move: Move | None = None
_sim_lock = threading.Lock()

# 對話 / 觸發記錄
_last_trigger_type: str | None = None
_last_trigger_time: float | None = None
_last_brain_response: BrainResponse | None = None
_chat_history: list[dict[str, Any]] = []

# 語音對話管線
_audio_input: Any = None  # AudioInput instance
_tts: Any = None  # TTSEngine instance
_voice_status: str = "idle"  # "idle" | "listening" | "processing" | "speaking"
_last_transcript: str | None = None

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
    """初始化模擬器各模組。

    根據環境變數 REACHY_MODE 決定使用 mock 或 real 模式：
    - mock（預設）：使用 MockReachyMini，包含完整模擬（地圖/導航/場景）
    - real：連接真實 Reachy Mini 機器人，跳過模擬器專屬邏輯
    """
    global _office_map, _robot, _robot_mode, _scenario, _navigator, _calendar
    global _brain, _expression, _event_log
    global _detector, _proactive
    global _last_trigger_type, _last_trigger_time, _last_brain_response, _chat_history
    global _audio_input, _tts, _voice_status, _last_transcript

    _robot_mode = os.environ.get("REACHY_MODE", "mock").lower()

    if _robot_mode == "real":
        # ── Real 模式：連接真實機器人 ──
        try:
            from .factory import create_robot
            _robot = create_robot(mode="real")
            _robot.wake_up()
            logger.info("已連接真實 Reachy Mini 機器人")
        except Exception as e:
            logger.error("無法連接真實機器人: %s，退回 mock 模式", e)
            _robot_mode = "mock"

    if _robot_mode == "mock":
        # ── Mock 模式：完整模擬 ──
        _office_map = create_default_office()
        charger = _office_map.get_location("充電站")
        _robot = MockReachyMini(
            position=(float(charger.position[0]), float(charger.position[1])),
            speed=3.0,
        )

    _scenario = ScenarioEngine()
    if _robot_mode == "mock" and _office_map:
        _navigator = Navigator(_office_map)
    _calendar = CalendarMock()
    _brain = AIBrain()
    _expression = ExpressionEngine()

    # 初始化人物偵測器和主動觸發器
    _detector = MockPersonDetector()
    _proactive = ProactiveTrigger(detector=_detector)

    _last_trigger_type = None
    _last_trigger_time = None
    _last_brain_response = None
    _chat_history = []

    def _on_proactive_trigger(trigger_type: str, prompt_text: str) -> None:
        global _last_trigger_type, _last_trigger_time
        _last_trigger_type = trigger_type
        _last_trigger_time = time.time()
        _add_event(f"主動觸發: [{trigger_type}]", "system")
        if _brain:
            _brain.inject(prompt_text, f"proactive_{trigger_type}")

    _proactive.on_trigger = _on_proactive_trigger
    _detector.start()
    _proactive.start()

    # AI 回應回呼
    def _on_brain_response(resp: BrainResponse) -> None:
        global _last_brain_response, _tts
        _last_brain_response = resp
        emotion_tag = f"[{resp.emotion}]" if resp.emotion else ""
        _add_event(f"Robot: {emotion_tag} {resp.text}", "robot")
        _chat_history.append({
            "role": "robot",
            "text": resp.text,
            "emotion": resp.emotion,
            "event_type": resp.event_type,
            "time": time.time(),
        })
        if resp.emotion and _expression:
            _expression.trigger_emotion(resp.emotion)
        # TTS 播放
        if _tts and resp.text:
            _tts.speak(resp.text)
        if resp.nav_target and _navigator and _robot:
            success = _navigator.navigate_to(resp.nav_target, from_pos=_robot.position)
            if success:
                _add_event(f"AI 導航: → {resp.nav_target}", "robot")

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

    # ── 語音對話管線 ──
    _voice_status = "idle"
    _last_transcript = None

    if _HAS_TTS:
        if _robot_mode == "real":
            _tts = TTSEngine(robot=_robot)
        else:
            _tts = TTSEngine()
        logger.warning("TTS 初始化: available=%s, api_key_len=%d, robot=%s",
                        _tts.available, len(_tts._api_key), _tts._robot is not None)

        def _on_speak_start():
            global _voice_status
            _voice_status = "speaking"
            if _expression:
                _expression.set_state("SPEAKING")
            if _audio_input:
                _audio_input.paused = True  # 避免迴聲

        def _on_speak_end():
            global _voice_status
            _voice_status = "listening" if (_audio_input and not _audio_input._stop.is_set()) else "idle"
            if _expression:
                _expression.set_state("IDLE")
            if _audio_input:
                _audio_input.paused = False

        _tts.on_speak_start = _on_speak_start
        _tts.on_speak_end = _on_speak_end
        _tts.start()

    if _HAS_AUDIO_INPUT:
        def _handle_transcript(text: str) -> None:
            global _voice_status, _last_transcript
            _last_transcript = text
            _voice_status = "processing"
            if _expression:
                _expression.set_state("PROCESSING")
            _add_event(f"語音辨識: {text}", "user")
            # 記錄到對話歷史
            _chat_history.append({
                "role": "user",
                "text": text,
                "name": "使用者(語音)",
                "time": time.time(),
            })
            # 注入 AI Brain
            if _brain:
                _brain.handle_event("user_speaks", {"name": "使用者", "text": text})

        _audio_input = AudioInput(on_transcript=_handle_transcript)

    _add_event("系統啟動...", "system")
    logger.info("模擬器初始化完成")


def _simulation_loop() -> None:
    """模擬主迴圈（在背景執行緒中執行）。"""
    global _sim_running, _paused, _speed_multiplier

    _sim_running = True
    while _sim_running:
        if not _paused and _robot:
            with _sim_lock:
                effective_dt = _SIM_DT * _speed_multiplier

                if _robot_mode == "mock":
                    # ── Mock 模式專屬邏輯 ──
                    if _scenario:
                        _scenario.tick(effective_dt)
                    if _scenario and _calendar:
                        office_min = _sim_to_office_minutes(_scenario.current_time)
                        _calendar.set_current_time(office_min)
                    if _navigator:
                        _navigator.update(effective_dt, _robot)

                    # Mock 專屬：插值引擎 / 動作播放 / 錄製
                    if hasattr(_robot, '_interp_engine'):
                        interp_result = _robot._interp_engine.tick(effective_dt)
                        if interp_result:
                            _robot.set_target(**interp_result)
                    if hasattr(_robot, '_motion_player'):
                        _robot._motion_player.tick(effective_dt, _robot)
                    if hasattr(_robot, '_motion_recorder') and _robot._motion_recorder.is_recording:
                        _robot._motion_recorder.capture(_robot)

                    # 天線呼吸動畫（Mock 模式）
                    no_anim = (
                        hasattr(_robot, '_interp_engine') and not _robot._interp_engine.is_active
                        and hasattr(_robot, '_motion_player') and not _robot._motion_player.is_playing
                    )
                    if no_anim:
                        t = _scenario.current_time if _scenario else 0
                        breath = 0.15 * math.sin(2 * math.pi * 0.3 * t)
                        if _navigator and _navigator.is_navigating:
                            _robot.set_target(antennas=[0.3 + breath, 0.3 + breath])
                        else:
                            _robot.set_target(antennas=[breath, breath])

                # ── 共通邏輯（mock + real 都執行）──

                # 更新人物偵測
                if _detector and _detector.is_running:
                    _detector.update(effective_dt)

                # 更新主動觸發
                if _proactive and _proactive.is_running:
                    _proactive.update(effective_dt)

                # 表情引擎（real 模式也套用）
                if _expression and _robot:
                    _expression.update(_robot)

        time.sleep(0.15)


def _get_full_state() -> dict[str, Any]:
    """取得完整的模擬器狀態快照（供 WebSocket 推送用）。"""
    if not _robot:
        return {}

    state = _robot.get_state_summary()

    # Mock 模式專屬資料
    office_min = 0
    persons = {}
    nav_path = []

    if _robot_mode == "mock" and _scenario and _navigator and _calendar:
        office_min = _sim_to_office_minutes(_scenario.current_time)
        for name, person in _scenario.persons.items():
            if person.is_visible:
                persons[name] = {
                    "position": list(person.position),
                    "is_visible": True,
                }
        if _navigator.is_navigating:
            nav_path = [list(p) for p in _navigator.remaining_path]

    current_meeting = _calendar.get_current()
    next_meeting = _calendar.get_next()

    # 機器人狀態（相容 mock / real）
    robot_state = {
        "mode": _robot_mode,
        "is_awake": _robot.is_awake,
        "imu": _robot.get_imu_data(),
        "joints": _robot.get_current_joint_positions(),
    }

    if _robot_mode == "mock":
        robot_state.update({
            "position": list(state.get("position", (0, 0))),
            "heading": state.get("heading", 0),
            "antenna_pos": state.get("antenna_pos", [0, 0]),
            "antenna_pos_deg": state.get("antenna_pos_deg", [0, 0]),
            "head_yaw_deg": state.get("head_yaw_deg", 0),
            "head_pitch_deg": state.get("head_pitch_deg", 0),
            "body_yaw_deg": state.get("body_yaw_deg", 0),
            "is_moving": state.get("is_moving", False),
            "move_target": list(state["move_target"]) if state.get("move_target") else None,
            "motor_states": {
                name: _robot.is_motor_enabled(name)
                for name in ["head_roll", "head_pitch", "head_yaw", "antenna_right", "antenna_left", "body_yaw"]
            },
            "gravity_compensation": _robot._gravity_compensation if hasattr(_robot, '_gravity_compensation') else False,
            "is_recording": _robot.media.is_recording,
            "is_sound_playing": _robot.media.is_sound_playing(),
            "is_motion_playing": _robot.is_motion_playing,
        })
    else:
        # Real 模式：從 SDK 直接讀取
        robot_state.update({
            "antenna_pos": list(_robot.antenna_pos),
            "head_pose": _robot.head_pose.tolist() if hasattr(_robot.head_pose, 'tolist') else _robot.head_pose,
            "body_yaw": _robot.body_yaw,
            "is_moving": state.get("is_moving", False),
        })

    # 導航和時間（mock 專屬）
    nav_target = None
    time_info = {"speed": _speed_multiplier, "paused": _paused}
    calendar_info = {}

    if _robot_mode == "mock" and _scenario and _navigator and _calendar:
        nav_target = _navigator.current_target
        current_meeting = _calendar.get_current()
        next_meeting = _calendar.get_next()
        time_info.update({
            "office_time": _office_minutes_str(office_min),
            "office_minutes": office_min,
            "sim_time": _scenario.current_time,
            "finished": _scenario.is_finished and not _navigator.is_navigating,
        })
        calendar_info = {
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
        }

    return {
        "robot": robot_state,
        "nav_target": nav_target,
        "nav_path": nav_path,
        "persons": persons,
        "time": time_info,
        "calendar": calendar_info,
        "perception": {
            "mode": "mock" if isinstance(_detector, MockPersonDetector) else "yolo" if _detector else "none",
            "person_visible": _detector.person_visible if _detector else False,
            "person_count": _detector.person_count if _detector else 0,
            "persons": _detector.get_persons() if isinstance(_detector, MockPersonDetector) else {},
            "absence_duration": _detector.get_person_absence_duration() if _detector else 0.0,
            "is_running": _detector.is_running if _detector else False,
        },
        "proactive": {
            "enabled": _proactive.enabled if _proactive else False,
            "is_running": _proactive.is_running if _proactive else False,
            "last_trigger_type": _last_trigger_type,
            "last_trigger_time": _last_trigger_time,
        },
        "conversation": {
            "last_response": _last_brain_response.text if _last_brain_response else None,
            "last_emotion": _last_brain_response.emotion if _last_brain_response else None,
            "history_count": len(_chat_history),
        },
        "voice": {
            "status": _voice_status,
            "is_listening": (not _audio_input._stop.is_set() and _audio_input._vad_thread is not None and _audio_input._vad_thread.is_alive()) if _audio_input and hasattr(_audio_input, '_stop') else False,
            "last_transcript": _last_transcript,
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
    if _tts:
        _tts.stop()
    if _audio_input:
        _audio_input.stop()
    if _proactive:
        _proactive.stop()
    if _detector:
        _detector.stop()
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


# ── Phase 4A: 新增 REST API 端點 ────────────────────────────────

@app.post("/api/goto_target")
async def goto_target(body: dict[str, Any]) -> dict[str, Any]:
    """插值目標設定。

    body: {head: list (4x4 nested), antennas: [r, l], body_yaw: float,
           duration: float, method: str}
    """
    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        try:
            import numpy as np
            head = None
            if "head" in body:
                head = np.array(body["head"], dtype=np.float64)
            antennas = body.get("antennas")
            body_yaw = body.get("body_yaw")
            duration = float(body.get("duration", 1.0))
            method = body.get("method", "MIN_JERK")

            _robot.goto_target(
                head=head,
                antennas=antennas,
                body_yaw=body_yaw,
                duration=duration,
                method=method,
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


@app.post("/api/look_at")
async def look_at(body: dict[str, Any]) -> dict[str, Any]:
    """凝視追蹤。

    body: {mode: "image", u: float, v: float}
       或 {mode: "world", x: float, y: float, z: float}
    """
    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        try:
            mode = body.get("mode", "image")
            if mode == "image":
                u = float(body.get("u", 0.5))
                v = float(body.get("v", 0.5))
                _robot.look_at_image(u, v)
            elif mode == "world":
                x = float(body.get("x", 1.0))
                y = float(body.get("y", 0.0))
                z = float(body.get("z", 0.0))
                _robot.look_at_world(x, y, z)
            else:
                return {"success": False, "error": f"未知的模式: {mode}"}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}


@app.post("/api/wake_up")
async def wake_up_endpoint() -> dict[str, Any]:
    """喚醒機器人。"""
    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        _robot.wake_up()
        return {"success": True, "is_awake": True}


@app.post("/api/goto_sleep")
async def goto_sleep_endpoint() -> dict[str, Any]:
    """讓機器人睡眠。"""
    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        _robot.goto_sleep()
        return {"success": True, "is_awake": False}


@app.post("/api/motor")
async def motor_control(body: dict[str, Any]) -> dict[str, Any]:
    """馬達控制。body: {motor_name: str, enabled: bool}"""
    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        try:
            motor_name = body.get("motor_name", "")
            enabled = bool(body.get("enabled", True))
            _robot.set_motor_enabled(motor_name, enabled)
            return {"success": True, "motor_name": motor_name, "enabled": enabled}
        except ValueError as e:
            return {"success": False, "error": str(e)}


@app.post("/api/play_sound")
async def play_sound_endpoint(body: dict[str, Any]) -> dict[str, Any]:
    """播放音檔。body: {file_path: str}"""
    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        file_path = body.get("file_path", "")
        if not file_path:
            return {"success": False, "error": "file_path 不可為空"}
        _robot.media.play_sound(file_path)
        return {"success": True}


@app.post("/api/record")
async def record_control(body: dict[str, Any]) -> dict[str, Any]:
    """錄音控制。body: {action: "start"|"stop"|"get_sample"}"""
    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        action = body.get("action", "")
        if action == "start":
            _robot.media.start_recording()
            return {"success": True, "is_recording": True}
        elif action == "stop":
            _robot.media.stop_recording()
            return {"success": True, "is_recording": False}
        elif action == "get_sample":
            sample = _robot.media.get_audio_sample()
            if sample is not None:
                return {"success": True, "sample_length": len(sample)}
            return {"success": True, "sample_length": 0}
        return {"success": False, "error": f"未知的動作: {action}"}


@app.post("/api/motion")
async def motion_control(body: dict[str, Any]) -> dict[str, Any]:
    """動作錄製/回放。

    body: {action: "start_record"|"stop_record"|"play"|"stop",
           move: dict (for play), speed: float (for play)}
    """
    global _last_recorded_move

    if not _robot:
        return {"success": False, "error": "模擬器尚未初始化"}

    with _sim_lock:
        action = body.get("action", "")

        if action == "start_record":
            _robot.start_motion_recording()
            return {"success": True, "recording": True}

        elif action == "stop_record":
            move = _robot.stop_motion_recording()
            _last_recorded_move = move
            return {
                "success": True,
                "recording": False,
                "frames": len(move.frames),
                "duration": move.duration,
            }

        elif action == "play":
            move_data = body.get("move")
            speed = float(body.get("speed", 1.0))
            if move_data:
                move = Move.from_dict(move_data)
            elif _last_recorded_move:
                move = _last_recorded_move
            else:
                return {"success": False, "error": "沒有可回放的動作"}
            _robot.play_motion(move, speed)
            return {"success": True, "playing": True}

        elif action == "stop":
            _robot._motion_player.stop()
            return {"success": True, "playing": False}

        return {"success": False, "error": f"未知的動作: {action}"}


@app.get("/api/imu")
async def get_imu() -> dict[str, Any]:
    """取得 IMU 數據。"""
    if not _robot:
        return {"error": "模擬器尚未初始化"}

    with _sim_lock:
        return _robot.get_imu_data()


@app.get("/api/joints")
async def get_joints() -> dict[str, Any]:
    """取得關節角度。"""
    if not _robot:
        return {"error": "模擬器尚未初始化"}

    with _sim_lock:
        return _robot.get_current_joint_positions()


@app.get("/api/doa")
async def get_doa_endpoint() -> dict[str, Any]:
    """取得聲源方向。"""
    if not _robot:
        return {"error": "模擬器尚未初始化"}

    with _sim_lock:
        return {"doa": _robot.media.get_doa()}


# ── 人物感知 + 主動對話 REST API ─────────────────────────────────

@app.get("/api/perception")
async def get_perception() -> dict[str, Any]:
    """回傳人物偵測狀態。"""
    if _detector is None:
        return {"error": "detector not initialized"}
    with _sim_lock:
        return {
            "mode": "mock" if isinstance(_detector, MockPersonDetector) else "yolo",
            "person_visible": _detector.person_visible,
            "person_count": _detector.person_count,
            "person_positions": _detector.person_positions,
            "persons": _detector.get_persons() if isinstance(_detector, MockPersonDetector) else {},
            "absence_duration": _detector.get_person_absence_duration(),
            "is_running": _detector.is_running,
        }


@app.post("/api/perception/inject")
async def inject_person(data: dict[str, Any]) -> dict[str, Any]:
    """手動注入人物（mock 模式）。

    data: {"name": "David", "position": [0.5, 0.5]}
    """
    if not isinstance(_detector, MockPersonDetector):
        return {"success": False, "error": "只有 mock 模式可手動注入"}

    name = data.get("name", "").strip()
    if not name:
        return {"success": False, "error": "name 不可為空"}

    position = data.get("position", [0.5, 0.5])
    if isinstance(position, list) and len(position) == 2:
        pos = (float(position[0]), float(position[1]))
    else:
        pos = (0.5, 0.5)

    with _sim_lock:
        _detector.inject_person(name, pos)
        _add_event(f"手動注入人物: {name}", "person")

    return {"success": True, "name": name, "position": list(pos)}


@app.post("/api/perception/remove")
async def remove_person(data: dict[str, Any]) -> dict[str, Any]:
    """移除人物（mock 模式）。

    data: {"name": "David"}
    """
    if not isinstance(_detector, MockPersonDetector):
        return {"success": False, "error": "只有 mock 模式可手動移除"}

    name = data.get("name", "").strip()
    if not name:
        return {"success": False, "error": "name 不可為空"}

    with _sim_lock:
        _detector.remove_person(name)
        _add_event(f"手動移除人物: {name}", "leave")

    return {"success": True, "name": name}


@app.get("/api/proactive/status")
async def get_proactive_status() -> dict[str, Any]:
    """回傳主動觸發狀態。"""
    return {
        "enabled": _proactive.enabled if _proactive else False,
        "is_running": _proactive.is_running if _proactive else False,
        "greet_cooldown": _proactive.greet_cooldown if _proactive else 0,
        "idle_timeout": _proactive.idle_timeout if _proactive else 0,
        "last_trigger_type": _last_trigger_type,
        "last_trigger_time": _last_trigger_time,
    }


@app.post("/api/proactive/config")
async def update_proactive_config(data: dict[str, Any]) -> dict[str, Any]:
    """更新主動觸發設定。

    data: {"enabled": true, "greet_cooldown": 30, "idle_timeout": 120}
    """
    if _proactive is None:
        return {"success": False, "error": "proactive not initialized"}

    if "enabled" in data:
        _proactive.enabled = bool(data["enabled"])
    if "greet_cooldown" in data:
        _proactive._greet_cooldown = float(data["greet_cooldown"])
    if "idle_timeout" in data:
        _proactive._idle_timeout = float(data["idle_timeout"])

    return {
        "success": True,
        "enabled": _proactive.enabled,
        "greet_cooldown": _proactive.greet_cooldown,
        "idle_timeout": _proactive.idle_timeout,
    }


@app.post("/api/chat")
async def send_chat(data: dict[str, Any]) -> dict[str, Any]:
    """手動發送對話訊息。

    data: {"message": "你好", "name": "使用者"}
    """
    message = data.get("message", "").strip()
    if not message:
        return {"success": False, "error": "message 不可為空"}

    name = data.get("name", "使用者")

    with _sim_lock:
        _add_event(f'{name}: "{message}"', "user")
        _chat_history.append({
            "role": "user",
            "text": message,
            "name": name,
            "time": time.time(),
        })
        if _brain:
            _brain.handle_event("user_speaks", {"name": name, "text": message})
        if _proactive:
            _proactive.reset_idle_timer()

    return {"success": True}


@app.get("/api/chat/history")
async def get_chat_history() -> dict[str, Any]:
    """回傳對話歷史。"""
    return {"history": list(_chat_history[-100:])}


# ── 語音對話 REST API ────────────────────────────────────────────

@app.post("/api/voice/start")
async def voice_start():
    """啟動語音監聽。"""
    global _voice_status
    if not _HAS_AUDIO_INPUT or not _audio_input:
        return {"success": False, "error": "AudioInput 未安裝"}
    _audio_input.start()
    _voice_status = "listening"
    if _expression:
        _expression.set_state("LISTENING")
    return {"success": True, "status": "listening"}


@app.post("/api/voice/stop")
async def voice_stop():
    """停止語音監聽。"""
    global _voice_status
    if _audio_input:
        _audio_input.stop()
    _voice_status = "idle"
    if _expression:
        _expression.set_state("IDLE")
    return {"success": True, "status": "idle"}


@app.get("/api/voice/status")
async def voice_status():
    """取得語音狀態。"""
    return {
        "status": _voice_status,
        "is_listening": (not _audio_input._stop.is_set() and _audio_input._vad_thread is not None and _audio_input._vad_thread.is_alive()) if _audio_input and hasattr(_audio_input, '_stop') else False,
        "is_speaking": not _tts._stop.is_set() and not _tts._queue.empty() if _tts and hasattr(_tts, '_stop') else False,
        "last_transcript": _last_transcript,
        "has_audio_input": _HAS_AUDIO_INPUT,
        "has_tts": _HAS_TTS,
    }


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
