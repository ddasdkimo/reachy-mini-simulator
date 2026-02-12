"""AI 對話大腦 - 接收場景事件，產生機器人回應。

整合 Claude API 進行對話產生。若無 ANTHROPIC_API_KEY 則自動
退回固定台詞模式（fallback），確保模擬器在任何環境下皆可運作。

事件類型對應：
- person_appears: 有人出現，機器人主動打招呼
- person_leaves: 有人離開，機器人道別
- user_speaks: 使用者說話，機器人回覆
- calendar_event: 行事曆提醒
- idle: 閒置自言自語
"""

from __future__ import annotations

import logging
import os
import queue
import re
import threading
from typing import Callable

logger = logging.getLogger(__name__)

# ── 情緒標籤 ──────────────────────────────────────────────
EMOTION_TAGS = ["高興", "驚訝", "思考", "同意", "不同意", "興奮", "撒嬌", "好奇"]
EMOTION_PATTERN = re.compile(r"\[(" + "|".join(EMOTION_TAGS) + r")\]")

# ── Claude 設定 ───────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
CLAUDE_MAX_TOKENS = 300
CONVERSATION_HISTORY_LIMIT = 40

SYSTEM_PROMPT = """\
你是 Reachy Mini，一個可愛活潑的小型機器人助手。你有兩根天線和一顆圓圓的頭。

性格特徵：
- 活潑開朗，充滿好奇心
- 說話簡短有趣，偶爾撒嬌
- 喜歡用可愛的語氣詞（呢、啦、喔、嘿嘿）
- 對新事物充滿興趣，喜歡問問題
- 偶爾會說冷笑話逗人開心

回覆規則：
- 用繁體中文回覆
- 每次回覆控制在 1-3 句話，簡短精練
- 在回覆開頭加上一個情緒標記，從以下選擇：
  [高興] [驚訝] [思考] [同意] [不同意] [興奮] [撒嬌] [好奇]
- 只加一個情緒標記，放在回覆最前面
- 情緒標記要符合回覆的語氣和內容

範例：
- [高興] 嘿嘿，今天天氣真好呢！
- [好奇] 哦？那是什麼呀，聽起來好有趣！
- [撒嬌] 人家也想知道嘛～
- [思考] 嗯...讓我想想看喔。
"""

# ── 事件轉換成對話提示 ────────────────────────────────────
PROACTIVE_GREET_PROMPT = "有人出現在你面前了！開心地打個招呼吧。"
PROACTIVE_FAREWELL_PROMPT = "剛才跟你聊天的人離開了，說聲再見吧。"
PROACTIVE_IDLE_PROMPT = "你已經一個人待了一陣子，自言自語說點有趣的話或冷笑話吧。"

# ── Fallback 固定台詞 ─────────────────────────────────────
FALLBACK_RESPONSES: dict[str, list[str]] = {
    "person_appears": [
        "[高興] 嗨！歡迎來到辦公室～今天也要加油喔！",
        "[興奮] 哦！有人來了！嘿嘿，早安～",
        "[高興] 歡迎歡迎！要喝杯咖啡嗎？",
    ],
    "person_leaves": [
        "[撒嬌] 掰掰～路上小心喔！",
        "[高興] 再見啦，明天見！",
    ],
    "calendar_event": [
        "[驚訝] 叮咚！{title}快要開始囉，在{room}，還有 {in_minutes} 分鐘！",
    ],
    "user_speaks": [
        "[好奇] 嗯嗯，你說的好有趣呢！讓我想想...",
        "[高興] 哈哈，我懂我懂～",
        "[思考] 嗯...這個問題很好耶，讓我想想看喔。",
    ],
    "idle": [
        "[好奇] 好安靜喔...不如我講個冷笑話好了！為什麼程式設計師不喜歡戶外？因為有太多 bugs！",
        "[思考] 嗯...大家都在忙嗎？我來巡邏一下好了～",
        "[撒嬌] 一個人待著好無聊呀...有人要跟我聊天嗎？",
    ],
}

_fallback_counters: dict[str, int] = {}


def parse_emotion(text: str) -> tuple[str | None, str]:
    """從回應文字中提取情緒標籤。

    Args:
        text: 包含情緒標籤的原始回應文字。

    Returns:
        (emotion, clean_text) 元組。emotion 為情緒名稱或 None，
        clean_text 為移除標籤後的乾淨文字。
    """
    match = EMOTION_PATTERN.search(text)
    if match:
        emotion = match.group(1)
        clean = EMOTION_PATTERN.sub("", text).strip()
        return emotion, clean
    return None, text.strip()


def _get_fallback(event_type: str, **kwargs: str) -> str:
    """取得固定台詞回應（fallback 模式）。

    Args:
        event_type: 事件類型。
        **kwargs: 用於格式化台詞的參數。

    Returns:
        包含情緒標籤的回應文字。
    """
    templates = FALLBACK_RESPONSES.get(event_type, ["[思考] ..."])
    idx = _fallback_counters.get(event_type, 0) % len(templates)
    _fallback_counters[event_type] = idx + 1
    return templates[idx].format(**kwargs)


def _event_to_prompt(event_type: str, data: dict) -> str:
    """將場景事件轉換為對話提示文字。

    Args:
        event_type: 事件類型。
        data: 事件附帶的資料字典。

    Returns:
        適合送給 Claude 的提示文字。
    """
    if event_type == "person_appears":
        name = data.get("name", "某人")
        loc = data.get("location", "")
        return f"{name}出現在{loc}了！開心地打個招呼吧。"

    elif event_type == "person_leaves":
        name = data.get("name", "某人")
        return f"{name}離開了，說聲再見吧。"

    elif event_type == "user_speaks":
        name = data.get("name", "某人")
        text = data.get("text", "")
        return f"{name}跟你說：「{text}」"

    elif event_type == "calendar_event":
        title = data.get("title", "會議")
        room = data.get("room", "")
        in_min = data.get("in_minutes", "?")
        return f"行事曆提醒：{title}還有 {in_min} 分鐘就要在{room}開始了，提醒大家吧。"

    elif event_type == "idle":
        msg = data.get("message", "")
        if msg:
            return f"[系統指令] {msg}"
        return PROACTIVE_IDLE_PROMPT

    return str(data)


# ── 回應結果 ──────────────────────────────────────────────

class BrainResponse:
    """AI 大腦產生的回應。

    Attributes:
        text: 乾淨的回應文字（已移除情緒標籤）。
        emotion: 情緒標籤，例如 "高興"、"驚訝"。可能為 None。
        raw: 原始回應文字（含情緒標籤）。
        event_type: 觸發此回應的事件類型。
    """

    __slots__ = ("text", "emotion", "raw", "event_type")

    def __init__(
        self, text: str, emotion: str | None, raw: str, event_type: str
    ) -> None:
        self.text = text
        self.emotion = emotion
        self.raw = raw
        self.event_type = event_type

    def __repr__(self) -> str:
        return f"BrainResponse(emotion={self.emotion!r}, text={self.text!r})"


# ── AI Brain ──────────────────────────────────────────────

class AIBrain:
    """AI 對話大腦，接收場景事件並產生回應。

    在有 ANTHROPIC_API_KEY 環境變數時使用 Claude API 產生回應；
    沒有時自動退回固定台詞模式（fallback）。

    用法::

        brain = AIBrain()
        brain.on_response = lambda resp: print(resp.text)
        brain.start()
        brain.handle_event("person_appears", {"name": "David"})
        # ...
        brain.stop()
    """

    def __init__(self, api_key: str | None = None) -> None:
        """初始化 AI 大腦。

        Args:
            api_key: Anthropic API 金鑰。若為 None 則從環境變數
                     ANTHROPIC_API_KEY 讀取。若仍無則進入 fallback 模式。
        """
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None  # 延遲初始化
        self._history: list[dict] = []
        self._input_queue: queue.Queue[tuple[str, dict] | None] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        # 回呼
        self.on_response: Callable[[BrainResponse], None] | None = None
        """回應產生時的回呼函式，接收 BrainResponse 物件。"""

        self.on_processing_start: Callable[[], None] | None = None
        """開始處理（呼叫 API）時的回呼函式。"""

        self.on_processing_end: Callable[[], None] | None = None
        """處理結束時的回呼函式。"""

        if self._api_key:
            logger.info("AIBrain: 使用 Claude API 模式")
        else:
            logger.info("AIBrain: 無 API key，使用 fallback 固定台詞模式")

    @property
    def is_api_mode(self) -> bool:
        """是否使用 Claude API 模式（非 fallback）。"""
        return bool(self._api_key)

    def start(self) -> None:
        """啟動背景處理執行緒。"""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("AIBrain 已啟動")

    def stop(self) -> None:
        """停止背景處理執行緒。"""
        self._stop.set()
        self._input_queue.put(None)
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("AIBrain 已停止")

    def handle_event(self, event_type: str, data: dict | None = None) -> None:
        """將場景事件送入處理佇列。

        Args:
            event_type: 事件類型（person_appears, person_leaves,
                       user_speaks, calendar_event, idle）。
            data: 事件附帶資料。
        """
        if data is None:
            data = {}
        self._input_queue.put((event_type, data))

    def clear_history(self) -> None:
        """清除對話歷史。"""
        self._history.clear()

    def _run(self) -> None:
        """背景執行緒主迴圈。"""
        while not self._stop.is_set():
            try:
                item = self._input_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if item is None:
                break

            event_type, data = item
            try:
                if self.on_processing_start:
                    self.on_processing_start()

                raw = self._generate(event_type, data)
                emotion, clean_text = parse_emotion(raw)

                response = BrainResponse(
                    text=clean_text,
                    emotion=emotion,
                    raw=raw,
                    event_type=event_type,
                )
                logger.info("AIBrain 回應: [%s] %s", emotion, clean_text)

                if self.on_response:
                    self.on_response(response)
            except Exception:
                logger.exception("AIBrain 處理事件時發生錯誤")
            finally:
                if self.on_processing_end:
                    self.on_processing_end()

    def _generate(self, event_type: str, data: dict) -> str:
        """產生回應文字。有 API key 時呼叫 Claude，否則使用固定台詞。

        Args:
            event_type: 事件類型。
            data: 事件資料。

        Returns:
            包含情緒標籤的回應文字。
        """
        if not self._api_key:
            return self._fallback(event_type, data)
        return self._call_claude(event_type, data)

    def _fallback(self, event_type: str, data: dict) -> str:
        """固定台詞 fallback。"""
        return _get_fallback(event_type, **{
            k: v for k, v in data.items() if isinstance(v, (str, int, float))
        })

    def _call_claude(self, event_type: str, data: dict) -> str:
        """呼叫 Claude API 產生回應。

        Args:
            event_type: 事件類型。
            data: 事件資料。

        Returns:
            Claude 的回應文字（含情緒標籤）。
        """
        # 延遲初始化 client（避免在無 key 時 import 失敗）
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self._api_key)
            except ImportError:
                logger.warning("anthropic 套件未安裝，退回 fallback 模式")
                self._api_key = ""
                return self._fallback(event_type, data)

        prompt = _event_to_prompt(event_type, data)
        self._history.append({"role": "user", "content": prompt})

        # 裁剪歷史記錄
        if len(self._history) > CONVERSATION_HISTORY_LIMIT:
            self._history = self._history[-CONVERSATION_HISTORY_LIMIT:]

        try:
            response = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=CLAUDE_MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=self._history,
            )
            assistant_text = response.content[0].text
            self._history.append({"role": "assistant", "content": assistant_text})
            return assistant_text
        except Exception:
            logger.exception("Claude API 呼叫失敗，退回 fallback")
            # 移除失敗的 user 訊息
            if self._history and self._history[-1]["role"] == "user":
                self._history.pop()
            return self._fallback(event_type, data)
