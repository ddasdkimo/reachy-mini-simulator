"""障礙偵測與避障模組。

定義 ObstacleDetectorInterface 抽象基底類別，以及兩種實作：
- MockObstacleDetector：根據 OfficeMap 模擬障礙偵測。
- SensorObstacleDetector：讀取 LIDAR 或超音波感測器（serial 或 GPIO）。
"""

from __future__ import annotations

import json
import logging
import math
from abc import ABC, abstractmethod
from typing import Callable

from .office_map import OfficeMap

logger = logging.getLogger(__name__)

# 預設感測器方向（8 方向，以弧度表示，從正前方開始順時針）
DEFAULT_SENSOR_ANGLES: list[float] = [
    0.0,                    # 正前方
    math.pi / 4,            # 右前 45°
    math.pi / 2,            # 正右
    3 * math.pi / 4,        # 右後 135°
    math.pi,                # 正後方
    -3 * math.pi / 4,       # 左後 135°
    -math.pi / 2,           # 正左
    -math.pi / 4,           # 左前 45°
]


class ObstacleDetectorInterface(ABC):
    """障礙偵測器抽象基底類別。

    定義障礙偵測的統一介面，讓模擬偵測器和真實感測器
    都遵循相同的操作方式。
    """

    @abstractmethod
    def get_distances(self) -> list[float]:
        """取得各方向的障礙物距離。

        Returns:
            各方向障礙物距離列表（公尺），順序對應感測器方向。
            若該方向無障礙物，回傳 float('inf')。
        """

    @abstractmethod
    def is_path_clear(self, direction: float, distance: float = 1.0) -> bool:
        """檢查指定方向的路徑是否暢通。

        Args:
            direction: 方向角度（弧度），相對於機器人朝向。
            distance: 檢查距離（公尺），預設 1.0。

        Returns:
            True 表示路徑暢通，False 表示有障礙物。
        """

    def on_obstacle(self, callback: Callable[[list[float]], None]) -> None:
        """註冊障礙物偵測回呼。

        當偵測到障礙物時（距離低於安全閾值），呼叫回呼函式。

        Args:
            callback: 回呼函式，參數為各方向距離列表。
        """
        self._obstacle_callbacks.append(callback)

    @property
    def _obstacle_callbacks(self) -> list[Callable[[list[float]], None]]:
        """障礙物回呼列表（延遲初始化）。"""
        if not hasattr(self, "_callbacks"):
            self._callbacks: list[Callable[[list[float]], None]] = []
        return self._callbacks

    def _notify_obstacle(self, distances: list[float]) -> None:
        """通知所有已註冊的障礙物回呼。"""
        for cb in self._obstacle_callbacks:
            try:
                cb(distances)
            except Exception as e:
                logger.warning("障礙物回呼執行失敗：%s", e)

    @abstractmethod
    def close(self) -> None:
        """釋放資源。"""


class MockObstacleDetector(ObstacleDetectorInterface):
    """根據 OfficeMap 模擬障礙偵測。

    透過在地圖上進行射線投射（raycasting），模擬各方向感測器
    偵測到的障礙物距離。

    Attributes:
        safe_distance: 安全距離閾值（公尺），低於此值觸發回呼。
    """

    def __init__(
        self,
        office_map: OfficeMap,
        robot_position_fn: Callable[[], tuple[float, float]],
        robot_heading_fn: Callable[[], float],
        sensor_angles: list[float] | None = None,
        max_range: float = 5.0,
        safe_distance: float = 0.5,
    ) -> None:
        """初始化模擬障礙偵測器。

        Args:
            office_map: 辦公室地圖。
            robot_position_fn: 取得機器人位置 (x, y) 的函式。
            robot_heading_fn: 取得機器人朝向（度）的函式。
            sensor_angles: 感測器方向列表（弧度），預設 8 方向。
            max_range: 最大偵測距離（公尺），預設 5.0。
            safe_distance: 安全距離閾值（公尺），預設 0.5。
        """
        self._map = office_map
        self._get_position = robot_position_fn
        self._get_heading = robot_heading_fn
        self._sensor_angles = sensor_angles or DEFAULT_SENSOR_ANGLES
        self._max_range = max_range
        self.safe_distance = safe_distance

        logger.info(
            "MockObstacleDetector 已初始化：%d 個感測方向，最大距離=%.1fm",
            len(self._sensor_angles),
            max_range,
        )

    def _raycast(self, start_x: float, start_y: float, angle_rad: float) -> float:
        """在地圖上進行射線投射，找出障礙物距離。

        從起點沿指定角度發射射線，以 0.25 格（約 0.125m）為步進，
        檢查每一步是否碰到不可通行的格子。

        Args:
            start_x: 起點 x（地圖格座標）。
            start_y: 起點 y（地圖格座標）。
            angle_rad: 射線方向（弧度）。

        Returns:
            障礙物距離（格數），若超出範圍回傳 max_range 對應的格數。
        """
        # 每格 0.5m，max_range 換算為格數
        max_steps = int(self._max_range / 0.5 * 4)  # 步進 = 0.25 格
        step_size = 0.25

        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        for i in range(1, max_steps + 1):
            cx = start_x + cos_a * step_size * i
            cy = start_y + sin_a * step_size * i
            gx = int(round(cx))
            gy = int(round(cy))

            if not self._map._in_bounds(gx, gy):
                # 超出地圖邊界，視為障礙
                return step_size * i * 0.5  # 轉為公尺

            if not self._map.is_walkable(gx, gy):
                return step_size * i * 0.5  # 轉為公尺

        return self._max_range

    def get_distances(self) -> list[float]:
        """根據地圖模擬各方向障礙物距離。"""
        px, py = self._get_position()
        heading_deg = self._get_heading()
        heading_rad = math.radians(heading_deg)

        distances: list[float] = []
        for sensor_angle in self._sensor_angles:
            world_angle = heading_rad + sensor_angle
            dist = self._raycast(px, py, world_angle)
            distances.append(dist)

        # 檢查是否需要觸發障礙物回呼
        if any(d < self.safe_distance for d in distances):
            self._notify_obstacle(distances)

        return distances

    def is_path_clear(self, direction: float, distance: float = 1.0) -> bool:
        """檢查指定方向是否暢通。"""
        px, py = self._get_position()
        heading_deg = self._get_heading()
        heading_rad = math.radians(heading_deg)
        world_angle = heading_rad + direction

        dist = self._raycast(px, py, world_angle)
        return dist >= distance

    def close(self) -> None:
        """釋放資源。"""
        logger.info("MockObstacleDetector 已關閉")


class SensorObstacleDetector(ObstacleDetectorInterface):
    """讀取 LIDAR 或超音波感測器的障礙偵測器。

    透過 serial port 與感測器微控制器通訊，讀取各方向距離資料。
    通訊協議與 SerialChassis 類似，使用 JSON 格式：
    - 發送讀取指令：{"cmd": "scan"}
    - 回應格式：{"distances": [1.2, 0.8, ...], "ok": true}

    若 pyserial 未安裝或連線失敗，所有方向回傳 float('inf')。
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB1",
        baudrate: int = 115200,
        timeout: float = 1.0,
        num_sensors: int = 8,
        safe_distance: float = 0.5,
    ) -> None:
        """初始化感測器障礙偵測器。

        Args:
            port: 串列埠裝置路徑。
            baudrate: 鮑率，預設 115200。
            timeout: 讀取逾時（秒）。
            num_sensors: 感測器數量，預設 8。
            safe_distance: 安全距離閾值（公尺）。
        """
        self._port_name = port
        self._num_sensors = num_sensors
        self._safe_distance = safe_distance
        self._serial = None
        self._last_distances: list[float] = [float("inf")] * num_sensors

        try:
            import serial as pyserial
            self._serial = pyserial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
            )
            logger.info("SensorObstacleDetector 已連線：%s", port)
        except ImportError:
            logger.warning(
                "pyserial 未安裝，SensorObstacleDetector 將以離線模式運作。"
            )
        except Exception as e:
            logger.warning("無法開啟感測器串列埠 %s：%s", port, e)

    def _send_command(self, cmd: dict) -> dict | None:
        """發送 JSON 指令並讀取回應。"""
        if self._serial is None or not self._serial.is_open:
            return None

        try:
            line = json.dumps(cmd) + "\n"
            self._serial.write(line.encode("utf-8"))
            self._serial.flush()

            response_line = self._serial.readline().decode("utf-8").strip()
            if response_line:
                return json.loads(response_line)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("感測器通訊錯誤：%s", e)

        return None

    def get_distances(self) -> list[float]:
        """從感測器讀取各方向距離。"""
        resp = self._send_command({"cmd": "scan"})
        if resp and "distances" in resp:
            raw = resp["distances"]
            self._last_distances = [float(d) for d in raw]

        # 檢查是否需要觸發障礙物回呼
        if any(d < self._safe_distance for d in self._last_distances):
            self._notify_obstacle(self._last_distances)

        return list(self._last_distances)

    def is_path_clear(self, direction: float, distance: float = 1.0) -> bool:
        """檢查指定方向是否暢通。

        將方向對應到最近的感測器，檢查該感測器距離是否大於指定距離。
        """
        if self._num_sensors == 0:
            return True

        # 將方向正規化到 [0, 2*pi)
        direction = direction % (2 * math.pi)

        # 找到最近的感測器索引
        sensor_spacing = 2 * math.pi / self._num_sensors
        idx = int(round(direction / sensor_spacing)) % self._num_sensors

        return self._last_distances[idx] >= distance

    def close(self) -> None:
        """關閉感測器連線。"""
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
            logger.info("SensorObstacleDetector 已關閉：%s", self._port_name)
