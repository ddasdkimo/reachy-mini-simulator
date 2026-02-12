"""行事曆模擬 - 提供模擬的會議排程查詢功能。

在模擬環境中替代真實行事曆 API，提供預設的一日會議排程，
支援查詢即將開始與進行中的會議。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Meeting:
    """會議資料。

    Attributes:
        title: 會議標題。
        start_minutes: 開始時間（一天中的第幾分鐘，例如 540 = 09:00）。
        duration_minutes: 會議時長（分鐘）。
        room: 會議室名稱。
        participants: 參與者名單。
    """

    title: str
    start_minutes: float
    duration_minutes: float = 30.0
    room: str = ""
    participants: list[str] = field(default_factory=list)

    @property
    def end_minutes(self) -> float:
        """會議結束時間（一天中的第幾分鐘）。"""
        return self.start_minutes + self.duration_minutes

    def start_time_str(self) -> str:
        """回傳格式化的開始時間字串，例如 '09:00'。"""
        hours = int(self.start_minutes // 60)
        mins = int(self.start_minutes % 60)
        return f"{hours:02d}:{mins:02d}"

    def end_time_str(self) -> str:
        """回傳格式化的結束時間字串。"""
        hours = int(self.end_minutes // 60)
        mins = int(self.end_minutes % 60)
        return f"{hours:02d}:{mins:02d}"

    def __str__(self) -> str:
        return (
            f"{self.start_time_str()}-{self.end_time_str()} "
            f"{self.title} @ {self.room}"
        )


def _default_schedule() -> list[Meeting]:
    """建立預設的一日會議排程。

    包含四場典型的辦公室會議：
    - 09:00 站會（15 分鐘）
    - 10:00 週會（60 分鐘）
    - 14:00 1-on-1（30 分鐘）
    - 16:00 Code Review（45 分鐘）
    """
    return [
        Meeting(
            title="每日站會",
            start_minutes=9 * 60,  # 09:00
            duration_minutes=15,
            room="會議室A",
            participants=["David", "Amy", "Brian"],
        ),
        Meeting(
            title="週會",
            start_minutes=10 * 60,  # 10:00
            duration_minutes=60,
            room="大會議室",
            participants=["David", "Amy", "Brian", "Carol", "主管"],
        ),
        Meeting(
            title="1-on-1",
            start_minutes=14 * 60,  # 14:00
            duration_minutes=30,
            room="小會議室",
            participants=["David", "主管"],
        ),
        Meeting(
            title="Code Review",
            start_minutes=16 * 60,  # 16:00
            duration_minutes=45,
            room="會議室B",
            participants=["David", "Amy"],
        ),
    ]


class CalendarMock:
    """模擬行事曆，提供會議查詢功能。

    使用模擬時間（以「一天中的第幾分鐘」為單位）來查詢即將開始
    或正在進行中的會議。

    用法::

        cal = CalendarMock()  # 使用預設排程
        cal.set_current_time(minutes=538)  # 設定為 08:58
        upcoming = cal.get_upcoming(within_minutes=10)
        # 回傳 09:00 站會
    """

    def __init__(self, meetings: list[Meeting] | None = None) -> None:
        """初始化行事曆。

        Args:
            meetings: 會議列表。若為 None 則使用預設的一日排程。
        """
        self._meetings = meetings if meetings is not None else _default_schedule()
        self._meetings.sort(key=lambda m: m.start_minutes)
        self._current_minutes: float = 0.0

    @property
    def meetings(self) -> list[Meeting]:
        """所有已排定的會議。"""
        return list(self._meetings)

    @property
    def current_minutes(self) -> float:
        """目前的時間（一天中的第幾分鐘）。"""
        return self._current_minutes

    def set_current_time(self, minutes: float) -> None:
        """設定目前的模擬時間。

        Args:
            minutes: 一天中的第幾分鐘（例如 540 = 09:00）。
        """
        self._current_minutes = minutes

    def advance_time(self, minutes: float) -> None:
        """推進模擬時間。

        Args:
            minutes: 要推進的分鐘數。
        """
        self._current_minutes += minutes

    def get_upcoming(self, within_minutes: float = 15.0) -> list[Meeting]:
        """查詢即將開始的會議。

        回傳在目前時間之後、``within_minutes`` 分鐘以內開始的會議。

        Args:
            within_minutes: 查詢時間範圍（分鐘），預設 15 分鐘。

        Returns:
            即將開始的會議列表，按開始時間排序。
        """
        now = self._current_minutes
        deadline = now + within_minutes
        return [
            m
            for m in self._meetings
            if now <= m.start_minutes <= deadline
        ]

    def get_current(self) -> Meeting | None:
        """查詢目前正在進行中的會議。

        Returns:
            正在進行中的會議；若無則回傳 None。
                若有多場重疊，回傳最近開始的那場。
        """
        now = self._current_minutes
        active = [
            m
            for m in self._meetings
            if m.start_minutes <= now < m.end_minutes
        ]
        if not active:
            return None
        # 回傳最近開始的
        return max(active, key=lambda m: m.start_minutes)

    def get_next(self) -> Meeting | None:
        """查詢下一場尚未開始的會議。

        Returns:
            下一場會議；若今日已無更多會議則回傳 None。
        """
        now = self._current_minutes
        for m in self._meetings:
            if m.start_minutes > now:
                return m
        return None
