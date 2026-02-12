"""Reachy Mini Office Assistant Simulator."""

from .robot_interface import RobotInterface, MediaInterface
from .ai_brain import AIBrain, BrainResponse, parse_emotion
from .audio_input import AudioInput
from .factory import create_robot
from .calendar_mock import CalendarMock, Meeting
from .expression import ExpressionEngine
from .mock_media import MockMedia
from .mock_robot import MockReachyMini
from .real_robot import RealReachyMini, RealMedia
from .chassis_controller import ChassisInterface, MockChassis, SerialChassis
from .obstacle_detector import (
    ObstacleDetectorInterface,
    MockObstacleDetector,
    SensorObstacleDetector,
)
from .office_map import OfficeMap, CellType, NamedLocation, create_default_office
from .navigation import Navigator, a_star, create_default_patrol
from .scenario import ScenarioEngine, SimEvent, SimPerson
from .tts_engine import TTSEngine

try:
    from .visualizer import Visualizer
except ImportError:
    Visualizer = None  # type: ignore[assignment,misc]

try:
    from .web_server import app as web_app
except ImportError:
    web_app = None  # type: ignore[assignment]

__all__ = [
    "AIBrain",
    "AudioInput",
    "BrainResponse",
    "CalendarMock",
    "CellType",
    "ChassisInterface",
    "create_robot",
    "ExpressionEngine",
    "MediaInterface",
    "Meeting",
    "MockChassis",
    "MockMedia",
    "MockObstacleDetector",
    "MockReachyMini",
    "NamedLocation",
    "Navigator",
    "ObstacleDetectorInterface",
    "OfficeMap",
    "RealMedia",
    "RealReachyMini",
    "RobotInterface",
    "ScenarioEngine",
    "SensorObstacleDetector",
    "SerialChassis",
    "SimEvent",
    "SimPerson",
    "TTSEngine",
    "Visualizer",
    "web_app",
    "a_star",
    "create_default_office",
    "create_default_patrol",
    "parse_emotion",
]
