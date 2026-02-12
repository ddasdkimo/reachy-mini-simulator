"""測試 OfficeMap 地圖模組。

涵蓋地圖建立、is_walkable、get_neighbors 邊界、具名位置、序列化等功能。
"""

import json
import tempfile

import numpy as np
import pytest

from reachy_mini_simulator.office_map import (
    CellType,
    NamedLocation,
    OfficeMap,
    create_default_office,
)


# ── 基本建立 ──────────────────────────────────────────────────────

class TestOfficeMapCreation:
    """測試地圖建立與初始化。"""

    def test_empty_map_dimensions(self):
        """空白地圖尺寸正確。"""
        omap = OfficeMap(10, 8)
        assert omap.width == 10
        assert omap.height == 8
        assert omap.grid.shape == (8, 10)

    def test_empty_map_all_walkable(self):
        """空白地圖全部格子都是 EMPTY，皆可通行。"""
        omap = OfficeMap(5, 5)
        for y in range(5):
            for x in range(5):
                assert omap.is_walkable(x, y)
                assert omap.grid[y, x] == CellType.EMPTY

    def test_set_cell(self):
        """set_cell 正確設定格子類型。"""
        omap = OfficeMap(5, 5)
        omap.set_cell(2, 3, CellType.WALL)
        assert omap.grid[3, 2] == CellType.WALL
        assert not omap.is_walkable(2, 3)

    def test_fill_rect(self):
        """fill_rect 正確填充矩形區域。"""
        omap = OfficeMap(10, 10)
        omap.fill_rect(2, 3, 4, 2, CellType.WALL)
        for y in range(3, 5):
            for x in range(2, 6):
                assert omap.grid[y, x] == CellType.WALL

    def test_draw_room(self):
        """draw_room 正確繪製房間（含牆壁與門）。"""
        omap = OfficeMap(10, 10)
        omap.draw_room(1, 1, 5, 5, doors=[(2, 4)])

        # 四面牆
        assert omap.grid[1, 1] == CellType.WALL  # 左上角
        assert omap.grid[5, 5] == CellType.WALL  # 右下角

        # 門
        assert omap.grid[5, 3] == CellType.DOOR  # (1+2, 1+4) = (3, 5)

        # 內部應為 EMPTY
        assert omap.grid[3, 3] == CellType.EMPTY


# ── is_walkable 邊界測試 ──────────────────────────────────────────

class TestIsWalkable:
    """測試 is_walkable 的邊界條件。"""

    def test_walkable_empty(self):
        """EMPTY 格子可通行。"""
        omap = OfficeMap(5, 5)
        assert omap.is_walkable(0, 0)

    def test_walkable_door(self):
        """DOOR 格子可通行。"""
        omap = OfficeMap(5, 5)
        omap.set_cell(1, 1, CellType.DOOR)
        assert omap.is_walkable(1, 1)

    def test_walkable_charger(self):
        """CHARGER 格子可通行。"""
        omap = OfficeMap(5, 5)
        omap.set_cell(2, 2, CellType.CHARGER)
        assert omap.is_walkable(2, 2)

    def test_not_walkable_wall(self):
        """WALL 格子不可通行。"""
        omap = OfficeMap(5, 5)
        omap.set_cell(1, 1, CellType.WALL)
        assert not omap.is_walkable(1, 1)

    def test_not_walkable_desk(self):
        """DESK 格子不可通行。"""
        omap = OfficeMap(5, 5)
        omap.set_cell(1, 1, CellType.DESK)
        assert not omap.is_walkable(1, 1)

    def test_not_walkable_chair(self):
        """CHAIR 格子不可通行。"""
        omap = OfficeMap(5, 5)
        omap.set_cell(1, 1, CellType.CHAIR)
        assert not omap.is_walkable(1, 1)

    def test_out_of_bounds_negative(self):
        """負座標回傳不可通行。"""
        omap = OfficeMap(5, 5)
        assert not omap.is_walkable(-1, 0)
        assert not omap.is_walkable(0, -1)

    def test_out_of_bounds_overflow(self):
        """超出上限座標回傳不可通行。"""
        omap = OfficeMap(5, 5)
        assert not omap.is_walkable(5, 0)
        assert not omap.is_walkable(0, 5)
        assert not omap.is_walkable(100, 100)


# ── get_neighbors 測試 ────────────────────────────────────────────

class TestGetNeighbors:
    """測試 get_neighbors 鄰居查詢。"""

    def test_center_open_map(self):
        """開放地圖中央格子有 8 個鄰居。"""
        omap = OfficeMap(5, 5)
        neighbors = omap.get_neighbors(2, 2)
        assert len(neighbors) == 8

    def test_corner(self):
        """角落格子鄰居數量正確（最多 3 個）。"""
        omap = OfficeMap(5, 5)
        neighbors = omap.get_neighbors(0, 0)
        assert len(neighbors) == 3  # (1,0), (0,1), (1,1)

    def test_edge(self):
        """邊緣格子鄰居數量正確（最多 5 個）。"""
        omap = OfficeMap(5, 5)
        neighbors = omap.get_neighbors(2, 0)
        assert len(neighbors) == 5

    def test_wall_blocks_neighbor(self):
        """牆壁會阻擋鄰居。"""
        omap = OfficeMap(5, 5)
        omap.set_cell(3, 2, CellType.WALL)
        neighbors = omap.get_neighbors(2, 2)
        assert (3, 2) not in neighbors

    def test_diagonal_blocked_by_wall_corner(self):
        """斜角移動在牆角處被阻擋（不穿牆角）。"""
        omap = OfficeMap(5, 5)
        # 在 (3,2) 和 (2,3) 放牆壁
        omap.set_cell(3, 2, CellType.WALL)
        omap.set_cell(2, 3, CellType.WALL)
        neighbors = omap.get_neighbors(2, 2)
        # (3,3) 是斜角方向，但兩個正交鄰居 (3,2) 和 (2,3) 都是牆壁
        assert (3, 3) not in neighbors


# ── 具名位置 ──────────────────────────────────────────────────────

class TestNamedLocations:
    """測試具名位置管理。"""

    def test_add_and_get_location(self):
        """新增與取得具名位置。"""
        omap = OfficeMap(10, 10)
        omap.add_named_location("測試", 3, 4, "room")
        loc = omap.get_location("測試")
        assert loc.name == "測試"
        assert loc.position == (3, 4)
        assert loc.cell_type == "room"

    def test_get_nonexistent_location(self):
        """取得不存在的位置應拋出 KeyError。"""
        omap = OfficeMap(10, 10)
        with pytest.raises(KeyError):
            omap.get_location("不存在")


# ── 序列化 ────────────────────────────────────────────────────────

class TestSerialization:
    """測試 JSON 序列化與反序列化。"""

    def test_save_and_load(self, tmp_path):
        """儲存後載入的地圖應與原始地圖一致。"""
        omap = OfficeMap(8, 6)
        omap.set_cell(2, 3, CellType.WALL)
        omap.set_cell(4, 1, CellType.DOOR)
        omap.add_named_location("測試室", 5, 2, "room")

        path = str(tmp_path / "test_map.json")
        omap.save_to_json(path)
        loaded = OfficeMap.load_from_json(path)

        assert loaded.width == omap.width
        assert loaded.height == omap.height
        assert np.array_equal(loaded.grid, omap.grid)
        assert "測試室" in loaded.named_locations
        assert loaded.named_locations["測試室"].position == (5, 2)


# ── 預設地圖 ──────────────────────────────────────────────────────

class TestDefaultOffice:
    """測試預設辦公室地圖。"""

    def test_default_map_dimensions(self):
        """預設地圖尺寸為 20x12。"""
        omap = create_default_office()
        assert omap.width == 20
        assert omap.height == 12

    def test_default_map_has_named_locations(self):
        """預設地圖包含必要的具名位置。"""
        omap = create_default_office()
        required = ["會議室A", "會議室B", "會議室C", "充電站", "大門", "茶水間"]
        for name in required:
            assert name in omap.named_locations, f"缺少具名位置: {name}"

    def test_default_map_outer_walls(self):
        """預設地圖四周有外牆。"""
        omap = create_default_office()
        # 上牆
        for x in range(omap.width):
            assert omap.grid[0, x] == CellType.WALL
        # 下牆
        for x in range(omap.width):
            assert omap.grid[omap.height - 1, x] == CellType.WALL
        # 左牆
        for y in range(omap.height):
            assert omap.grid[y, 0] == CellType.WALL
        # 右牆（大門位置除外）
        door_ys = {4, 5}  # 大門在 y=4,5
        for y in range(omap.height):
            if y not in door_ys:
                assert omap.grid[y, omap.width - 1] == CellType.WALL

    def test_charger_is_walkable(self):
        """充電站位置可通行。"""
        omap = create_default_office()
        loc = omap.get_location("充電站")
        assert omap.is_walkable(*loc.position)

    def test_to_ascii(self):
        """ASCII 輸出不為空。"""
        omap = create_default_office()
        ascii_str = omap.to_ascii()
        assert len(ascii_str) > 0
        assert "具名位置" in ascii_str


# ── NamedLocation dataclass ───────────────────────────────────────

class TestNamedLocation:
    """測試 NamedLocation 資料類別。"""

    def test_to_dict_and_from_dict(self):
        """序列化與反序列化一致。"""
        loc = NamedLocation(name="A", position=(3, 4), cell_type="room")
        d = loc.to_dict()
        restored = NamedLocation.from_dict(d)
        assert restored.name == loc.name
        assert restored.position == loc.position
        assert restored.cell_type == loc.cell_type
