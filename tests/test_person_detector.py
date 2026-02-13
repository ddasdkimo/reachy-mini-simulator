"""人物偵測模組測試。"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

from reachy_mini_simulator.person_detector import (
    MockPersonDetector,
    PersonDetectorInterface,
    YOLOPersonDetector,
    create_person_detector,
)


# ── MockPersonDetector 測試 ──────────────────────────────────────────


class TestMockInjectRemove:
    """測試 inject_person / remove_person 基本行為。"""

    def test_initial_state(self) -> None:
        d = MockPersonDetector()
        assert not d.person_visible
        assert d.person_count == 0
        assert d.person_positions == []

    def test_inject_and_remove(self) -> None:
        d = MockPersonDetector()
        d.inject_person("alice", (0.3, 0.7))
        assert d.person_visible
        assert d.person_count == 1
        assert d.person_positions == [(0.3, 0.7)]

        d.remove_person("alice")
        assert not d.person_visible
        assert d.person_count == 0
        assert d.person_positions == []

    def test_inject_default_position(self) -> None:
        d = MockPersonDetector()
        d.inject_person("bob")
        assert d.person_positions == [(0.5, 0.5)]

    def test_remove_nonexistent_no_error(self) -> None:
        d = MockPersonDetector()
        d.remove_person("ghost")  # 不應 raise


class TestMockCallbacks:
    """測試 on_person_appeared / on_person_left 回呼時機。"""

    def test_appeared_callback(self) -> None:
        d = MockPersonDetector()
        appeared = []
        d.on_person_appeared = lambda: appeared.append(True)

        d.inject_person("alice")
        assert len(appeared) == 1

    def test_left_callback(self) -> None:
        d = MockPersonDetector()
        left = []
        d.on_person_left = lambda: left.append(True)

        d.inject_person("alice")
        d.remove_person("alice")
        assert len(left) == 1

    def test_no_callback_when_not_set(self) -> None:
        d = MockPersonDetector()
        # 不設 callback，不應 raise
        d.inject_person("alice")
        d.remove_person("alice")


class TestMockMultiplePersons:
    """測試多人注入/移除時的 callback 觸發時機。"""

    def test_callback_only_on_zero_boundary(self) -> None:
        d = MockPersonDetector()
        appeared = []
        left = []
        d.on_person_appeared = lambda: appeared.append(True)
        d.on_person_left = lambda: left.append(True)

        d.inject_person("alice")   # 0→1: appeared
        d.inject_person("bob")     # 1→2: 不觸發
        assert len(appeared) == 1

        d.remove_person("alice")   # 2→1: 不觸發
        assert len(left) == 0

        d.remove_person("bob")     # 1→0: left
        assert len(left) == 1

    def test_person_count_tracks_correctly(self) -> None:
        d = MockPersonDetector()
        d.inject_person("a")
        d.inject_person("b")
        d.inject_person("c")
        assert d.person_count == 3

        d.remove_person("b")
        assert d.person_count == 2


class TestMockAbsenceDuration:
    """測試 get_person_absence_duration。"""

    def test_zero_when_person_visible(self) -> None:
        d = MockPersonDetector()
        d.inject_person("alice")
        assert d.get_person_absence_duration() == 0.0

    def test_accumulates_when_no_person(self) -> None:
        d = MockPersonDetector()
        d.update(1.0)
        d.update(0.5)
        assert d.get_person_absence_duration() == pytest.approx(1.5)

    def test_resets_on_inject(self) -> None:
        d = MockPersonDetector()
        d.update(2.0)
        assert d.get_person_absence_duration() == pytest.approx(2.0)

        d.inject_person("alice")
        assert d.get_person_absence_duration() == 0.0


class TestMockGetPersons:
    """測試 get_persons() 回傳值。"""

    def test_returns_copy(self) -> None:
        d = MockPersonDetector()
        d.inject_person("alice", (0.1, 0.2))
        d.inject_person("bob", (0.8, 0.9))

        persons = d.get_persons()
        assert persons == {"alice": (0.1, 0.2), "bob": (0.8, 0.9)}

        # 修改回傳值不應影響內部狀態
        persons["charlie"] = (0.5, 0.5)
        assert d.person_count == 2


class TestMockStartStop:
    """測試 start/stop 狀態切換。"""

    def test_initial_not_running(self) -> None:
        d = MockPersonDetector()
        assert not d.is_running

    def test_start_stop_toggle(self) -> None:
        d = MockPersonDetector()
        d.start()
        assert d.is_running
        d.stop()
        assert not d.is_running


# ── YOLOPersonDetector 測試 ──────────────────────────────────────────


class TestYOLOWithoutUltralytics:
    """測試 ultralytics 未安裝時的行為。"""

    def test_construction_ok(self) -> None:
        media = MagicMock()
        # 建構時不需 ultralytics
        detector = YOLOPersonDetector(media=media)
        assert not detector.is_running

    def test_start_raises_import_error(self) -> None:
        media = MagicMock()
        detector = YOLOPersonDetector(media=media)

        with patch.dict(sys.modules, {"ultralytics": None}):
            with pytest.raises(ImportError, match="ultralytics"):
                detector.start()


class TestYOLOWithMockUltralytics:
    """測試 ultralytics 存在時可正常建構與運行。"""

    def test_construction_with_params(self) -> None:
        media = MagicMock()
        detector = YOLOPersonDetector(
            media=media,
            model_path="yolov8s.pt",
            confidence=0.6,
            detect_interval=1.0,
        )
        assert detector._model_path == "yolov8s.pt"
        assert detector._confidence == 0.6
        assert detector._detect_interval == 1.0

    def test_start_stop_with_mock_ultralytics(self) -> None:
        """用 mock ultralytics 模組測試 start/stop 流程。"""
        media = MagicMock()
        detector = YOLOPersonDetector(media=media, detect_interval=0.1)

        # 建立假的 ultralytics 模組
        mock_ultralytics = types.ModuleType("ultralytics")
        mock_yolo_cls = MagicMock()
        mock_model = MagicMock()
        mock_model.return_value = []
        mock_yolo_cls.return_value = mock_model
        mock_ultralytics.YOLO = mock_yolo_cls

        with patch.dict(sys.modules, {"ultralytics": mock_ultralytics}):
            detector.start()
            assert detector.is_running

            # 短暫等待讓背景執行緒運行
            import time
            time.sleep(0.3)

            detector.stop()
            assert not detector.is_running


# ── 介面合規測試 ─────────────────────────────────────────────────────


class TestInterfaceCompliance:
    """驗證 MockPersonDetector 實作所有抽象方法。"""

    def test_mock_is_subclass(self) -> None:
        assert issubclass(MockPersonDetector, PersonDetectorInterface)

    def test_yolo_is_subclass(self) -> None:
        assert issubclass(YOLOPersonDetector, PersonDetectorInterface)

    def test_mock_instantiable(self) -> None:
        d = MockPersonDetector()
        # 驗證所有抽象方法都可呼叫
        d.start()
        d.stop()
        _ = d.is_running
        _ = d.person_visible
        _ = d.person_count
        _ = d.person_positions
        _ = d.get_person_absence_duration()
        d.update(0.1)


# ── 工廠函式測試 ─────────────────────────────────────────────────────


class TestFactory:
    """測試 create_person_detector 工廠函式。"""

    def test_factory_mock(self) -> None:
        d = create_person_detector("mock")
        assert isinstance(d, MockPersonDetector)

    def test_factory_yolo(self) -> None:
        media = MagicMock()
        d = create_person_detector("yolo", media=media)
        assert isinstance(d, YOLOPersonDetector)

    def test_factory_invalid_mode(self) -> None:
        with pytest.raises(ValueError, match="不支援"):
            create_person_detector("invalid")
