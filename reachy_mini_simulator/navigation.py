"""導航模組 - A* 路徑規劃、巡邏排程與避障。

提供在 OfficeMap 上的路徑搜尋、巡邏路線排程、
動態避障，以及機器人移動控制整合。
"""

from __future__ import annotations

import heapq
import math
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .office_map import OfficeMap

if TYPE_CHECKING:
    from .obstacle_detector import ObstacleDetectorInterface

logger = logging.getLogger(__name__)


def a_star(
    office_map: OfficeMap,
    start: tuple[int, int],
    goal: tuple[int, int],
) -> list[tuple[int, int]] | None:
    """A* 路徑搜尋。

    在 OfficeMap 上搜尋從 start 到 goal 的最短路徑，
    支援 8 方向移動，斜角移動成本為 √2。

    Args:
        office_map: 辦公室地圖。
        start: 起點座標 (x, y)。
        goal: 終點座標 (x, y)。

    Returns:
        從 start 到 goal 的座標列表（含起點和終點）；
        若無法到達則回傳 None。
    """
    if not office_map.is_walkable(*start) or not office_map.is_walkable(*goal):
        return None

    open_set: list[tuple[float, tuple[int, int]]] = []
    heapq.heappush(open_set, (0.0, start))

    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0.0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            # 回溯路徑
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for neighbor in office_map.get_neighbors(*current):
            dx = neighbor[0] - current[0]
            dy = neighbor[1] - current[1]
            # 斜角移動成本為 √2，正交為 1
            move_cost = math.sqrt(2) if (dx != 0 and dy != 0) else 1.0
            tentative_g = g_score[current] + move_cost

            if tentative_g < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                # 啟發式：歐幾里得距離
                h = math.sqrt(
                    (neighbor[0] - goal[0]) ** 2
                    + (neighbor[1] - goal[1]) ** 2
                )
                f = tentative_g + h
                heapq.heappush(open_set, (f, neighbor))

    return None


@dataclass
class PatrolSchedule:
    """巡邏排程項目。

    Attributes:
        time_minutes: 一天中的第幾分鐘觸發。
        location_name: 目標位置名稱（對應 OfficeMap 的 named_locations）。
        action: 到達後的行為描述。
    """
    time_minutes: float
    location_name: str
    action: str = "巡邏"


class Navigator:
    """導航器 - 管理路徑規劃與巡邏排程。

    整合 A* 路徑搜尋和巡邏路線排程，
    驅動 MockReachyMini 在地圖上移動。

    用法::

        nav = Navigator(office_map)
        nav.navigate_to("會議室A")
        while nav.is_navigating:
            nav.update(dt, robot)
    """

    def __init__(
        self,
        office_map: OfficeMap,
        obstacle_detector: ObstacleDetectorInterface | None = None,
    ) -> None:
        self.office_map = office_map
        self._path: list[tuple[int, int]] = []
        self._path_index: int = 0
        self._current_target: str | None = None
        self._on_arrival: callable | None = None
        self._obstacle_detector = obstacle_detector
        self._replan_cooldown: float = 0.0

        # 巡邏排程
        self._patrol_schedule: list[PatrolSchedule] = []
        self._patrol_index: int = 0

    @property
    def is_navigating(self) -> bool:
        """是否正在導航中。"""
        return self._path_index < len(self._path) or self._current_target is not None

    @property
    def current_target(self) -> str | None:
        """目前的導航目標名稱。"""
        return self._current_target

    @property
    def current_path(self) -> list[tuple[int, int]]:
        """目前的完整路徑。"""
        return list(self._path)

    @property
    def remaining_path(self) -> list[tuple[int, int]]:
        """剩餘路徑。"""
        return self._path[self._path_index:]

    def navigate_to(
        self,
        location_name: str,
        from_pos: tuple[float, float] | None = None,
        on_arrival: callable | None = None,
    ) -> bool:
        """導航到指定的具名位置。

        Args:
            location_name: 目標位置名稱。
            from_pos: 起點座標 (x, y)，若為 None 則使用 (0, 0)。
            on_arrival: 到達目標時的回呼函式。

        Returns:
            True 表示路徑規劃成功，False 表示無法到達。
        """
        try:
            loc = self.office_map.get_location(location_name)
        except KeyError:
            logger.warning("找不到位置: %s", location_name)
            return False

        start = (int(round(from_pos[0])), int(round(from_pos[1]))) if from_pos else (0, 0)
        goal = loc.position

        path = a_star(self.office_map, start, goal)
        if path is None:
            logger.warning("無法規劃路徑: %s → %s", start, location_name)
            return False

        self._path = path
        self._path_index = 0
        self._current_target = location_name
        self._on_arrival = on_arrival

        logger.info(
            "路徑規劃完成: → %s（%d 步）",
            location_name,
            len(path),
        )
        return True

    def update(self, dt: float, robot) -> None:
        """更新導航狀態，驅動機器人移動。

        每次呼叫時檢查機器人是否已到達當前路徑節點，
        若到達則前進到下一個節點。若有障礙偵測器且偵測到
        前方障礙，會嘗試動態重新規劃路徑。

        Args:
            dt: 時間增量（秒）。
            robot: MockReachyMini 實例。
        """
        if not self.is_navigating:
            return

        # 更新重新規劃冷卻時間
        if self._replan_cooldown > 0:
            self._replan_cooldown -= dt

        # 障礙物偵測與動態避障
        if (
            self._obstacle_detector is not None
            and self._replan_cooldown <= 0
            and self._path_index < len(self._path)
        ):
            if not self._obstacle_detector.is_path_clear(0.0, distance=0.8):
                self._try_replan(robot)

        # 如果機器人不在移動中，給它下一個目標點
        if not robot.is_moving:
            if self._path_index < len(self._path):
                next_point = self._path[self._path_index]
                robot.move_to(float(next_point[0]), float(next_point[1]))
                self._path_index += 1
            else:
                # 已到達終點
                self._current_target = None
                if self._on_arrival:
                    self._on_arrival()
                    self._on_arrival = None
                return

        # 更新機器人位置
        robot.update_position(dt)

    def _try_replan(self, robot) -> bool:
        """嘗試動態重新規劃路徑以避開障礙物。

        從機器人目前位置重新規劃到原目標的路徑。
        設定冷卻時間以避免頻繁重新規劃。

        Args:
            robot: 機器人實例。

        Returns:
            True 表示重新規劃成功，False 表示失敗。
        """
        if self._current_target is None:
            return False

        try:
            loc = self.office_map.get_location(self._current_target)
        except KeyError:
            return False

        start = (int(round(robot.position[0])), int(round(robot.position[1])))
        goal = loc.position

        new_path = a_star(self.office_map, start, goal)
        if new_path is None:
            logger.warning("避障重新規劃失敗：無法從 %s 到 %s", start, self._current_target)
            return False

        self._path = new_path
        self._path_index = 0
        self._replan_cooldown = 2.0  # 冷卻 2 秒

        logger.info(
            "避障重新規劃：%s（%d 步）",
            self._current_target,
            len(new_path),
        )
        return True

    def set_patrol_schedule(self, schedule: list[PatrolSchedule]) -> None:
        """設定巡邏排程。

        Args:
            schedule: 排程列表，按時間排序。
        """
        self._patrol_schedule = sorted(schedule, key=lambda s: s.time_minutes)
        self._patrol_index = 0

    def check_patrol(self, current_minutes: float, robot) -> PatrolSchedule | None:
        """檢查是否有到期的巡邏任務。

        Args:
            current_minutes: 目前的時間（一天中的第幾分鐘）。
            robot: MockReachyMini 實例。

        Returns:
            觸發的巡邏排程，若無則回傳 None。
        """
        if self._patrol_index >= len(self._patrol_schedule):
            return None

        schedule = self._patrol_schedule[self._patrol_index]
        if current_minutes >= schedule.time_minutes:
            self._patrol_index += 1
            self.navigate_to(
                schedule.location_name,
                from_pos=robot.position,
            )
            logger.info(
                "巡邏觸發: %s → %s",
                schedule.action,
                schedule.location_name,
            )
            return schedule

        return None


def create_default_patrol() -> list[PatrolSchedule]:
    """建立預設巡邏排程（一日）。

    Returns:
        預設排程列表。
    """
    return [
        PatrolSchedule(8 * 60 + 50, "大門", "早晨迎接"),
        PatrolSchedule(9 * 60 - 5, "會議室A", "提醒站會"),
        PatrolSchedule(9 * 60 + 30, "走廊中心", "走廊巡邏"),
        PatrolSchedule(10 * 60 - 5, "會議室C", "提醒週會"),
        PatrolSchedule(12 * 60, "茶水間", "午間巡邏"),
        PatrolSchedule(14 * 60 - 5, "會議室B", "提醒 1-on-1"),
        PatrolSchedule(15 * 60, "走廊中心", "下午巡邏"),
        PatrolSchedule(16 * 60 - 5, "會議室A", "提醒 Review"),
        PatrolSchedule(17 * 60 + 30, "充電站", "返回充電"),
    ]
