"""測試 IMU 感測器數據。"""

import pytest

from reachy_mini_simulator.mock_robot import MockReachyMini


class TestIMUData:
    """測試 get_imu_data。"""

    def test_returns_dict(self):
        """回傳字典。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        assert isinstance(data, dict)

    def test_has_accelerometer(self):
        """包含 accelerometer 鍵。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        assert "accelerometer" in data
        assert len(data["accelerometer"]) == 3

    def test_has_gyroscope(self):
        """包含 gyroscope 鍵。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        assert "gyroscope" in data
        assert len(data["gyroscope"]) == 3

    def test_has_quaternion(self):
        """包含 quaternion 鍵。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        assert "quaternion" in data
        assert len(data["quaternion"]) == 4

    def test_accelerometer_z_near_gravity(self):
        """靜止時 z 軸加速度接近 9.81。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        az = data["accelerometer"][2]
        assert az == pytest.approx(9.81, abs=0.5)

    def test_gyroscope_near_zero(self):
        """靜止時角速度接近 0。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        for g in data["gyroscope"]:
            assert g == pytest.approx(0.0, abs=0.5)

    def test_quaternion_unit(self):
        """四元數接近單位四元數 [1, 0, 0, 0]。"""
        robot = MockReachyMini()
        data = robot.get_imu_data()
        q = data["quaternion"]
        assert q[0] == pytest.approx(1.0)
        assert q[1] == pytest.approx(0.0)
        assert q[2] == pytest.approx(0.0)
        assert q[3] == pytest.approx(0.0)
