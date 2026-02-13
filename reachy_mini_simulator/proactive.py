"""主動觸發系統 — 偵測人物事件 + 閒置超時 → 主動發起對話。

綁定 PersonDetectorInterface 的回呼，當偵測到人物出現、離開或
長時間閒置時，透過 on_trigger 回呼通知上層（例如 AIBrain.inject）。
"""

from __future__ import annotations

import logging
import time
from typing import Callable

from .person_detector import PersonDetectorInterface

logger = logging.getLogger(__name__)

# ── 預設提示文字 ─────────────────────────────────────────
GREET_PROMPT = "有人出現在附近，請主動友善地打招呼。"
FAREWELL_PROMPT = "附近的人已經離開了，請說聲再見。"
IDLE_PROMPT = "對方已經沉默了一段時間，請主動關心一下。"


class ProactiveTrigger:
    """主動觸發器 — 監控人物事件與閒置狀態，觸發對話。

    用法::

        trigger = ProactiveTrigger(detector)
        trigger.on_trigger = lambda t, p: brain.inject(p, f"proactive_{t}")
        trigger.start()

    Args:
        detector: PersonDetectorInterface 實例。
        greet_cooldown: 打招呼冷卻秒數，預設 30 秒。
        idle_timeout: 閒置觸發秒數，預設 120 秒。
    """

    def __init__(
        self,
        detector: PersonDetectorInterface,
        greet_cooldown: float = 30.0,
        idle_timeout: float = 120.0,
    ) -> None:
        self._detector = detector
        self._greet_cooldown = greet_cooldown
        self._idle_timeout = idle_timeout

        self._running: bool = False
        self._enabled: bool = True

        # 冷卻 / 閒置狀態
        self._last_greet_time: float = 0.0
        self._idle_elapsed: float = 0.0
        self._idle_triggered: bool = False

        # 回呼
        self.on_trigger: Callable[[str, str], None] | None = None
        """觸發時的回呼 — callback(trigger_type, prompt_text)。"""

        # 綁定偵測器回呼
        self._detector.on_person_appeared = self._on_person_appeared
        self._detector.on_person_left = self._on_person_left

        logger.info(
            "ProactiveTrigger 已初始化：cooldown=%.1fs, idle_timeout=%.1fs",
            greet_cooldown,
            idle_timeout,
        )

    # ── 生命週期 ─────────────────────────────────────────

    def start(self) -> None:
        """啟動觸發器。"""
        self._running = True
        self._idle_elapsed = 0.0
        self._idle_triggered = False
        logger.info("ProactiveTrigger 已啟動")

    def stop(self) -> None:
        """停止觸發器。"""
        self._running = False
        logger.info("ProactiveTrigger 已停止")

    @property
    def is_running(self) -> bool:
        """觸發器是否正在運行。"""
        return self._running

    @property
    def greet_cooldown(self) -> float:
        """打招呼冷卻期（秒）。"""
        return self._greet_cooldown

    @property
    def idle_timeout(self) -> float:
        """閒置超時（秒）。"""
        return self._idle_timeout

    @property
    def enabled(self) -> bool:
        """觸發器是否啟用。"""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        logger.info("ProactiveTrigger enabled=%s", value)

    # ── 閒置管理 ─────────────────────────────────────────

    def reset_idle_timer(self) -> None:
        """重置閒置計時器（使用者互動時呼叫）。"""
        self._idle_elapsed = 0.0
        self._idle_triggered = False

    def update(self, dt: float) -> None:
        """每幀更新閒置計時。

        當有人在場且閒置超過 idle_timeout 時觸發一次 idle 事件。

        Args:
            dt: 時間差（秒）。
        """
        if not self._running or not self._enabled:
            return

        if not self._detector.person_visible:
            return

        self._idle_elapsed += dt

        if not self._idle_triggered and self._idle_elapsed >= self._idle_timeout:
            self._idle_triggered = True
            logger.info("ProactiveTrigger: 閒置觸發")
            self._fire("idle", IDLE_PROMPT)

    # ── 偵測器回呼 ───────────────────────────────────────

    def _on_person_appeared(self) -> None:
        """偵測到人物出現的回呼。"""
        if not self._running or not self._enabled:
            return

        now = time.time()
        if now - self._last_greet_time < self._greet_cooldown:
            logger.debug("ProactiveTrigger: 打招呼冷卻中，跳過")
            return

        self._last_greet_time = now
        self.reset_idle_timer()
        logger.info("ProactiveTrigger: 打招呼觸發")
        self._fire("greet", GREET_PROMPT)

    def _on_person_left(self) -> None:
        """偵測到人物離開的回呼。"""
        if not self._running or not self._enabled:
            return

        self.reset_idle_timer()
        logger.info("ProactiveTrigger: 道別觸發")
        self._fire("farewell", FAREWELL_PROMPT)

    # ── 內部 ─────────────────────────────────────────────

    def _fire(self, trigger_type: str, prompt_text: str) -> None:
        """觸發 on_trigger 回呼。"""
        if self.on_trigger is not None:
            self.on_trigger(trigger_type, prompt_text)
