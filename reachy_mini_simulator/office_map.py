"""Office Map - 2D grid 辦公室平面圖系統。

以 2D grid 表示辦公室配置，每格代表 0.5m x 0.5m。
支援地圖載入/儲存、可通行性檢查、鄰居查詢、ASCII 顯示等功能。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from pathlib import Path
from typing import Optional

import numpy as np


class CellType(IntEnum):
    """地圖格子類型。"""
    EMPTY = 0    # 可通行空地
    WALL = 1     # 牆壁（不可通行）
    DOOR = 2     # 門（可通行）
    DESK = 3     # 桌子（不可通行）
    CHAIR = 4    # 椅子（不可通行）
    CHARGER = 5  # 充電站（特殊位置，可通行）


# 可通行的格子類型
_WALKABLE = frozenset({CellType.EMPTY, CellType.DOOR, CellType.CHARGER})

# ASCII 顯示用字元對照
_CELL_CHAR: dict[int, str] = {
    CellType.EMPTY: ".",
    CellType.WALL: "#",
    CellType.DOOR: "D",
    CellType.DESK: "T",
    CellType.CHAIR: "C",
    CellType.CHARGER: "E",
}

# 八方向偏移量（上下左右 + 四個斜角）
_DIRECTIONS_8 = [
    (-1, 0), (1, 0), (0, -1), (0, 1),   # 上下左右
    (-1, -1), (-1, 1), (1, -1), (1, 1),  # 斜角
]


@dataclass
class NamedLocation:
    """具名位置，例如會議室、大門、茶水間等。

    Attributes:
        name: 位置名稱，例如 "會議室A"、"大門"、"茶水間"。
        position: grid 座標 (x, y)。
        cell_type: 位置類別，如 "room"、"entrance"、"area"、"charger"。
    """
    name: str
    position: tuple[int, int]
    cell_type: str  # "room", "entrance", "area", "charger"

    def to_dict(self) -> dict:
        """序列化為字典。"""
        return {
            "name": self.name,
            "position": list(self.position),
            "cell_type": self.cell_type,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NamedLocation:
        """從字典反序列化。"""
        return cls(
            name=data["name"],
            position=tuple(data["position"]),
            cell_type=data["cell_type"],
        )


class OfficeMap:
    """2D Grid 辦公室地圖。

    以 numpy 2D array 儲存每格的 CellType，並維護具名位置字典。
    grid 的索引方式為 grid[y, x]，其中 y 為列（由上到下），x 為欄（由左到右）。
    每格代表 0.5m x 0.5m 的實際空間。

    Attributes:
        width: 地圖寬度（格數）。
        height: 地圖高度（格數）。
        grid: 2D numpy array，dtype=int，每格儲存 CellType 值。
        named_locations: 具名位置字典，key 為位置名稱。
    """

    def __init__(self, width: int, height: int) -> None:
        """初始化空白地圖。

        Args:
            width: 地圖寬度（格數）。
            height: 地圖高度（格數）。
        """
        self.width = width
        self.height = height
        self.grid: np.ndarray = np.full((height, width), CellType.EMPTY, dtype=int)
        self.named_locations: dict[str, NamedLocation] = {}

    # ------------------------------------------------------------------
    # 查詢方法
    # ------------------------------------------------------------------

    def _in_bounds(self, x: int, y: int) -> bool:
        """檢查座標是否在地圖範圍內。"""
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        """檢查某格是否可通行。

        Args:
            x: 欄索引。
            y: 列索引。

        Returns:
            True 表示該格可通行（EMPTY / DOOR / CHARGER）。
        """
        if not self._in_bounds(x, y):
            return False
        return CellType(self.grid[y, x]) in _WALKABLE

    def get_location(self, name: str) -> NamedLocation:
        """取得具名位置。

        Args:
            name: 位置名稱。

        Returns:
            對應的 NamedLocation。

        Raises:
            KeyError: 找不到該名稱的位置。
        """
        if name not in self.named_locations:
            raise KeyError(f"找不到具名位置: {name!r}")
        return self.named_locations[name]

    def get_neighbors(self, x: int, y: int) -> list[tuple[int, int]]:
        """取得相鄰可通行格子（8 方向）。

        斜角移動時會額外檢查：確保兩個正交鄰居都可通行，
        避免穿越牆角。

        Args:
            x: 欄索引。
            y: 列索引。

        Returns:
            可通行鄰居座標列表。
        """
        neighbors: list[tuple[int, int]] = []
        for dx, dy in _DIRECTIONS_8:
            nx, ny = x + dx, y + dy
            if not self.is_walkable(nx, ny):
                continue
            # 斜角移動：確保不穿牆角
            if dx != 0 and dy != 0:
                if not self.is_walkable(x + dx, y) or not self.is_walkable(x, y + dy):
                    continue
            neighbors.append((nx, ny))
        return neighbors

    # ------------------------------------------------------------------
    # 地圖繪製輔助
    # ------------------------------------------------------------------

    def set_cell(self, x: int, y: int, cell_type: CellType) -> None:
        """設定單格類型。"""
        self.grid[y, x] = cell_type

    def fill_rect(self, x: int, y: int, w: int, h: int, cell_type: CellType) -> None:
        """以指定類型填充矩形區域。

        Args:
            x: 左上角欄索引。
            y: 左上角列索引。
            w: 寬度（格數）。
            h: 高度（格數）。
            cell_type: 要填充的格子類型。
        """
        self.grid[y:y + h, x:x + w] = cell_type

    def draw_room(self, x: int, y: int, w: int, h: int,
                  doors: Optional[list[tuple[int, int]]] = None) -> None:
        """繪製一個有牆壁的房間，可選擇性地加門。

        先畫四面牆，再把內部設為 EMPTY，最後在指定位置加門。

        Args:
            x: 房間左上角欄索引。
            y: 房間左上角列索引。
            w: 房間寬度（含牆壁）。
            h: 房間高度（含牆壁）。
            doors: 門的座標列表 [(dx, dy), ...]，相對於房間左上角。
        """
        # 四面牆
        self.fill_rect(x, y, w, 1, CellType.WALL)           # 上牆
        self.fill_rect(x, y + h - 1, w, 1, CellType.WALL)   # 下牆
        self.fill_rect(x, y, 1, h, CellType.WALL)            # 左牆
        self.fill_rect(x + w - 1, y, 1, h, CellType.WALL)    # 右牆
        # 內部空地
        if w > 2 and h > 2:
            self.fill_rect(x + 1, y + 1, w - 2, h - 2, CellType.EMPTY)
        # 門
        if doors:
            for dx, dy in doors:
                self.set_cell(x + dx, y + dy, CellType.DOOR)

    def add_named_location(self, name: str, x: int, y: int, cell_type: str) -> None:
        """註冊具名位置。

        Args:
            name: 位置名稱。
            x: 欄索引。
            y: 列索引。
            cell_type: 位置類別字串。
        """
        self.named_locations[name] = NamedLocation(
            name=name, position=(x, y), cell_type=cell_type,
        )

    # ------------------------------------------------------------------
    # 序列化
    # ------------------------------------------------------------------

    def save_to_json(self, path: str) -> None:
        """將地圖存成 JSON 檔案。

        Args:
            path: 檔案路徑。
        """
        data = {
            "width": self.width,
            "height": self.height,
            "grid": self.grid.tolist(),
            "named_locations": {
                k: v.to_dict() for k, v in self.named_locations.items()
            },
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load_from_json(cls, path: str) -> OfficeMap:
        """從 JSON 檔案載入地圖。

        Args:
            path: 檔案路徑。

        Returns:
            載入的 OfficeMap 實例。
        """
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        omap = cls(data["width"], data["height"])
        omap.grid = np.array(data["grid"], dtype=int)
        for k, v in data.get("named_locations", {}).items():
            omap.named_locations[k] = NamedLocation.from_dict(v)
        return omap

    # ------------------------------------------------------------------
    # ASCII 顯示
    # ------------------------------------------------------------------

    def to_ascii(self) -> str:
        """輸出 ASCII 版地圖（用於終端顯示）。

        使用字元對照：
          . = 空地, # = 牆壁, D = 門, T = 桌子, C = 椅子, E = 充電站

        具名位置會以標記形式標在地圖下方。

        Returns:
            ASCII 字串。
        """
        lines: list[str] = []
        # 欄索引標頭
        header = "   " + "".join(f"{i % 10}" for i in range(self.width))
        lines.append(header)
        for y in range(self.height):
            row_chars: list[str] = []
            for x in range(self.width):
                row_chars.append(_CELL_CHAR.get(self.grid[y, x], "?"))
            lines.append(f"{y:2d} " + "".join(row_chars))
        # 具名位置標記
        if self.named_locations:
            lines.append("")
            lines.append("具名位置:")
            for name, loc in sorted(self.named_locations.items()):
                lines.append(f"  {name}: ({loc.position[0]}, {loc.position[1]}) [{loc.cell_type}]")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"OfficeMap(width={self.width}, height={self.height}, locations={len(self.named_locations)})"


# ======================================================================
# 預設辦公室地圖
# ======================================================================

def create_default_office() -> OfficeMap:
    """建立預設辦公室地圖（20x12 格，10m x 6m）。

    整體配置（20 欄 x 12 列，每格 0.5m）：

    ```
       01234567890123456789
     0 ####################
     1 #...#.#..#..TTC.TTC#   T=桌 C=椅
     2 #...D.#..#..TTC.TTC#   D=門 E=充電站
     3 #...#.#DD#.D###D####   #=牆 .=空地
     4 #####..............D
     5 #####..............D
     6 #...#..............#
     7 #...D......TTC.....#
     8 #...#......TTC.#####
     9 #####..........D...#
    10 ##E#D..........D...#
    11 ####################
    ```

    區域配置：
    - 左上：會議室A (5x5)，門開在右牆
    - 左下：會議室B (5x5)，門開在右牆
    - 中上：會議室C (4x4)，門開在下牆
    - 走廊：x=5 垂直 + y=4..5 水平 + x=10 下方垂直
    - 右上：開放辦公區，6 張辦公桌（含兩個入口門）
    - 右下：茶水間 (5x4)，門在左牆
    - 右邊中間：大門入口 (x=19, y=4..5)
    - 左下角：充電站

    Returns:
        配置好的 OfficeMap。
    """
    omap = OfficeMap(20, 12)
    omap.grid[:] = CellType.EMPTY

    # === 外牆 ===
    omap.fill_rect(0, 0, 20, 1, CellType.WALL)     # 上牆
    omap.fill_rect(0, 11, 20, 1, CellType.WALL)     # 下牆
    omap.fill_rect(0, 0, 1, 12, CellType.WALL)      # 左牆
    omap.fill_rect(19, 0, 1, 12, CellType.WALL)     # 右牆

    # === 會議室 A（左上 5x5） ===
    omap.draw_room(0, 0, 5, 5, doors=[(4, 2)])      # 門開在右牆 → (4,2)
    omap.add_named_location("會議室A", 2, 2, "room")

    # === 會議室 B（左下 5x5） ===
    omap.draw_room(0, 5, 5, 5, doors=[(4, 2)])      # 門開在右牆 → (4,7)
    omap.add_named_location("會議室B", 2, 7, "room")

    # === 會議室 C（中上 4x4，位於 x=6..9, y=0..3） ===
    omap.draw_room(6, 0, 4, 4, doors=[(1, 3), (2, 3)])  # 雙門在下牆 → (7,3),(8,3)
    omap.add_named_location("會議室C", 7, 1, "room")

    # === 走廊系統（兩格寬） ===
    # 垂直走廊 x=5, y=0..11（整個左半邊右側通道）
    omap.fill_rect(5, 0, 1, 12, CellType.EMPTY)
    # 上牆與下牆仍保留
    omap.set_cell(5, 0, CellType.WALL)
    omap.set_cell(5, 11, CellType.WALL)

    # 水平走廊 y=4..5, x=5..18（東西貫穿）
    omap.fill_rect(5, 4, 14, 2, CellType.EMPTY)

    # 右側垂直走廊 x=10..11, y=0..3（連接辦公區上方到水平走廊）
    omap.fill_rect(10, 0, 1, 4, CellType.EMPTY)
    omap.set_cell(10, 0, CellType.WALL)  # 上牆保留

    # 右半下方走廊 x=10..11, y=6..11
    omap.fill_rect(10, 6, 1, 6, CellType.EMPTY)
    omap.set_cell(10, 11, CellType.WALL)  # 下牆保留

    # === 充電站（左下角，位於 x=0..4, y=10..11） ===
    # 上牆（y=10），但 x=5 留空讓門連到走廊
    omap.fill_rect(0, 10, 4, 1, CellType.WALL)      # 上牆 x=0..3
    omap.set_cell(4, 10, CellType.DOOR)               # 門在 (4,10) 通往走廊 (5,10)
    omap.set_cell(2, 10, CellType.CHARGER)             # 充電樁
    omap.add_named_location("充電站", 4, 10, "charger")

    # === 茶水間（右下 5x4，位於 x=15..19, y=8..11） ===
    omap.draw_room(15, 8, 5, 4, doors=[(0, 1), (0, 2)])  # 門在左牆 → (15,9),(15,10)
    omap.add_named_location("茶水間", 17, 9, "room")

    # === 大門入口（右牆中間） ===
    omap.set_cell(19, 4, CellType.DOOR)
    omap.set_cell(19, 5, CellType.DOOR)
    omap.add_named_location("大門", 18, 4, "entrance")

    # === 開放辦公區（右半上方）===
    # 上方圍牆 (y=0) 已是外牆
    # 左邊用走廊 x=10 自然分隔
    # 下方分隔牆 y=3，從 x=11 到 x=19
    omap.fill_rect(11, 3, 9, 1, CellType.WALL)
    omap.set_cell(11, 3, CellType.DOOR)   # 左側入口門
    omap.set_cell(15, 3, CellType.DOOR)   # 中間走道入口門

    # 桌子配置（上方辦公區 x=11..18, y=1..2）
    # 具名位置指向桌旁的可通行格子（機器人停靠點）
    # 排列：TTC . TTC（中間留走道 x=15）
    # 桌子 1
    omap.set_cell(12, 1, CellType.DESK)
    omap.set_cell(13, 1, CellType.DESK)
    omap.set_cell(14, 1, CellType.CHAIR)
    omap.add_named_location("辦公桌1", 11, 1, "area")  # 桌旁空地

    # 桌子 2
    omap.set_cell(12, 2, CellType.DESK)
    omap.set_cell(13, 2, CellType.DESK)
    omap.set_cell(14, 2, CellType.CHAIR)
    omap.add_named_location("辦公桌2", 11, 2, "area")  # 桌旁空地

    # x=15 留走道（全空）

    # 桌子 3
    omap.set_cell(16, 1, CellType.DESK)
    omap.set_cell(17, 1, CellType.DESK)
    omap.set_cell(18, 1, CellType.CHAIR)
    omap.add_named_location("辦公桌3", 15, 1, "area")  # 走道旁空地

    # 桌子 4
    omap.set_cell(16, 2, CellType.DESK)
    omap.set_cell(17, 2, CellType.DESK)
    omap.set_cell(18, 2, CellType.CHAIR)
    omap.add_named_location("辦公桌4", 15, 2, "area")  # 走道旁空地

    # === 下方辦公區桌子（x=11..14, y=7..8） ===
    omap.set_cell(11, 7, CellType.DESK)
    omap.set_cell(12, 7, CellType.DESK)
    omap.set_cell(13, 7, CellType.CHAIR)
    omap.add_named_location("辦公桌5", 14, 7, "area")  # 桌旁空地

    omap.set_cell(11, 8, CellType.DESK)
    omap.set_cell(12, 8, CellType.DESK)
    omap.set_cell(13, 8, CellType.CHAIR)
    omap.add_named_location("辦公桌6", 14, 8, "area")  # 桌旁空地

    # === 走廊位置標記 ===
    omap.add_named_location("走廊中心", 10, 4, "area")

    return omap


def get_default_map_path() -> Path:
    """取得預設地圖 JSON 檔案路徑。"""
    return Path(__file__).parent / "maps" / "default_office.json"


def load_or_create_default() -> OfficeMap:
    """載入預設地圖，若 JSON 不存在則建立並儲存。

    Returns:
        預設辦公室地圖。
    """
    map_path = get_default_map_path()
    if map_path.exists():
        return OfficeMap.load_from_json(str(map_path))
    omap = create_default_office()
    omap.save_to_json(str(map_path))
    return omap
