"""場景引擎 - 事件驅動的模擬腳本執行器。

按照時間軸依序觸發辦公室事件（人物出現、離開、移動、行事曆提醒等），
驅動機器人做出對應行為。使用模擬時間而非真實時間，支援暫停、倍速等控制。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class SimEvent:
    """場景中的單一事件。

    Attributes:
        time: 模擬秒數（從 0 開始）。
        event_type: 事件類型，例如 "person_appears", "person_leaves",
                    "calendar_event", "person_moves", "idle", "user_speaks"。
        data: 事件附帶的資料字典。
    """

    time: float
    event_type: str
    data: dict = field(default_factory=dict)


@dataclass
class SimPerson:
    """場景中的人物狀態。

    Attributes:
        name: 人物名稱。
        position: 平面座標 (x, y)。
        is_visible: 是否在場景中可見。
    """

    name: str
    position: tuple[float, float] = (0.0, 0.0)
    is_visible: bool = True


class ScenarioEngine:
    """場景引擎 - 管理場景腳本的載入與逐幀推進。

    使用模擬時間，可透過 ``tick(dt)`` 手動推進。支援暫停、恢復及倍速播放。

    用法::

        engine = ScenarioEngine()
        engine.on_event = my_handler
        engine.load_from_json("scenarios/office_day.json")
        engine.start()
        while not engine.is_finished:
            engine.tick(1.0)
    """

    def __init__(self) -> None:
        self._events: list[SimEvent] = []
        self._event_index: int = 0
        self._current_time: float = 0.0
        self._running: bool = False
        self._paused: bool = False
        self._speed: float = 1.0

        self.persons: dict[str, SimPerson] = {}
        """當前場景中的所有人物，以名稱為鍵。"""

        self.on_event: Callable[[SimEvent], None] | None = None
        """事件觸發時的回呼函式。"""

    # -- 屬性 --

    @property
    def current_time(self) -> float:
        """當前模擬時間（秒）。"""
        return self._current_time

    @property
    def is_running(self) -> bool:
        """引擎是否正在執行中。"""
        return self._running and not self._paused

    @property
    def is_finished(self) -> bool:
        """所有事件是否已觸發完畢。"""
        return self._event_index >= len(self._events)

    @property
    def speed(self) -> float:
        """目前的播放倍速。"""
        return self._speed

    @property
    def total_events(self) -> int:
        """已載入的事件總數。"""
        return len(self._events)

    @property
    def triggered_count(self) -> int:
        """已觸發的事件數量。"""
        return self._event_index

    # -- 載入 --

    def load(self, events: list[SimEvent]) -> None:
        """載入場景腳本（SimEvent 列表）。

        事件會依照 ``time`` 欄位排序。載入後會重置引擎狀態。

        Args:
            events: SimEvent 物件列表。
        """
        self._events = sorted(events, key=lambda e: e.time)
        self._reset()
        logger.info("場景已載入，共 %d 個事件", len(self._events))

    def load_from_json(self, path: str) -> None:
        """從 JSON 檔案載入場景腳本。

        JSON 格式為陣列，每個元素包含 ``time``、``event_type``、``data`` 欄位。

        Args:
            path: JSON 檔案路徑。
        """
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        events = [
            SimEvent(
                time=item["time"],
                event_type=item["event_type"],
                data=item.get("data", {}),
            )
            for item in raw
        ]
        self.load(events)
        logger.info("從 %s 載入場景", path)

    # -- 控制 --

    def start(self) -> None:
        """開始模擬。重置時間與事件索引到起點。"""
        self._reset()
        self._running = True
        logger.info("場景引擎啟動")

    def stop(self) -> None:
        """停止模擬並重置狀態。"""
        self._running = False
        self._paused = False
        logger.info("場景引擎停止")

    def pause(self) -> None:
        """暫停模擬。"""
        self._paused = True
        logger.debug("場景引擎暫停")

    def resume(self) -> None:
        """恢復模擬。"""
        self._paused = False
        logger.debug("場景引擎恢復")

    def set_speed(self, multiplier: float) -> None:
        """設定播放倍速。

        Args:
            multiplier: 倍速值，1.0 為正常速度，2.0 為兩倍速。
        """
        if multiplier <= 0:
            raise ValueError("倍速值必須大於 0")
        self._speed = multiplier
        logger.debug("播放倍速設為 %.1fx", multiplier)

    # -- 推進 --

    def tick(self, dt: float) -> list[SimEvent]:
        """推進模擬時間，觸發到期的事件。

        Args:
            dt: 真實經過的秒數。會乘以倍速後加到模擬時間上。

        Returns:
            此次 tick 中觸發的事件列表。
        """
        if not self._running or self._paused:
            return []

        self._current_time += dt * self._speed
        triggered: list[SimEvent] = []

        while self._event_index < len(self._events):
            event = self._events[self._event_index]
            if event.time > self._current_time:
                break

            self._event_index += 1
            self._apply_event(event)
            triggered.append(event)

            logger.info(
                "[t=%.1f] 觸發事件: %s %s",
                event.time,
                event.event_type,
                event.data,
            )

            if self.on_event is not None:
                self.on_event(event)

        return triggered

    # -- 內部方法 --

    def _reset(self) -> None:
        """重置引擎到初始狀態（不清除已載入的事件）。"""
        self._event_index = 0
        self._current_time = 0.0
        self._paused = False
        self.persons.clear()

    def _apply_event(self, event: SimEvent) -> None:
        """根據事件類型更新場景狀態（人物位置等）。

        Args:
            event: 要處理的事件。
        """
        data = event.data

        if event.event_type == "person_appears":
            name = data["name"]
            pos = tuple(data.get("position", [0.0, 0.0]))
            self.persons[name] = SimPerson(
                name=name,
                position=(pos[0], pos[1]),
                is_visible=True,
            )

        elif event.event_type == "person_leaves":
            name = data["name"]
            if name in self.persons:
                self.persons[name].is_visible = False

        elif event.event_type == "person_moves":
            name = data["name"]
            pos = tuple(data.get("position", [0.0, 0.0]))
            if name in self.persons:
                self.persons[name].position = (pos[0], pos[1])
            else:
                # 若人物尚未出現，自動加入
                self.persons[name] = SimPerson(
                    name=name,
                    position=(pos[0], pos[1]),
                    is_visible=True,
                )

        # calendar_event, idle, user_speaks 不影響人物狀態，僅靠回呼處理
