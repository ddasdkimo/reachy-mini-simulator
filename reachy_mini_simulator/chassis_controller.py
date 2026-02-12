"""底盤控制器 - 抽象介面與實作。

定義 ChassisInterface 抽象基底類別，以及兩種實作：
- MockChassis：純軟體模擬底盤，在 2D 空間中移動。
- SerialChassis：透過 serial port 與 ESP32/Arduino 底盤通訊。
"""

from __future__ import annotations

import json
import logging
import math
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ChassisInterface(ABC):
    """底盤控制器抽象基底類別。

    定義底盤移動控制的統一介面，讓模擬底盤和真實底盤
    都遵循相同的操作方式。
    """

    @abstractmethod
    def set_velocity(self, linear_speed: float, angular_speed: float) -> None:
        """設定底盤線速度和角速度。

        Args:
            linear_speed: 線速度（m/s），正值為前進。
            angular_speed: 角速度（rad/s），正值為逆時針旋轉。
        """

    @abstractmethod
    def stop(self) -> None:
        """停止底盤移動。"""

    @abstractmethod
    def get_odometry(self) -> tuple[float, float, float]:
        """讀取里程計資訊。

        Returns:
            (x, y, heading) 元組，x/y 單位為公尺，heading 單位為弧度。
        """

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """底盤是否已連線。"""

    @abstractmethod
    def close(self) -> None:
        """釋放資源、關閉連線。"""


class MockChassis(ChassisInterface):
    """模擬底盤，在 2D 空間中以運動學模型移動。

    根據設定的線速度和角速度，在每次 tick 時更新位置。
    適合在沒有實體底盤的情況下測試導航邏輯。

    Attributes:
        x: 目前 x 座標（公尺）。
        y: 目前 y 座標（公尺）。
        heading: 目前朝向（弧度）。
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        heading: float = 0.0,
    ) -> None:
        """初始化模擬底盤。

        Args:
            x: 初始 x 座標（公尺）。
            y: 初始 y 座標（公尺）。
            heading: 初始朝向（弧度）。
        """
        self.x = x
        self.y = y
        self.heading = heading
        self._linear_speed: float = 0.0
        self._angular_speed: float = 0.0
        self._last_tick: float = time.monotonic()
        self._connected = True

        logger.info(
            "MockChassis 已初始化：位置=(%.2f, %.2f)，朝向=%.2f rad",
            x, y, heading,
        )

    def set_velocity(self, linear_speed: float, angular_speed: float) -> None:
        """設定模擬底盤的速度。"""
        self._linear_speed = linear_speed
        self._angular_speed = angular_speed

    def stop(self) -> None:
        """停止模擬底盤。"""
        self._linear_speed = 0.0
        self._angular_speed = 0.0

    def get_odometry(self) -> tuple[float, float, float]:
        """讀取模擬里程計。"""
        return (self.x, self.y, self.heading)

    @property
    def is_connected(self) -> bool:
        """模擬底盤始終已連線。"""
        return self._connected

    def tick(self, dt: float) -> None:
        """更新模擬底盤位置。

        使用差動驅動運動學模型（differential drive kinematics），
        根據目前速度和時間差更新位置和朝向。

        Args:
            dt: 時間差（秒）。
        """
        if abs(self._linear_speed) < 1e-9 and abs(self._angular_speed) < 1e-9:
            return

        # 更新朝向
        self.heading += self._angular_speed * dt
        # 正規化到 [-pi, pi]
        self.heading = math.atan2(math.sin(self.heading), math.cos(self.heading))

        # 更新位置
        self.x += self._linear_speed * math.cos(self.heading) * dt
        self.y += self._linear_speed * math.sin(self.heading) * dt

    def close(self) -> None:
        """關閉模擬底盤。"""
        self._connected = False
        self.stop()
        logger.info("MockChassis 已關閉")


class SerialChassis(ChassisInterface):
    """透過 serial port 與 ESP32/Arduino 底盤通訊。

    使用簡單的 JSON 串列協議與底盤微控制器通訊：
    - 發送指令：{"cmd": "vel", "linear": 0.5, "angular": 0.0}
    - 讀取里程計：{"cmd": "odom"}
    - 停止：{"cmd": "stop"}
    - 回應格式：{"x": 1.0, "y": 2.0, "heading": 0.5, "ok": true}

    若 pyserial 未安裝，建構時會記錄警告並以斷線狀態運作。
    """

    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 115200,
        timeout: float = 1.0,
    ) -> None:
        """初始化 Serial 底盤控制器。

        Args:
            port: 串列埠裝置路徑（如 /dev/ttyUSB0 或 COM3）。
            baudrate: 鮑率，預設 115200。
            timeout: 讀取逾時（秒）。
        """
        self._port_name = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial = None
        self._last_odom: tuple[float, float, float] = (0.0, 0.0, 0.0)

        try:
            import serial as pyserial
            self._serial = pyserial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=timeout,
            )
            logger.info("SerialChassis 已連線：%s @ %d", port, baudrate)
        except ImportError:
            logger.warning(
                "pyserial 未安裝，SerialChassis 將以斷線狀態運作。"
                "請執行 pip install pyserial 以啟用串列通訊。"
            )
        except Exception as e:
            logger.warning("無法開啟串列埠 %s：%s", port, e)

    def _send_command(self, cmd: dict) -> dict | None:
        """發送 JSON 指令並讀取回應。

        Args:
            cmd: 要發送的指令字典。

        Returns:
            回應字典，若通訊失敗則回傳 None。
        """
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
            logger.warning("串列通訊錯誤：%s", e)

        return None

    def set_velocity(self, linear_speed: float, angular_speed: float) -> None:
        """發送速度指令到底盤。"""
        resp = self._send_command({
            "cmd": "vel",
            "linear": round(linear_speed, 4),
            "angular": round(angular_speed, 4),
        })
        if resp is None:
            logger.debug("set_velocity 指令未送達（底盤未連線）")

    def stop(self) -> None:
        """發送停止指令到底盤。"""
        resp = self._send_command({"cmd": "stop"})
        if resp is None:
            logger.debug("stop 指令未送達（底盤未連線）")

    def get_odometry(self) -> tuple[float, float, float]:
        """從底盤讀取里程計資料。"""
        resp = self._send_command({"cmd": "odom"})
        if resp and "x" in resp and "y" in resp and "heading" in resp:
            self._last_odom = (
                float(resp["x"]),
                float(resp["y"]),
                float(resp["heading"]),
            )
        return self._last_odom

    @property
    def is_connected(self) -> bool:
        """串列底盤是否已連線。"""
        return self._serial is not None and self._serial.is_open

    def close(self) -> None:
        """關閉串列連線。"""
        self.stop()
        if self._serial is not None and self._serial.is_open:
            self._serial.close()
            logger.info("SerialChassis 已關閉連線：%s", self._port_name)
