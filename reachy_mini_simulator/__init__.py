"""Reachy Mini Office Assistant Simulator."""

from .robot_interface import RobotInterface, MediaInterface
from .ai_brain import AIBrain, BrainResponse, parse_emotion, parse_nav_target
from .audio_input import AudioInput
from .factory import create_robot
from .calendar_mock import CalendarMock, Meeting
from .expression import ExpressionEngine
from .interpolation import (
    InterpolationMethod,
    InterpolationEngine,
    InterpolationTarget,
    interpolate,
)
from .mock_media import MockMedia
from .mock_robot import MockReachyMini
from .motion import JointFrame, Move, MotionRecorder, MotionPlayer
from .real_robot import RealReachyMini, RealMedia
from .chassis_controller import ChassisInterface, MockChassis, SerialChassis
from .obstacle_detector import (
    ObstacleDetectorInterface,
    MockObstacleDetector,
    SensorObstacleDetector,
)
from .person_detector import (
    PersonDetectorInterface,
    MockPersonDetector,
    create_person_detector,
)
from .proactive import ProactiveTrigger

try:
    from .person_detector import YOLOPersonDetector
except ImportError:
    YOLOPersonDetector = None  # type: ignore[assignment,misc]
from .office_map import OfficeMap, CellType, NamedLocation, create_default_office
from .navigation import Navigator, a_star, create_default_patrol
from .scenario import ScenarioEngine, SimEvent, SimPerson
from .tts_engine import TTSEngine
from .utils import create_head_pose

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
    "create_head_pose",
    "create_robot",
    "ExpressionEngine",
    "InterpolationEngine",
    "InterpolationMethod",
    "InterpolationTarget",
    "interpolate",
    "JointFrame",
    "MediaInterface",
    "Meeting",
    "MockChassis",
    "MockMedia",
    "MockObstacleDetector",
    "MockPersonDetector",
    "MockReachyMini",
    "MotionPlayer",
    "MotionRecorder",
    "Move",
    "NamedLocation",
    "Navigator",
    "ObstacleDetectorInterface",
    "OfficeMap",
    "PersonDetectorInterface",
    "ProactiveTrigger",
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
    "create_person_detector",
    "parse_emotion",
    "YOLOPersonDetector",
]
