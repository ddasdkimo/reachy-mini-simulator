"""工廠函式 - 根據模式建立 RobotInterface 實例。

透過 create_robot() 函式根據 mode 參數或環境變數 REACHY_MODE
建立 MockReachyMini 或 RealReachyMini 實例。
"""

import logging
import os

from .robot_interface import RobotInterface

logger = logging.getLogger(__name__)


def create_robot(mode: str | None = None, **kwargs) -> RobotInterface:
    """根據模式建立機器人實例。

    Args:
        mode: "mock" 或 "real"。若為 None，則讀取環境變數 REACHY_MODE，
              預設為 "mock"。
        **kwargs: 傳遞給對應建構子的額外參數。
            mock 模式支援：position, heading, speed, use_webcam。
            real 模式不需要額外參數（由 SDK 自動連線）。

    Returns:
        RobotInterface 實例。

    Raises:
        ValueError: 若 mode 不是 "mock" 或 "real"。
        ImportError: 若 real 模式但 reachy_mini SDK 未安裝。
    """
    if mode is None:
        mode = os.environ.get("REACHY_MODE", "mock").lower()

    if mode == "mock":
        from .mock_robot import MockReachyMini

        logger.info("建立 MockReachyMini（模擬模式）")
        return MockReachyMini(**kwargs)

    if mode == "real":
        try:
            from reachy_mini import ReachyMini
        except ImportError as e:
            raise ImportError(
                "reachy_mini SDK 未安裝。請執行 pip install reachy-mini "
                "或切換到 mock 模式。"
            ) from e

        from .real_robot import RealReachyMini

        logger.info("建立 RealReachyMini（真實機器人模式）")
        sdk_robot = ReachyMini()
        return RealReachyMini(sdk_robot)

    raise ValueError(
        f"未知的模式 '{mode}'，請使用 'mock' 或 'real'。"
    )
