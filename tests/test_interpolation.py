"""測試插值系統。"""

import numpy as np
import pytest

from reachy_mini_simulator.interpolation import (
    InterpolationMethod,
    InterpolationEngine,
    InterpolationTarget,
    interpolate,
)


class TestInterpolateFunction:
    """測試 interpolate() 函式。"""

    @pytest.mark.parametrize("method", list(InterpolationMethod))
    def test_boundary_zero(self, method):
        """t=0 時回傳 0。"""
        assert interpolate(0.0, method) == pytest.approx(0.0, abs=1e-6)

    @pytest.mark.parametrize("method", list(InterpolationMethod))
    def test_boundary_one(self, method):
        """t=1 時回傳約 1.0。"""
        assert interpolate(1.0, method) == pytest.approx(1.0, abs=1e-6)

    def test_linear_midpoint(self):
        """LINEAR 在 t=0.5 回傳 0.5。"""
        assert interpolate(0.5, InterpolationMethod.LINEAR) == pytest.approx(0.5)

    def test_min_jerk_monotonic(self):
        """MIN_JERK 在 0~1 之間單調遞增。"""
        prev = 0.0
        for i in range(1, 11):
            t = i / 10.0
            val = interpolate(t, InterpolationMethod.MIN_JERK)
            assert val >= prev
            prev = val

    def test_ease_midpoint(self):
        """EASE 在 t=0.5 回傳 0.5。"""
        assert interpolate(0.5, InterpolationMethod.EASE) == pytest.approx(0.5)

    def test_cartoon_overshoot(self):
        """CARTOON 在中段有過衝效果（值 > 1.0）。"""
        val = interpolate(0.7, InterpolationMethod.CARTOON)
        assert val > 1.0

    def test_clamp_below_zero(self):
        """t < 0 被 clamp 到 0。"""
        assert interpolate(-0.5, InterpolationMethod.LINEAR) == pytest.approx(0.0)

    def test_clamp_above_one(self):
        """t > 1 被 clamp 到 1。"""
        assert interpolate(1.5, InterpolationMethod.LINEAR) == pytest.approx(1.0)


class TestInterpolationTarget:
    """測試 InterpolationTarget dataclass。"""

    def test_is_done_initially_false(self):
        target = InterpolationTarget(duration=1.0)
        assert not target.is_done

    def test_is_done_when_elapsed(self):
        target = InterpolationTarget(duration=1.0, elapsed=1.0)
        assert target.is_done

    def test_progress_zero(self):
        target = InterpolationTarget(duration=1.0, elapsed=0.0)
        assert target.progress == pytest.approx(0.0)

    def test_progress_half(self):
        target = InterpolationTarget(duration=2.0, elapsed=1.0)
        assert target.progress == pytest.approx(0.5)

    def test_progress_capped(self):
        target = InterpolationTarget(duration=1.0, elapsed=2.0)
        assert target.progress == pytest.approx(1.0)

    def test_zero_duration(self):
        target = InterpolationTarget(duration=0.0)
        assert target.progress == pytest.approx(1.0)


class TestInterpolationEngine:
    """測試 InterpolationEngine 生命週期。"""

    def test_not_active_initially(self):
        engine = InterpolationEngine()
        assert not engine.is_active

    def test_tick_returns_none_without_target(self):
        engine = InterpolationEngine()
        assert engine.tick(0.1) is None

    def test_start_and_tick(self):
        engine = InterpolationEngine()
        target = InterpolationTarget(
            start_head=np.eye(4),
            end_head=np.eye(4) * 2.0,
            duration=1.0,
            method=InterpolationMethod.LINEAR,
        )
        engine.start(target)
        assert engine.is_active

        result = engine.tick(0.5)
        assert result is not None
        assert "head" in result

    def test_engine_completes(self):
        engine = InterpolationEngine()
        target = InterpolationTarget(
            start_body_yaw=0.0,
            end_body_yaw=1.0,
            duration=1.0,
            method=InterpolationMethod.LINEAR,
        )
        engine.start(target)

        engine.tick(0.5)
        assert engine.is_active

        engine.tick(0.6)
        # After elapsed >= duration, next tick returns None
        result = engine.tick(0.1)
        assert result is None
        assert not engine.is_active

    def test_cancel(self):
        engine = InterpolationEngine()
        target = InterpolationTarget(
            start_body_yaw=0.0,
            end_body_yaw=1.0,
            duration=1.0,
        )
        engine.start(target)
        assert engine.is_active

        engine.cancel()
        assert not engine.is_active

    def test_antenna_interpolation(self):
        engine = InterpolationEngine()
        target = InterpolationTarget(
            start_antennas=[0.0, 0.0],
            end_antennas=[1.0, 1.0],
            duration=1.0,
            method=InterpolationMethod.LINEAR,
        )
        engine.start(target)
        result = engine.tick(0.5)
        assert result is not None
        assert "antennas" in result
        assert len(result["antennas"]) == 2
        # At t=0.5 with LINEAR, should be around 0.5
        assert result["antennas"][0] == pytest.approx(0.5, abs=0.1)
