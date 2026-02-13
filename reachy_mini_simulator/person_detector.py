"""人物感知模組 — 抽象介面 + Mock / YOLO 實作。

定義 PersonDetectorInterface 抽象基底類別，以及兩種實作：
- MockPersonDetector：手動注入模擬，供測試與情境引擎使用。
- YOLOPersonDetector：背景執行緒 YOLO 偵測，適配真實攝影機。
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from typing import Callable

logger = logging.getLogger(__name__)


class PersonDetectorInterface(ABC):
    """人物偵測器抽象基底類別。

    定義人物感知的統一介面，讓模擬偵測器和 YOLO 偵測器
    都遵循相同的操作方式。
    """

    def __init__(self) -> None:
        self.on_person_appeared: Callable[[], None] | None = None
        self.on_person_left: Callable[[], None] | None = None

    @abstractmethod
    def start(self) -> None:
        """啟動偵測。"""

    @abstractmethod
    def stop(self) -> None:
        """停止偵測。"""

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """偵測器是否正在運行。"""

    @property
    @abstractmethod
    def person_visible(self) -> bool:
        """是否至少有一人可見。"""

    @property
    @abstractmethod
    def person_count(self) -> int:
        """目前偵測到的人數。"""

    @property
    @abstractmethod
    def person_positions(self) -> list[tuple[float, float]]:
        """所有偵測到的人物正規化座標（0~1）。"""

    @abstractmethod
    def get_person_absence_duration(self) -> float:
        """距最後看到人的秒數。若目前有人，回傳 0.0。"""

    @abstractmethod
    def update(self, dt: float) -> None:
        """每幀更新（供模擬迴圈呼叫）。

        Args:
            dt: 時間差（秒）。
        """


class MockPersonDetector(PersonDetectorInterface):
    """手動注入式模擬人物偵測器。

    不需要攝影機，透過 inject_person / remove_person 手動控制，
    支援 ScenarioEngine 的 person_appears / person_leaves 事件。
    """

    def __init__(self) -> None:
        super().__init__()
        self._persons: dict[str, tuple[float, float]] = {}
        self._running: bool = False
        self._last_seen_time: float = 0.0
        self._accumulated_absence: float = 0.0

        logger.info("MockPersonDetector 已初始化")

    def start(self) -> None:
        """啟動偵測器。"""
        self._running = True
        logger.info("MockPersonDetector 已啟動")

    def stop(self) -> None:
        """停止偵測器。"""
        self._running = False
        logger.info("MockPersonDetector 已停止")

    @property
    def is_running(self) -> bool:
        """偵測器是否正在運行。"""
        return self._running

    @property
    def person_visible(self) -> bool:
        """是否至少有一人可見。"""
        return len(self._persons) > 0

    @property
    def person_count(self) -> int:
        """目前偵測到的人數。"""
        return len(self._persons)

    @property
    def person_positions(self) -> list[tuple[float, float]]:
        """所有偵測到的人物正規化座標。"""
        return list(self._persons.values())

    def get_person_absence_duration(self) -> float:
        """距最後看到人的秒數。若目前有人，回傳 0.0。"""
        if self.person_visible:
            return 0.0
        return self._accumulated_absence

    def update(self, dt: float) -> None:
        """每幀更新。無人時累計缺席時間。

        Args:
            dt: 時間差（秒）。
        """
        if not self.person_visible:
            self._accumulated_absence += dt

    def inject_person(
        self, name: str, position: tuple[float, float] = (0.5, 0.5)
    ) -> None:
        """加入可見人物。

        Args:
            name: 人物名稱。
            position: 正規化座標 (x, y)，範圍 0~1。
        """
        was_empty = len(self._persons) == 0
        self._persons[name] = position
        self._accumulated_absence = 0.0
        logger.debug("注入人物：%s 位置=(%s, %s)", name, position[0], position[1])

        if was_empty and self.on_person_appeared is not None:
            self.on_person_appeared()

    def remove_person(self, name: str) -> None:
        """移除人物。

        Args:
            name: 人物名稱。
        """
        if name not in self._persons:
            logger.warning("嘗試移除不存在的人物：%s", name)
            return

        del self._persons[name]
        logger.debug("移除人物：%s", name)

        if len(self._persons) == 0 and self.on_person_left is not None:
            self.on_person_left()

    def get_persons(self) -> dict[str, tuple[float, float]]:
        """取得所有可見人物。

        Returns:
            人物名稱到正規化座標的字典。
        """
        return dict(self._persons)


class YOLOPersonDetector(PersonDetectorInterface):
    """YOLO 背景執行緒人物偵測器。

    使用 ultralytics YOLO 模型在背景執行緒中週期性偵測人物，
    需搭配 MediaInterface 提供影像。

    若 ultralytics 未安裝，建構時不報錯，但 start() 時會
    raise ImportError。
    """

    # YOLO person class ID
    PERSON_CLASS: int = 0

    def __init__(
        self,
        media: object,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.5,
        detect_interval: float = 0.5,
    ) -> None:
        """初始化 YOLO 人物偵測器。

        Args:
            media: MediaInterface 實例，需有 get_frame() 方法。
            model_path: YOLO 模型檔路徑，預設 yolov8n.pt。
            confidence: 偵測信心度閾值，預設 0.5。
            detect_interval: 偵測間隔（秒），預設 0.5。
        """
        super().__init__()
        self._media = media
        self._model_path = model_path
        self._confidence = confidence
        self._detect_interval = detect_interval

        self._running: bool = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # 偵測結果（由背景執行緒寫入，主執行緒讀取）
        self._lock = threading.Lock()
        self._person_count: int = 0
        self._person_positions: list[tuple[float, float]] = []
        self._last_seen_time: float = 0.0

        logger.info(
            "YOLOPersonDetector 已初始化：model=%s, confidence=%.2f, interval=%.1fs",
            model_path,
            confidence,
            detect_interval,
        )

    def start(self) -> None:
        """啟動背景偵測執行緒。

        Raises:
            ImportError: 若 ultralytics 未安裝。
        """
        # 先檢查 ultralytics 是否可用
        try:
            import ultralytics  # noqa: F401
        except ImportError:
            raise ImportError(
                "ultralytics 未安裝。請執行 pip install ultralytics 安裝。"
            )

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._running = True
        logger.info("YOLOPersonDetector 背景偵測已啟動")

    def stop(self) -> None:
        """停止背景偵測執行緒。"""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        self._running = False
        logger.info("YOLOPersonDetector 背景偵測已停止")

    @property
    def is_running(self) -> bool:
        """偵測器是否正在運行。"""
        return self._running

    @property
    def person_visible(self) -> bool:
        """是否至少有一人可見。"""
        with self._lock:
            return self._person_count > 0

    @property
    def person_count(self) -> int:
        """目前偵測到的人數。"""
        with self._lock:
            return self._person_count

    @property
    def person_positions(self) -> list[tuple[float, float]]:
        """所有偵測到的人物正規化座標。"""
        with self._lock:
            return list(self._person_positions)

    def get_person_absence_duration(self) -> float:
        """距最後看到人的秒數。若目前有人，回傳 0.0。"""
        with self._lock:
            if self._person_count > 0:
                return 0.0
            if self._last_seen_time == 0.0:
                return float("inf")
            return time.time() - self._last_seen_time

    def update(self, dt: float) -> None:
        """每幀更新（YOLO 偵測由背景執行緒處理，此處為空操作）。

        Args:
            dt: 時間差（秒）。
        """

    def _run(self) -> None:
        """背景偵測執行緒主迴圈。"""
        from ultralytics import YOLO

        logger.info("載入 YOLO 模型：%s", self._model_path)
        model = YOLO(self._model_path)
        logger.info("YOLO 模型載入完成")

        while not self._stop_event.is_set():
            try:
                self._detect(model)
            except Exception:
                logger.exception("YOLO 偵測發生錯誤")
            self._stop_event.wait(timeout=self._detect_interval)

    def _detect(self, model: object) -> None:
        """執行一次 YOLO 偵測。"""
        frame = self._media.get_frame()
        if frame is None:
            return

        results = model(frame, verbose=False, conf=self._confidence)

        positions: list[tuple[float, float]] = []
        if results and results[0].boxes is not None:
            img_h, img_w = frame.shape[:2]
            for box in results[0].boxes:
                if int(box.cls[0]) == self.PERSON_CLASS:
                    # 取 bounding box 中心點，正規化到 0~1
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx = (x1 + x2) / 2.0 / img_w
                    cy = (y1 + y2) / 2.0 / img_h
                    positions.append((cx, cy))

        count = len(positions)
        now = time.time()

        with self._lock:
            prev_count = self._person_count
            self._person_count = count
            self._person_positions = positions
            if count > 0:
                self._last_seen_time = now

        # 回呼在鎖外觸發，避免死鎖
        if prev_count == 0 and count > 0:
            if self.on_person_appeared is not None:
                self.on_person_appeared()
        elif prev_count > 0 and count == 0:
            if self.on_person_left is not None:
                self.on_person_left()


def create_person_detector(mode: str = "mock", **kwargs: object) -> PersonDetectorInterface:
    """建立人物偵測器的工廠函式。

    Args:
        mode: 偵測器模式，"mock" 或 "yolo"。
        **kwargs: 傳給偵測器建構子的參數。

    Returns:
        PersonDetectorInterface 實例。

    Raises:
        ValueError: 若 mode 不是 "mock" 或 "yolo"。
    """
    if mode == "mock":
        return MockPersonDetector()
    elif mode == "yolo":
        return YOLOPersonDetector(**kwargs)
    else:
        raise ValueError(f"不支援的偵測器模式：{mode!r}（請使用 'mock' 或 'yolo'）")
