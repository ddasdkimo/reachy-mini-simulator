"""測試導航模組 - A* 路徑搜尋與 Navigator。

涵蓋 A* 正確性、無路可走、Navigator 狀態轉換等功能。
"""

import math

import pytest

from reachy_mini_simulator.office_map import CellType, OfficeMap, create_default_office
from reachy_mini_simulator.navigation import a_star, Navigator, PatrolSchedule
from reachy_mini_simulator.mock_robot import MockReachyMini


# ── A* 路徑搜尋 ──────────────────────────────────────────────────

class TestAStar:
    """測試 A* 路徑搜尋演算法。"""

    def _make_open_map(self, w: int = 10, h: int = 10) -> OfficeMap:
        """建立全開放地圖。"""
        return OfficeMap(w, h)

    def test_same_start_and_goal(self):
        """起點與終點相同，路徑只含一個點。"""
        omap = self._make_open_map()
        path = a_star(omap, (3, 3), (3, 3))
        assert path is not None
        assert len(path) == 1
        assert path[0] == (3, 3)

    def test_straight_line(self):
        """直線路徑的起點和終點正確。"""
        omap = self._make_open_map()
        path = a_star(omap, (0, 0), (5, 0))
        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (5, 0)

    def test_path_contains_start_and_goal(self):
        """路徑包含起點和終點。"""
        omap = self._make_open_map()
        path = a_star(omap, (1, 1), (8, 8))
        assert path is not None
        assert path[0] == (1, 1)
        assert path[-1] == (8, 8)

    def test_path_is_connected(self):
        """路徑上每兩個相鄰節點之間的距離不超過 sqrt(2)（8 方向移動）。"""
        omap = self._make_open_map()
        path = a_star(omap, (0, 0), (9, 9))
        assert path is not None
        for i in range(len(path) - 1):
            dx = abs(path[i + 1][0] - path[i][0])
            dy = abs(path[i + 1][1] - path[i][1])
            assert dx <= 1 and dy <= 1, f"路徑不連續: {path[i]} -> {path[i+1]}"

    def test_path_around_wall(self):
        """路徑能繞過牆壁。"""
        omap = self._make_open_map()
        # 在 x=5 建一道從 y=0 到 y=8 的牆，留 y=9 開口
        for y in range(9):
            omap.set_cell(5, y, CellType.WALL)
        path = a_star(omap, (0, 0), (9, 0))
        assert path is not None
        assert path[-1] == (9, 0)
        # 路徑不應穿過牆壁
        for px, py in path:
            assert omap.is_walkable(px, py)

    def test_no_path_completely_blocked(self):
        """完全被牆壁封住時回傳 None。"""
        omap = self._make_open_map(5, 5)
        # 用牆壁完全包圍 (0,0)
        omap.set_cell(1, 0, CellType.WALL)
        omap.set_cell(0, 1, CellType.WALL)
        omap.set_cell(1, 1, CellType.WALL)
        path = a_star(omap, (0, 0), (4, 4))
        assert path is None

    def test_unwalkable_start(self):
        """起點不可通行時回傳 None。"""
        omap = self._make_open_map()
        omap.set_cell(0, 0, CellType.WALL)
        path = a_star(omap, (0, 0), (5, 5))
        assert path is None

    def test_unwalkable_goal(self):
        """終點不可通行時回傳 None。"""
        omap = self._make_open_map()
        omap.set_cell(5, 5, CellType.WALL)
        path = a_star(omap, (0, 0), (5, 5))
        assert path is None

    def test_diagonal_path_length(self):
        """開放地圖上對角線路徑長度接近最佳值。"""
        omap = self._make_open_map()
        path = a_star(omap, (0, 0), (9, 9))
        assert path is not None
        # 對角線路徑最佳為 10 步（含起點）
        assert len(path) == 10

    def test_through_door(self):
        """路徑能通過門。"""
        omap = OfficeMap(7, 3)
        # 建一面牆，留一個門
        for x in range(7):
            omap.set_cell(x, 1, CellType.WALL)
        omap.set_cell(3, 1, CellType.DOOR)
        path = a_star(omap, (3, 0), (3, 2))
        assert path is not None
        assert (3, 1) in path


# ── 預設地圖上的 A* ──────────────────────────────────────────────

class TestAStarDefaultMap:
    """在預設辦公室地圖上測試 A* 路徑。"""

    def test_charger_to_gate(self):
        """充電站到大門之間存在路徑。"""
        omap = create_default_office()
        charger = omap.get_location("充電站").position
        gate = omap.get_location("大門").position
        path = a_star(omap, charger, gate)
        assert path is not None
        assert path[0] == charger
        assert path[-1] == gate

    def test_all_named_locations_reachable_from_charger(self):
        """所有具名位置都可從充電站到達。"""
        omap = create_default_office()
        charger = omap.get_location("充電站").position
        for name, loc in omap.named_locations.items():
            path = a_star(omap, charger, loc.position)
            assert path is not None, f"充電站到 {name} 無路徑"


# ── Navigator 狀態測試 ────────────────────────────────────────────

class TestNavigator:
    """測試 Navigator 導航器。"""

    def _setup(self):
        """建立測試用的 Navigator 和 Robot。"""
        omap = create_default_office()
        nav = Navigator(omap)
        charger = omap.get_location("充電站")
        robot = MockReachyMini(
            position=(float(charger.position[0]), float(charger.position[1])),
            speed=3.0,
        )
        return omap, nav, robot

    def test_initial_state(self):
        """初始狀態不在導航中。"""
        _, nav, _ = self._setup()
        assert not nav.is_navigating
        assert nav.current_target is None
        assert nav.current_path == []

    def test_navigate_to_success(self):
        """navigate_to 成功後進入導航狀態。"""
        _, nav, robot = self._setup()
        result = nav.navigate_to("大門", from_pos=robot.position)
        assert result is True
        assert nav.is_navigating
        assert nav.current_target == "大門"
        assert len(nav.current_path) > 0

    def test_navigate_to_unknown_location(self):
        """navigate_to 到不存在的位置回傳 False。"""
        _, nav, robot = self._setup()
        result = nav.navigate_to("火星基地", from_pos=robot.position)
        assert result is False
        assert not nav.is_navigating

    def test_update_moves_robot(self):
        """update 會驅動機器人移動。"""
        _, nav, robot = self._setup()
        nav.navigate_to("走廊中心", from_pos=robot.position)
        initial_pos = robot.position

        # 多次 update 推進移動
        for _ in range(100):
            nav.update(0.5, robot)

        # 機器人位置應該改變了
        assert robot.position != initial_pos

    def test_navigation_completes(self):
        """導航最終會完成（到達目標）。"""
        _, nav, robot = self._setup()
        nav.navigate_to("走廊中心", from_pos=robot.position)

        # 跑足夠多的步驟
        for _ in range(500):
            nav.update(0.5, robot)
            if not nav.is_navigating:
                break

        assert not nav.is_navigating

    def test_remaining_path_decreases(self):
        """剩餘路徑長度會隨導航進行減少。"""
        _, nav, robot = self._setup()
        nav.navigate_to("走廊中心", from_pos=robot.position)
        initial_remaining = len(nav.remaining_path)

        for _ in range(50):
            nav.update(0.5, robot)

        assert len(nav.remaining_path) < initial_remaining

    def test_on_arrival_callback(self):
        """到達目標時觸發回呼。"""
        _, nav, robot = self._setup()
        arrived = {"called": False}

        def on_arrive():
            arrived["called"] = True

        nav.navigate_to("走廊中心", from_pos=robot.position, on_arrival=on_arrive)

        for _ in range(500):
            nav.update(0.5, robot)
            if not nav.is_navigating:
                break

        assert arrived["called"]


# ── PatrolSchedule 測試 ───────────────────────────────────────────

class TestPatrolSchedule:
    """測試巡邏排程。"""

    def test_set_and_check_patrol(self):
        """設定排程後可觸發巡邏。"""
        omap = create_default_office()
        nav = Navigator(omap)
        charger = omap.get_location("充電站")
        robot = MockReachyMini(
            position=(float(charger.position[0]), float(charger.position[1])),
            speed=3.0,
        )

        schedule = [
            PatrolSchedule(time_minutes=540, location_name="大門", action="迎接"),
        ]
        nav.set_patrol_schedule(schedule)

        # 時間到之前不觸發
        result = nav.check_patrol(539, robot)
        assert result is None

        # 時間到時觸發
        result = nav.check_patrol(540, robot)
        assert result is not None
        assert result.location_name == "大門"
        assert nav.is_navigating
