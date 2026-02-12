"""Reachy Mini 辦公室助手模擬器 - 終端 Demo。

整合 MockReachyMini、ScenarioEngine、OfficeMap、Navigator、CalendarMock，
在終端中模擬機器人在辦公室中的一日行為。

執行方式::

    python -m reachy_mini_simulator.main
"""

from __future__ import annotations

import os
import time
import logging

from .ai_brain import AIBrain, BrainResponse
from .expression import ExpressionEngine
from .mock_robot import MockReachyMini
from .scenario import ScenarioEngine, SimEvent, SimPerson
from .office_map import create_default_office, OfficeMap, CellType
from .navigation import Navigator, a_star, create_default_patrol
from .calendar_mock import CalendarMock

logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
)
logger = logging.getLogger(__name__)

# ANSI 色碼
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"
BG_BLUE = "\033[44m"
BG_GREEN = "\033[42m"

def clear_screen() -> None:
    """清除終端畫面。"""
    os.system("cls" if os.name == "nt" else "clear")


def render_map_with_entities(
    office_map: OfficeMap,
    robot_pos: tuple[float, float],
    persons: dict[str, SimPerson],
    path: list[tuple[int, int]] | None = None,
) -> str:
    """繪製帶有機器人和人物標記的 ASCII 地圖。"""
    # 字元對照
    cell_chars = {
        CellType.EMPTY: "·",
        CellType.WALL: "█",
        CellType.DOOR: "▫",
        CellType.DESK: "▦",
        CellType.CHAIR: "○",
        CellType.CHARGER: "⚡",
    }

    # 建立 2D 字元陣列
    display = []
    for y in range(office_map.height):
        row = []
        for x in range(office_map.width):
            cell = office_map.grid[y, x]
            row.append(cell_chars.get(cell, "?"))
        display.append(row)

    # 畫路徑
    if path:
        for px, py in path:
            if 0 <= py < office_map.height and 0 <= px < office_map.width:
                if display[py][px] == "·":
                    display[py][px] = f"{DIM}·{RESET}"

    # 畫人物
    person_chars = "①②③④⑤⑥⑦⑧⑨"
    visible_persons = [
        (name, p) for name, p in persons.items() if p.is_visible
    ]
    for i, (name, person) in enumerate(visible_persons):
        px, py = int(round(person.position[0])), int(round(person.position[1]))
        if 0 <= py < office_map.height and 0 <= px < office_map.width:
            char = person_chars[i % len(person_chars)]
            display[py][px] = f"{YELLOW}{char}{RESET}"

    # 畫機器人
    rx, ry = int(round(robot_pos[0])), int(round(robot_pos[1]))
    if 0 <= ry < office_map.height and 0 <= rx < office_map.width:
        display[ry][rx] = f"{GREEN}◉{RESET}"

    # 組裝
    lines = []
    # 標頭
    header = "    " + "".join(f"{i % 10}" for i in range(office_map.width))
    lines.append(f"{DIM}{header}{RESET}")

    for y in range(office_map.height):
        row_str = "".join(display[y])
        lines.append(f"{DIM}{y:3d}{RESET} {row_str}")

    # 圖例
    lines.append("")
    legend_parts = []
    for name, person in visible_persons:
        idx = list(persons.keys()).index(name)
        char = person_chars[idx % len(person_chars)]
        legend_parts.append(f"{YELLOW}{char}{RESET}={name}")
    lines.append(
        f"  {GREEN}◉{RESET}=機器人  "
        + "  ".join(legend_parts)
    )

    return "\n".join(lines)


def render_status(
    sim_time: float,
    sim_minutes: float,
    robot,
    navigator: Navigator,
    calendar: CalendarMock,
    event_log: list[str],
) -> str:
    """繪製狀態面板。"""
    hours = int(sim_minutes // 60)
    mins = int(sim_minutes % 60)
    secs = int(sim_time % 60)

    state = robot.get_state_summary()
    ant = state["antenna_pos_deg"]

    lines = []
    lines.append(f"{BOLD}{'═' * 50}{RESET}")
    lines.append(
        f"{BOLD}  🕐 模擬時間: {hours:02d}:{mins:02d}:{secs:02d}"
        f"    （模擬秒: {sim_time:.0f}）{RESET}"
    )
    lines.append(f"{'─' * 50}")

    # 機器人狀態
    move_status = f"→ {navigator.current_target}" if navigator.is_navigating else "待命"
    lines.append(f"  {CYAN}機器人位置:{RESET} ({state['position'][0]:.1f}, {state['position'][1]:.1f})  {move_status}")
    lines.append(f"  {CYAN}天線角度:{RESET}  L={ant[1]:.0f}°  R={ant[0]:.0f}°")
    lines.append(f"  {CYAN}頭部:{RESET}      yaw={state['head_yaw_deg']:.0f}°  pitch={state['head_pitch_deg']:.0f}°")
    lines.append(f"  {CYAN}身體:{RESET}      yaw={state['body_yaw_deg']:.0f}°")

    # 下一場會議
    next_meeting = calendar.get_next()
    current_meeting = calendar.get_current()
    if current_meeting:
        lines.append(f"  {RED}進行中:{RESET}    {current_meeting}")
    if next_meeting:
        lines.append(f"  {YELLOW}下一場:{RESET}    {next_meeting}")

    # 事件日誌（最近 5 條）
    lines.append(f"{'─' * 50}")
    lines.append(f"  {BOLD}事件日誌:{RESET}")
    for entry in event_log[-6:]:
        lines.append(f"  {entry}")

    lines.append(f"{BOLD}{'═' * 50}{RESET}")
    return "\n".join(lines)


def create_demo_scenario() -> list[SimEvent]:
    """建立 demo 用的辦公室一日場景。

    使用壓縮時間：每 10 模擬秒 = 1 小時辦公時間。
    """
    return [
        # 08:55 - 機器人從充電站出發
        SimEvent(time=5, event_type="idle", data={"message": "早安！新的一天開始了"}),
        # 09:00 - David 到辦公室
        SimEvent(time=15, event_type="person_appears", data={
            "name": "David", "position": [18, 5], "location": "大門",
        }),
        SimEvent(time=18, event_type="user_speaks", data={
            "name": "David", "text": "早安！今天天氣真好",
        }),
        # David 走到辦公桌
        SimEvent(time=25, event_type="person_moves", data={
            "name": "David", "position": [16, 1], "location": "辦公桌1",
        }),
        # 09:00 站會提醒
        SimEvent(time=30, event_type="calendar_event", data={
            "title": "每日站會", "room": "會議室A", "in_minutes": 5,
        }),
        # Amy 到辦公室
        SimEvent(time=40, event_type="person_appears", data={
            "name": "Amy", "position": [18, 5], "location": "大門",
        }),
        # 閒置
        SimEvent(time=60, event_type="idle", data={}),
        # 10:00 週會提醒
        SimEvent(time=75, event_type="calendar_event", data={
            "title": "週會", "room": "會議室C", "in_minutes": 5,
        }),
        # 訪客來了
        SimEvent(time=95, event_type="person_appears", data={
            "name": "訪客", "position": [18, 6], "location": "大門",
        }),
        SimEvent(time=100, event_type="user_speaks", data={
            "name": "訪客", "text": "請問會議室在哪裡？",
        }),
        # Amy 離開
        SimEvent(time=115, event_type="person_leaves", data={"name": "Amy"}),
        # 下午閒置
        SimEvent(time=130, event_type="idle", data={}),
        # 14:00 1-on-1 提醒
        SimEvent(time=140, event_type="calendar_event", data={
            "title": "1-on-1", "room": "會議室B", "in_minutes": 5,
        }),
        # 訪客離開
        SimEvent(time=155, event_type="person_leaves", data={"name": "訪客"}),
        # David 離開
        SimEvent(time=170, event_type="person_leaves", data={"name": "David"}),
        # 下班閒置
        SimEvent(time=180, event_type="idle", data={"message": "大家都走了...我也該回去充電了"}),
    ]


def main() -> None:
    """執行終端 Demo。"""
    print(f"\n{BOLD}{BG_BLUE} Reachy Mini 辦公室助手模擬器 {RESET}\n")
    print(f"  按 {BOLD}Ctrl+C{RESET} 結束模擬\n")
    time.sleep(1)

    # 初始化各模組
    office_map = create_default_office()
    charger = office_map.get_location("充電站")
    robot = MockReachyMini(
        position=(float(charger.position[0]), float(charger.position[1])),
        speed=3.0,             # 格/秒
    )
    scenario = ScenarioEngine()
    navigator = Navigator(office_map)
    calendar = CalendarMock()

    # 載入場景
    events = create_demo_scenario()
    scenario.load(events)

    # AI 大腦與表情引擎
    brain = AIBrain()
    expression = ExpressionEngine()

    # 事件日誌
    event_log: list[str] = [f"{DIM}系統啟動...{RESET}"]
    mode_label = "AI" if brain.is_api_mode else "固定台詞"
    event_log.append(f"{DIM}  對話模式: {mode_label}{RESET}")

    # 模擬時間對應的辦公時間（每 10 秒 = 1 小時）
    office_start_minutes = 8 * 60 + 50  # 08:50
    sim_to_office_ratio = 6.0  # 1 模擬秒 = 6 分鐘辦公時間

    def sim_to_office_minutes(sim_time: float) -> float:
        return office_start_minutes + sim_time * sim_to_office_ratio

    # AI 回應回呼 - 在背景執行緒中觸發
    def on_brain_response(resp: BrainResponse) -> None:
        """處理 AI 大腦的回應：更新事件日誌並觸發情緒動畫。"""
        office_min = sim_to_office_minutes(scenario.current_time)
        time_str = f"{int(office_min // 60):02d}:{int(office_min % 60):02d}"
        emotion_tag = f"[{resp.emotion}]" if resp.emotion else ""
        event_log.append(
            f"  {GREEN}[{time_str}]{RESET} {emotion_tag} {resp.text}"
        )
        if resp.emotion:
            expression.trigger_emotion(resp.emotion)

    def on_brain_processing_start() -> None:
        expression.set_state("PROCESSING")

    def on_brain_processing_end() -> None:
        expression.set_state("IDLE")

    brain.on_response = on_brain_response
    brain.on_processing_start = on_brain_processing_start
    brain.on_processing_end = on_brain_processing_end
    brain.start()

    # 場景事件處理
    def handle_event(event: SimEvent) -> None:
        office_min = sim_to_office_minutes(event.time)
        time_str = f"{int(office_min // 60):02d}:{int(office_min % 60):02d}"

        if event.event_type == "person_appears":
            name = event.data["name"]
            loc = event.data.get("location", "")
            event_log.append(
                f"  {GREEN}[{time_str}]{RESET} {YELLOW}{name}{RESET} 出現在{loc}"
            )
            brain.handle_event("person_appears", event.data)
            # 機器人移動到大門迎接
            if loc == "大門":
                navigator.navigate_to("大門", from_pos=robot.position)

        elif event.event_type == "person_leaves":
            name = event.data["name"]
            event_log.append(
                f"  {RED}[{time_str}]{RESET} {name} 離開了"
            )
            brain.handle_event("person_leaves", event.data)

        elif event.event_type == "calendar_event":
            title = event.data["title"]
            room = event.data["room"]
            event_log.append(
                f"  {MAGENTA}[{time_str}]{RESET} 行事曆: {title} @ {room}"
            )
            brain.handle_event("calendar_event", event.data)
            # 機器人移動到會議室
            navigator.navigate_to(room, from_pos=robot.position)

        elif event.event_type == "user_speaks":
            name = event.data.get("name", "???")
            text = event.data.get("text", "")
            event_log.append(
                f"  {BLUE}[{time_str}]{RESET} {name}: 「{text}」"
            )
            expression.set_state("LISTENING")
            brain.handle_event("user_speaks", event.data)

        elif event.event_type == "idle":
            brain.handle_event("idle", event.data)
            # 閒置時巡邏
            if not navigator.is_navigating:
                navigator.navigate_to("走廊中心", from_pos=robot.position)

    scenario.on_event = handle_event

    # 模擬速度（倍速）
    scenario.set_speed(1.0)

    # 開始
    scenario.start()
    sim_dt = 0.5  # 每幀 0.5 秒

    print(f"  {GREEN}地圖載入完成{RESET}（{office_map.width}×{office_map.height}）")
    print(f"  {GREEN}場景載入完成{RESET}（{scenario.total_events} 個事件）")
    print(f"  {GREEN}機器人就緒{RESET}：充電站 → 開始巡邏\n")
    time.sleep(1.5)

    try:
        frame = 0
        while not scenario.is_finished or navigator.is_navigating:
            # 推進模擬
            scenario.tick(sim_dt)

            # 更新行事曆時間
            office_min = sim_to_office_minutes(scenario.current_time)
            calendar.set_current_time(office_min)

            # 更新導航
            navigator.update(sim_dt, robot)

            # 表情引擎驅動天線與頭部動畫
            expression.update(robot)

            # 每 2 幀渲染一次
            if frame % 2 == 0:
                clear_screen()

                # 地圖
                map_str = render_map_with_entities(
                    office_map,
                    robot.position,
                    scenario.persons,
                    navigator.remaining_path if navigator.is_navigating else None,
                )
                print(map_str)

                # 狀態面板
                status_str = render_status(
                    scenario.current_time,
                    office_min,
                    robot,
                    navigator,
                    calendar,
                    event_log,
                )
                print(status_str)

            frame += 1
            time.sleep(0.15)  # 控制渲染速度

        # 模擬結束
        clear_screen()
        map_str = render_map_with_entities(
            office_map, robot.position, scenario.persons
        )
        print(map_str)
        print(f"\n{BOLD}{BG_GREEN} 模擬完成！ {RESET}\n")
        print(f"  總模擬時間: {scenario.current_time:.0f} 秒")
        print(f"  觸發事件數: {scenario.triggered_count} / {scenario.total_events}")
        print(f"  機器人指令數: {len(robot.state_log)}")
        print(f"\n  事件回顧:")
        for entry in event_log:
            print(entry)
        print()

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}模擬中斷{RESET}")
    finally:
        brain.stop()
        robot.close()


if __name__ == "__main__":
    main()
