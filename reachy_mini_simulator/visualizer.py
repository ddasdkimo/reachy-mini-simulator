"""Visualizer - pygame 2D 辦公室地圖視覺化（互動版 + AI 對話）。

以圖形介面呈現辦公室地圖、機器人移動、人物出沒、導航路徑與事件日誌，
提供即時的模擬視覺回饋，並支援滑鼠點擊導航與人物控制等互動功能。
整合 AIBrain 進行智慧對話（支援 Claude API 或固定台詞 fallback），
以及 ExpressionEngine 驅動天線與頭部情緒動畫。

操作方式::

    左鍵點地圖   導航機器人到點擊位置
    右鍵點地圖   在該位置新增/移除人物
    T           開啟文字輸入框，模擬對機器人說話
    空白鍵       暫停/繼續
    ↑ / ↓       調整模擬速度
    R           重新開始
    Q / ESC     離開

執行方式::

    python -m reachy_mini_simulator.visualizer
"""

from __future__ import annotations

import math
import sys
import time
import logging

import numpy as np

try:
    import pygame
    import pygame.freetype
except ImportError:
    print("需要 pygame：pip install pygame")
    sys.exit(1)

from .ai_brain import AIBrain, BrainResponse
from .expression import ExpressionEngine
from .mock_robot import MockReachyMini
from .scenario import ScenarioEngine, SimEvent, SimPerson
from .office_map import create_default_office, OfficeMap, CellType
from .navigation import Navigator, create_default_patrol
from .calendar_mock import CalendarMock

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)

# ── 色彩定義 ──────────────────────────────────────────────────────
C_BG = (30, 30, 40)
C_EMPTY = (60, 63, 70)
C_WALL = (80, 85, 95)
C_DOOR = (140, 170, 200)
C_DESK = (120, 100, 70)
C_CHAIR = (100, 130, 90)
C_CHARGER = (255, 220, 60)
C_ROBOT = (50, 220, 120)
C_ROBOT_GLOW = (50, 220, 120, 60)
C_PATH = (80, 180, 255, 100)
C_PERSON = (255, 180, 60)
C_TEXT = (220, 225, 230)
C_TEXT_DIM = (130, 135, 145)
C_TEXT_HIGHLIGHT = (120, 230, 180)
C_PANEL_BG = (35, 38, 48)
C_PANEL_BORDER = (60, 65, 80)
C_EVENT_PERSON = (255, 200, 80)
C_EVENT_CALENDAR = (180, 130, 255)
C_EVENT_ROBOT = (80, 220, 150)
C_EVENT_LEAVE = (255, 100, 100)
C_GRID_LINE = (50, 53, 60)
C_LOCATION_LABEL = (180, 185, 200, 160)
C_HOVER = (255, 255, 255, 40)
C_CLICK_TARGET = (255, 80, 80, 120)
C_TEXT_INPUT_BG = (45, 48, 60)
C_TEXT_INPUT_BORDER = (120, 230, 180)
C_INTERACTIVE_PERSON = (100, 200, 255)

# 每格的像素大小
CELL_SIZE = 40
# 右側面板寬度
PANEL_WIDTH = 380

# 機器人對各事件的預設台詞
RESPONSES = {
    "person_appears": [
        "歡迎來到辦公室～今天也要加油！",
        "有人來了！嘿嘿，早安～",
        "歡迎歡迎！要喝杯咖啡嗎？",
    ],
    "person_leaves": [
        "掰掰～路上小心喔！",
        "再見啦，明天見！",
    ],
    "calendar_event": [
        "{title} 快開始了，在{room}，還有 {in_minutes} 分鐘！",
    ],
    "user_speaks": [
        "我聽到你說「{text}」了呢！",
    ],
    "idle": [
        "好安靜喔...巡邏一下好了～",
        "大家都在忙嗎？我來巡邏～",
        "一個人待著好無聊呀...",
    ],
}

_resp_counters: dict[str, int] = {}


def _get_response(event_type: str, **kwargs: object) -> str:
    templates = RESPONSES.get(event_type, ["..."])
    idx = _resp_counters.get(event_type, 0) % len(templates)
    _resp_counters[event_type] = idx + 1
    return templates[idx].format(**kwargs)


# ── 地圖格子顏色 ──────────────────────────────────────────────────
_CELL_COLOR: dict[int, tuple[int, int, int]] = {
    CellType.EMPTY: C_EMPTY,
    CellType.WALL: C_WALL,
    CellType.DOOR: C_DOOR,
    CellType.DESK: C_DESK,
    CellType.CHAIR: C_CHAIR,
    CellType.CHARGER: C_CHARGER,
}


# 格子類型中文名稱對照
_CELL_TYPE_NAME: dict[int, str] = {
    CellType.EMPTY: "空地",
    CellType.WALL: "牆壁",
    CellType.DOOR: "門",
    CellType.DESK: "桌子",
    CellType.CHAIR: "椅子",
    CellType.CHARGER: "充電站",
}


def _office_minutes_str(minutes: float) -> str:
    h = int(minutes // 60)
    m = int(minutes % 60)
    return f"{h:02d}:{m:02d}"


class Visualizer:
    """pygame 2D 辦公室模擬視覺化。"""

    def __init__(self) -> None:
        self.office_map = create_default_office()
        charger = self.office_map.get_location("充電站")
        self.robot = MockReachyMini(
            position=(float(charger.position[0]), float(charger.position[1])),
            speed=3.0,
        )
        self.scenario = ScenarioEngine()
        self.navigator = Navigator(self.office_map)
        self.calendar = CalendarMock()

        # 模擬時間參數
        self.office_start_minutes = 8 * 60 + 50  # 08:50
        self.sim_to_office_ratio = 6.0  # 1 模擬秒 = 6 分鐘
        self.sim_dt = 0.5
        self.speed_multiplier = 1.0

        # 事件日誌
        self.event_log: list[tuple[str, tuple[int, int, int], str]] = []
        # (time_str, color, message)

        # pygame
        map_w = self.office_map.width * CELL_SIZE
        map_h = self.office_map.height * CELL_SIZE
        self.map_pixel_w = map_w
        self.map_pixel_h = map_h
        self.win_w = map_w + PANEL_WIDTH
        self.win_h = max(map_h, 500)

        pygame.init()
        self.screen = pygame.display.set_mode((self.win_w, self.win_h))
        pygame.display.set_caption("Reachy Mini 辦公室助手模擬器")

        # 字型 - 使用穩健的字型載入
        self.font_sm = self._load_font(13)
        self.font_md = self._load_font(15)
        self.font_lg = self._load_font(20, bold=True)
        self.font_icon = self._load_font(22, bold=True)

        # 預渲染地圖表面 (must come after font init)
        self.map_surface = pygame.Surface((map_w, map_h))
        self._render_static_map()

        # 路徑表面（帶透明度）
        self.path_surface = pygame.Surface((map_w, map_h), pygame.SRCALPHA)

        # 動畫用
        self.frame_count = 0
        self.paused = False
        self.clock = pygame.time.Clock()

        # ── AI 大腦與表情引擎 ──
        self.brain = AIBrain()
        self.expression = ExpressionEngine()

        def _on_brain_response(resp: BrainResponse) -> None:
            """處理 AI 大腦回應：更新事件日誌並觸發情緒動畫。"""
            office_min = self._sim_to_office_minutes(self.scenario.current_time)
            ts = _office_minutes_str(office_min)
            emotion_tag = f"[{resp.emotion}]" if resp.emotion else ""
            self.event_log.append(
                (ts, C_EVENT_ROBOT, f"Robot: {emotion_tag} {resp.text}")
            )
            if resp.emotion:
                self.expression.trigger_emotion(resp.emotion)

        def _on_processing_start() -> None:
            self.expression.set_state("PROCESSING")

        def _on_processing_end() -> None:
            self.expression.set_state("IDLE")

        self.brain.on_response = _on_brain_response
        self.brain.on_processing_start = _on_processing_start
        self.brain.on_processing_end = _on_processing_end

        # ── 互動功能狀態 ──
        # 滑鼠懸停的格子座標（None 表示不在地圖範圍內）
        self._hover_cell: tuple[int, int] | None = None
        # 文字輸入模式
        self._text_input_active: bool = False
        self._text_input_buffer: str = ""
        # 互動新增人物的流水編號
        self._interactive_person_counter: int = 0

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> pygame.font.Font:
        """載入支援中文的字型，若找不到則使用預設字型。"""
        import platform
        from pathlib import Path

        candidates: list[str] = []
        if platform.system() == "Darwin":
            # macOS 系統字型路徑
            candidates = [
                "/System/Library/Fonts/PingFang.ttc",
                "/System/Library/Fonts/STHeiti Light.ttc",
                "/System/Library/Fonts/Hiragino Sans GB.ttc",
                "/Library/Fonts/Arial Unicode.ttf",
            ]
        elif platform.system() == "Windows":
            candidates = [
                "C:/Windows/Fonts/msjh.ttc",
                "C:/Windows/Fonts/msyh.ttc",
                "C:/Windows/Fonts/simsun.ttc",
            ]
        else:
            candidates = [
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            ]

        for font_path in candidates:
            if Path(font_path).exists():
                try:
                    f = pygame.font.Font(font_path, size)
                    f.set_bold(bold)
                    return f
                except Exception:
                    continue

        # fallback: pygame 預設字型（可能不支援中文）
        return pygame.font.Font(None, size)

    def _pixel_to_grid(self, px: int, py: int) -> tuple[int, int] | None:
        """將像素座標轉換為地圖格子座標。

        Args:
            px: 像素 x 座標。
            py: 像素 y 座標。

        Returns:
            格子座標 (gx, gy)，若超出地圖範圍則回傳 None。
        """
        gx = px // CELL_SIZE
        gy = py // CELL_SIZE
        if 0 <= gx < self.office_map.width and 0 <= gy < self.office_map.height:
            return (gx, gy)
        return None

    def _handle_left_click(self, grid_pos: tuple[int, int]) -> None:
        """處理左鍵點擊：導航機器人到點擊位置。"""
        gx, gy = grid_pos
        if not self.office_map.is_walkable(gx, gy):
            office_min = self._sim_to_office_minutes(self.scenario.current_time)
            ts = _office_minutes_str(office_min)
            cell_name = _CELL_TYPE_NAME.get(self.office_map.grid[gy, gx], "?")
            self.event_log.append(
                (ts, C_EVENT_LEAVE, f"無法導航到 ({gx},{gy})：{cell_name}不可通行")
            )
            return

        from .navigation import a_star

        start = (
            int(round(self.robot.position[0])),
            int(round(self.robot.position[1])),
        )
        path = a_star(self.office_map, start, (gx, gy))
        if path is None:
            office_min = self._sim_to_office_minutes(self.scenario.current_time)
            ts = _office_minutes_str(office_min)
            self.event_log.append(
                (ts, C_EVENT_LEAVE, f"找不到前往 ({gx},{gy}) 的路徑")
            )
            return

        # 直接設定 navigator 的路徑
        self.navigator._path = path
        self.navigator._path_index = 0
        self.navigator._current_target = f"({gx},{gy})"

        office_min = self._sim_to_office_minutes(self.scenario.current_time)
        ts = _office_minutes_str(office_min)
        self.event_log.append(
            (ts, C_EVENT_ROBOT, f"導航至 ({gx},{gy})（{len(path)} 步）")
        )

    def _handle_right_click(self, grid_pos: tuple[int, int]) -> None:
        """處理右鍵點擊：在該位置新增或移除人物。"""
        gx, gy = grid_pos
        office_min = self._sim_to_office_minutes(self.scenario.current_time)
        ts = _office_minutes_str(office_min)

        # 檢查該位置是否已有可見人物，有的話就移除
        for name, person in list(self.scenario.persons.items()):
            if not person.is_visible:
                continue
            px_round = int(round(person.position[0]))
            py_round = int(round(person.position[1]))
            if px_round == gx and py_round == gy:
                person.is_visible = False
                self.event_log.append(
                    (ts, C_EVENT_LEAVE, f"{name} 已被移除")
                )
                return

        # 否則在該位置新增人物
        if not self.office_map.is_walkable(gx, gy):
            self.event_log.append(
                (ts, C_EVENT_LEAVE, f"無法在 ({gx},{gy}) 放置人物")
            )
            return

        self._interactive_person_counter += 1
        name = f"人物{self._interactive_person_counter}"
        self.scenario.persons[name] = SimPerson(
            name=name,
            position=(float(gx), float(gy)),
            is_visible=True,
        )
        self.event_log.append(
            (ts, C_EVENT_PERSON, f"{name} 出現在 ({gx},{gy})")
        )
        self.brain.handle_event("person_appears", {"name": name, "location": f"({gx},{gy})"})

    def _handle_text_submit(self) -> None:
        """處理文字輸入提交：模擬使用者對機器人說話。"""
        text = self._text_input_buffer.strip()
        self._text_input_active = False
        self._text_input_buffer = ""
        if not text:
            return

        office_min = self._sim_to_office_minutes(self.scenario.current_time)
        ts = _office_minutes_str(office_min)
        self.event_log.append((ts, C_TEXT, f'使用者: "{text}"'))
        self.expression.set_state("LISTENING")
        self.brain.handle_event("user_speaks", {"name": "使用者", "text": text})

    def _sim_to_office_minutes(self, sim_time: float) -> float:
        return self.office_start_minutes + sim_time * self.sim_to_office_ratio

    def _render_static_map(self) -> None:
        """預渲染靜態地圖（牆壁、桌子等不會動的元素）。"""
        self.map_surface.fill(C_BG)
        for y in range(self.office_map.height):
            for x in range(self.office_map.width):
                cell = self.office_map.grid[y, x]
                color = _CELL_COLOR.get(cell, C_EMPTY)
                rect = pygame.Rect(
                    x * CELL_SIZE + 1,
                    y * CELL_SIZE + 1,
                    CELL_SIZE - 2,
                    CELL_SIZE - 2,
                )
                pygame.draw.rect(self.map_surface, color, rect, border_radius=3)

        # 繪製格線
        for x in range(self.office_map.width + 1):
            pygame.draw.line(
                self.map_surface,
                C_GRID_LINE,
                (x * CELL_SIZE, 0),
                (x * CELL_SIZE, self.map_pixel_h),
            )
        for y in range(self.office_map.height + 1):
            pygame.draw.line(
                self.map_surface,
                C_GRID_LINE,
                (0, y * CELL_SIZE),
                (self.map_pixel_w, y * CELL_SIZE),
            )

        # 繪製具名位置標籤
        for name, loc in self.office_map.named_locations.items():
            lx = loc.position[0] * CELL_SIZE + CELL_SIZE // 2
            ly = loc.position[1] * CELL_SIZE - 2
            label = self.font_sm.render(name, True, (180, 185, 200))
            label.set_alpha(140)
            lrect = label.get_rect(midbottom=(lx, ly))
            self.map_surface.blit(label, lrect)

    def _render_path(self) -> None:
        """渲染當前導航路徑。"""
        self.path_surface.fill((0, 0, 0, 0))
        if not self.navigator.is_navigating:
            return
        remaining = self.navigator.remaining_path
        if len(remaining) < 2:
            return

        # 繪製路徑點
        pulse = abs(math.sin(self.frame_count * 0.08))
        for i, (px, py) in enumerate(remaining):
            alpha = int(60 + 40 * pulse)
            cx = px * CELL_SIZE + CELL_SIZE // 2
            cy = py * CELL_SIZE + CELL_SIZE // 2
            r = 4 + int(2 * pulse)
            pygame.draw.circle(
                self.path_surface, (80, 180, 255, alpha), (cx, cy), r
            )

        # 繪製路徑連線
        points = [
            (p[0] * CELL_SIZE + CELL_SIZE // 2, p[1] * CELL_SIZE + CELL_SIZE // 2)
            for p in remaining
        ]
        if len(points) >= 2:
            pygame.draw.lines(
                self.path_surface, (80, 180, 255, 50), False, points, 2
            )

    def _render_hover_highlight(self, surface: pygame.Surface) -> None:
        """繪製滑鼠懸停格子的高亮框。"""
        if self._hover_cell is None:
            return
        gx, gy = self._hover_cell
        rect = pygame.Rect(
            gx * CELL_SIZE, gy * CELL_SIZE, CELL_SIZE, CELL_SIZE
        )
        highlight = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        highlight.fill(C_HOVER)
        surface.blit(highlight, rect.topleft)
        pygame.draw.rect(surface, (255, 255, 255, 100), rect, 1)

    def _render_text_input(self) -> None:
        """繪製文字輸入框（位於地圖下方或上方）。"""
        if not self._text_input_active:
            return
        box_w = self.map_pixel_w - 40
        box_h = 36
        box_x = 20
        box_y = self.map_pixel_h - box_h - 10

        # 背景
        bg_rect = pygame.Rect(box_x, box_y, box_w, box_h)
        pygame.draw.rect(self.screen, C_TEXT_INPUT_BG, bg_rect, border_radius=6)
        pygame.draw.rect(self.screen, C_TEXT_INPUT_BORDER, bg_rect, 2, border_radius=6)

        # 提示文字
        prompt = self.font_sm.render("說話: ", True, C_TEXT_HIGHLIGHT)
        self.screen.blit(prompt, (box_x + 8, box_y + 10))

        # 輸入文字 + 游標閃爍
        cursor = "|" if (self.frame_count // 15) % 2 == 0 else ""
        txt = self.font_md.render(
            self._text_input_buffer + cursor, True, C_TEXT
        )
        self.screen.blit(txt, (box_x + 50, box_y + 9))

    def _render_robot(self, surface: pygame.Surface) -> None:
        """繪製機器人。"""
        rx, ry = self.robot.position
        cx = rx * CELL_SIZE + CELL_SIZE // 2
        cy = ry * CELL_SIZE + CELL_SIZE // 2

        # 光暈效果
        pulse = 0.7 + 0.3 * abs(math.sin(self.frame_count * 0.06))
        glow_r = int(CELL_SIZE * 0.6 * pulse)
        glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(
            glow_surf, (50, 220, 120, int(40 * pulse)), (glow_r, glow_r), glow_r
        )
        surface.blit(glow_surf, (int(cx) - glow_r, int(cy) - glow_r))

        # 機器人主體
        body_r = int(CELL_SIZE * 0.35)
        pygame.draw.circle(surface, C_ROBOT, (int(cx), int(cy)), body_r)
        pygame.draw.circle(surface, (30, 180, 90), (int(cx), int(cy)), body_r, 2)

        # 眼睛
        eye_offset = body_r // 3
        eye_r = 3
        pygame.draw.circle(
            surface, (255, 255, 255),
            (int(cx) - eye_offset, int(cy) - eye_offset // 2), eye_r,
        )
        pygame.draw.circle(
            surface, (255, 255, 255),
            (int(cx) + eye_offset, int(cy) - eye_offset // 2), eye_r,
        )

        # 天線（根據 antenna_pos 角度繪製兩根短線）
        ant = self.robot.antenna_pos
        for i, (sign, angle) in enumerate([(-1, ant[1]), (1, ant[0])]):
            ax = cx + sign * (body_r * 0.5)
            ay = cy - body_r
            tip_x = ax + sign * 6
            tip_y = ay - 10 + angle * 8  # 角度影響天線高度
            pygame.draw.line(
                surface, C_ROBOT, (int(ax), int(ay)), (int(tip_x), int(tip_y)), 2
            )
            pygame.draw.circle(surface, (100, 255, 160), (int(tip_x), int(tip_y)), 3)

        # 朝向指示器（小三角形）
        heading_rad = math.radians(self.robot.heading)
        ind_dist = body_r + 5
        ind_x = cx + math.cos(heading_rad) * ind_dist
        ind_y = cy - math.sin(heading_rad) * ind_dist  # y 軸翻轉
        pygame.draw.circle(surface, (200, 255, 200), (int(ind_x), int(ind_y)), 3)

    def _render_persons(self, surface: pygame.Surface) -> None:
        """繪製場景中的人物。"""
        visible = [
            (name, p)
            for name, p in self.scenario.persons.items()
            if p.is_visible
        ]
        for i, (name, person) in enumerate(visible):
            px = person.position[0] * CELL_SIZE + CELL_SIZE // 2
            py = person.position[1] * CELL_SIZE + CELL_SIZE // 2
            r = int(CELL_SIZE * 0.3)

            # 人物圓圈
            pygame.draw.circle(surface, C_PERSON, (int(px), int(py)), r)
            pygame.draw.circle(surface, (200, 140, 30), (int(px), int(py)), r, 2)

            # 名稱標籤
            label = self.font_sm.render(name, True, C_TEXT)
            lrect = label.get_rect(midtop=(int(px), int(py) + r + 2))
            surface.blit(label, lrect)

    def _render_panel(self) -> None:
        """繪製右側資訊面板。"""
        panel_x = self.map_pixel_w
        panel_rect = pygame.Rect(panel_x, 0, PANEL_WIDTH, self.win_h)
        pygame.draw.rect(self.screen, C_PANEL_BG, panel_rect)
        pygame.draw.line(
            self.screen, C_PANEL_BORDER, (panel_x, 0), (panel_x, self.win_h), 2
        )

        x = panel_x + 16
        y = 16

        # ── 標題 ──
        title = self.font_lg.render("Reachy Mini 模擬器", True, C_TEXT_HIGHLIGHT)
        self.screen.blit(title, (x, y))
        y += 36

        # ── 時間 ──
        office_min = self._sim_to_office_minutes(self.scenario.current_time)
        time_str = _office_minutes_str(office_min)
        sim_sec = self.scenario.current_time

        time_label = self.font_md.render(
            f"辦公時間: {time_str}   模擬秒: {sim_sec:.0f}", True, C_TEXT
        )
        self.screen.blit(time_label, (x, y))
        y += 24

        speed_str = f"速度: {self.speed_multiplier:.1f}x"
        if self.paused:
            speed_str += "  [暫停]"
        speed_label = self.font_sm.render(speed_str, True, C_TEXT_DIM)
        self.screen.blit(speed_label, (x, y))
        y += 28

        # ── 分隔線 ──
        pygame.draw.line(
            self.screen, C_PANEL_BORDER,
            (x, y), (panel_x + PANEL_WIDTH - 16, y),
        )
        y += 12

        # ── 機器人狀態 ──
        sec_title = self.font_md.render("機器人狀態", True, C_TEXT_HIGHLIGHT)
        self.screen.blit(sec_title, (x, y))
        y += 22

        state = self.robot.get_state_summary()
        pos_str = f"位置: ({state['position'][0]:.1f}, {state['position'][1]:.1f})"
        pos_label = self.font_sm.render(pos_str, True, C_TEXT)
        self.screen.blit(pos_label, (x + 8, y))
        y += 18

        move_str = f"狀態: → {self.navigator.current_target}" if self.navigator.is_navigating else "狀態: 待命"
        move_label = self.font_sm.render(move_str, True, C_TEXT)
        self.screen.blit(move_label, (x + 8, y))
        y += 18

        ant = state["antenna_pos_deg"]
        ant_str = f"天線: L={ant[1]:.0f}°  R={ant[0]:.0f}°"
        ant_label = self.font_sm.render(ant_str, True, C_TEXT)
        self.screen.blit(ant_label, (x + 8, y))
        y += 18

        head_str = f"頭部: yaw={state['head_yaw_deg']:.0f}°  pitch={state['head_pitch_deg']:.0f}°"
        head_label = self.font_sm.render(head_str, True, C_TEXT)
        self.screen.blit(head_label, (x + 8, y))
        y += 18

        # AI 模式與表情狀態
        ai_mode = "Claude API" if self.brain.is_api_mode else "Fallback"
        ai_color = C_TEXT_HIGHLIGHT if self.brain.is_api_mode else C_TEXT_DIM
        ai_label = self.font_sm.render(f"AI: {ai_mode}", True, ai_color)
        self.screen.blit(ai_label, (x + 8, y))
        y += 18

        expr_str = f"表情: {self.expression.state}"
        if self.expression._emotion:
            expr_str += f" [{self.expression._emotion}]"
        expr_label = self.font_sm.render(expr_str, True, C_TEXT)
        self.screen.blit(expr_label, (x + 8, y))
        y += 26

        # ── 行事曆 ──
        pygame.draw.line(
            self.screen, C_PANEL_BORDER,
            (x, y), (panel_x + PANEL_WIDTH - 16, y),
        )
        y += 12
        cal_title = self.font_md.render("行事曆", True, C_TEXT_HIGHLIGHT)
        self.screen.blit(cal_title, (x, y))
        y += 22

        current_m = self.calendar.get_current()
        if current_m:
            cm_label = self.font_sm.render(
                f"進行中: {current_m}", True, (255, 130, 130)
            )
            self.screen.blit(cm_label, (x + 8, y))
            y += 18

        next_m = self.calendar.get_next()
        if next_m:
            nm_label = self.font_sm.render(
                f"下一場: {next_m}", True, C_TEXT_DIM
            )
            self.screen.blit(nm_label, (x + 8, y))
            y += 18
        y += 10

        # ── 人物 ──
        pygame.draw.line(
            self.screen, C_PANEL_BORDER,
            (x, y), (panel_x + PANEL_WIDTH - 16, y),
        )
        y += 12
        ppl_title = self.font_md.render("辦公室人物", True, C_TEXT_HIGHLIGHT)
        self.screen.blit(ppl_title, (x, y))
        y += 22

        visible = [
            (name, p)
            for name, p in self.scenario.persons.items()
            if p.is_visible
        ]
        if visible:
            for name, person in visible:
                p_label = self.font_sm.render(
                    f"  {name} @ ({person.position[0]:.0f}, {person.position[1]:.0f})",
                    True, C_PERSON,
                )
                self.screen.blit(p_label, (x + 8, y))
                y += 18
        else:
            empty_label = self.font_sm.render("  (無人)", True, C_TEXT_DIM)
            self.screen.blit(empty_label, (x + 8, y))
            y += 18
        y += 10

        # ── 滑鼠懸停資訊 ──
        pygame.draw.line(
            self.screen, C_PANEL_BORDER,
            (x, y), (panel_x + PANEL_WIDTH - 16, y),
        )
        y += 12
        hover_title = self.font_md.render("格子資訊", True, C_TEXT_HIGHLIGHT)
        self.screen.blit(hover_title, (x, y))
        y += 22

        if self._hover_cell is not None:
            hx, hy = self._hover_cell
            cell_val = self.office_map.grid[hy, hx]
            cell_name = _CELL_TYPE_NAME.get(cell_val, "?")
            walkable = self.office_map.is_walkable(hx, hy)
            walk_str = "可通行" if walkable else "不可通行"

            coord_label = self.font_sm.render(
                f"  座標: ({hx}, {hy})  類型: {cell_name}", True, C_TEXT
            )
            self.screen.blit(coord_label, (x + 8, y))
            y += 18

            walk_color = C_TEXT_HIGHLIGHT if walkable else C_EVENT_LEAVE
            walk_label = self.font_sm.render(
                f"  {walk_str}", True, walk_color
            )
            self.screen.blit(walk_label, (x + 8, y))
            y += 18

            # 顯示該格子所屬的具名位置（如果有的話）
            for loc_name, loc in self.office_map.named_locations.items():
                if loc.position == (hx, hy):
                    loc_label = self.font_sm.render(
                        f"  位置: {loc_name}", True, C_EVENT_CALENDAR
                    )
                    self.screen.blit(loc_label, (x + 8, y))
                    y += 18
                    break
        else:
            no_hover = self.font_sm.render(
                "  (將滑鼠移到地圖上)", True, C_TEXT_DIM
            )
            self.screen.blit(no_hover, (x + 8, y))
            y += 18
        y += 10

        # ── 事件日誌 ──
        pygame.draw.line(
            self.screen, C_PANEL_BORDER,
            (x, y), (panel_x + PANEL_WIDTH - 16, y),
        )
        y += 12
        log_title = self.font_md.render("事件日誌", True, C_TEXT_HIGHLIGHT)
        self.screen.blit(log_title, (x, y))
        y += 22

        max_log_lines = max(1, (self.win_h - y - 60) // 18)
        recent = self.event_log[-max_log_lines:]
        for time_str, color, msg in recent:
            log_line = self.font_sm.render(
                f"[{time_str}] {msg}", True, color
            )
            self.screen.blit(log_line, (x + 4, y))
            y += 18

        # ── 操作說明 ──
        bottom_y = self.win_h - 46
        help1 = "左鍵:導航  右鍵:人物  T:說話"
        help2 = "空白鍵:暫停  上下:速度  R:重啟  Q:離開"
        h1_label = self.font_sm.render(help1, True, C_TEXT_DIM)
        h2_label = self.font_sm.render(help2, True, C_TEXT_DIM)
        self.screen.blit(h1_label, (panel_x + 16, bottom_y))
        self.screen.blit(h2_label, (panel_x + 16, bottom_y + 16))

    def _handle_event(self, event: SimEvent) -> None:
        """處理場景事件，委派給 AIBrain 產生回應。"""
        office_min = self._sim_to_office_minutes(event.time)
        ts = _office_minutes_str(office_min)

        if event.event_type == "person_appears":
            name = event.data["name"]
            loc = event.data.get("location", "")
            self.event_log.append((ts, C_EVENT_PERSON, f"{name} 出現在{loc}"))
            self.brain.handle_event("person_appears", event.data)
            if loc == "大門":
                self.navigator.navigate_to("大門", from_pos=self.robot.position)

        elif event.event_type == "person_leaves":
            name = event.data["name"]
            self.event_log.append((ts, C_EVENT_LEAVE, f"{name} 離開了"))
            self.brain.handle_event("person_leaves", event.data)

        elif event.event_type == "calendar_event":
            title = event.data["title"]
            room = event.data["room"]
            self.event_log.append(
                (ts, C_EVENT_CALENDAR, f"行事曆: {title} @ {room}")
            )
            self.brain.handle_event("calendar_event", event.data)
            self.navigator.navigate_to(room, from_pos=self.robot.position)

        elif event.event_type == "user_speaks":
            name = event.data.get("name", "???")
            text = event.data.get("text", "")
            self.event_log.append((ts, C_TEXT, f'{name}: "{text}"'))
            self.expression.set_state("LISTENING")
            self.brain.handle_event("user_speaks", event.data)

        elif event.event_type == "idle":
            self.brain.handle_event("idle", event.data)
            if not self.navigator.is_navigating:
                self.navigator.navigate_to("走廊中心", from_pos=self.robot.position)

        elif event.event_type == "person_moves":
            name = event.data.get("name", "")
            loc = event.data.get("location", "")
            if name and loc:
                self.event_log.append((ts, C_TEXT_DIM, f"{name} 移動到{loc}"))

    def _create_demo_scenario(self) -> list[SimEvent]:
        """與 main.py 相同的 demo 場景。"""
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

    def _reset(self) -> None:
        """重置模擬狀態。"""
        # 停止舊的 brain 執行緒（若有的話）
        self.brain.stop()

        charger = self.office_map.get_location("充電站")
        self.robot = MockReachyMini(
            position=(float(charger.position[0]), float(charger.position[1])),
            speed=3.0,
        )
        self.scenario = ScenarioEngine()
        self.navigator = Navigator(self.office_map)
        self.calendar = CalendarMock()
        self.event_log.clear()

        mode_label = "Claude API" if self.brain.is_api_mode else "固定台詞 (Fallback)"
        self.event_log.append(("08:50", C_TEXT_DIM, "系統啟動..."))
        self.event_log.append(("08:50", C_TEXT_DIM, f"對話模式: {mode_label}"))

        # 重置 AI 大腦與表情引擎
        self.brain.clear_history()
        self.brain.start()
        self.expression = ExpressionEngine()

        events = self._create_demo_scenario()
        self.scenario.load(events)
        self.scenario.on_event = self._handle_event
        self.scenario.set_speed(1.0)
        self.scenario.start()
        self.paused = False
        self.frame_count = 0
        self._text_input_active = False
        self._text_input_buffer = ""
        self._interactive_person_counter = 0
        _resp_counters.clear()

    def run(self) -> None:
        """啟動 pygame 主迴圈。"""
        self._reset()

        running = True
        while running:
            # ── 更新滑鼠懸停位置 ──
            mx, my = pygame.mouse.get_pos()
            self._hover_cell = self._pixel_to_grid(mx, my)

            # ── 事件處理 ──
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False

                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    grid = self._pixel_to_grid(ev.pos[0], ev.pos[1])
                    if grid is not None:
                        if ev.button == 1:  # 左鍵：導航
                            self._handle_left_click(grid)
                        elif ev.button == 3:  # 右鍵：新增/移除人物
                            self._handle_right_click(grid)

                elif ev.type == pygame.KEYDOWN:
                    if self._text_input_active:
                        # 文字輸入模式下的按鍵處理
                        if ev.key == pygame.K_RETURN:
                            self._handle_text_submit()
                        elif ev.key == pygame.K_ESCAPE:
                            self._text_input_active = False
                            self._text_input_buffer = ""
                        elif ev.key == pygame.K_BACKSPACE:
                            self._text_input_buffer = self._text_input_buffer[:-1]
                        elif ev.unicode and ev.unicode.isprintable():
                            self._text_input_buffer += ev.unicode
                    else:
                        # 一般按鍵處理
                        if ev.key in (pygame.K_q, pygame.K_ESCAPE):
                            running = False
                        elif ev.key == pygame.K_SPACE:
                            self.paused = not self.paused
                        elif ev.key == pygame.K_UP:
                            self.speed_multiplier = min(
                                self.speed_multiplier + 0.5, 5.0
                            )
                        elif ev.key == pygame.K_DOWN:
                            self.speed_multiplier = max(
                                self.speed_multiplier - 0.5, 0.5
                            )
                        elif ev.key == pygame.K_r:
                            self._reset()
                        elif ev.key == pygame.K_t:
                            self._text_input_active = True
                            self._text_input_buffer = ""

            # ── 更新模擬 ──
            if not self.paused:
                effective_dt = self.sim_dt * self.speed_multiplier
                self.scenario.tick(effective_dt)

                office_min = self._sim_to_office_minutes(
                    self.scenario.current_time
                )
                self.calendar.set_current_time(office_min)

                self.navigator.update(effective_dt, self.robot)

                # 表情引擎驅動天線與頭部動畫
                self.expression.update(self.robot)

            # ── 渲染 ──
            self.screen.fill(C_BG)

            # 地圖底圖
            self.screen.blit(self.map_surface, (0, 0))

            # 路徑
            self._render_path()
            self.screen.blit(self.path_surface, (0, 0))

            # 滑鼠懸停高亮
            self._render_hover_highlight(self.screen)

            # 人物
            self._render_persons(self.screen)

            # 機器人
            self._render_robot(self.screen)

            # 文字輸入框
            self._render_text_input()

            # 右側面板
            self._render_panel()

            pygame.display.flip()
            self.frame_count += 1
            self.clock.tick(30)  # 30 FPS

            # 模擬結束時自動暫停
            if self.scenario.is_finished and not self.navigator.is_navigating:
                if not self.paused:
                    self.paused = True
                    self.event_log.append(
                        (
                            _office_minutes_str(
                                self._sim_to_office_minutes(
                                    self.scenario.current_time
                                )
                            ),
                            C_TEXT_HIGHLIGHT,
                            "模擬完成！按 R 重新開始",
                        )
                    )

        self.brain.stop()
        pygame.quit()


def main() -> None:
    """入口點。"""
    viz = Visualizer()
    viz.run()


if __name__ == "__main__":
    main()
