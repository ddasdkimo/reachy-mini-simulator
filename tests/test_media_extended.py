"""測試擴充的媒體功能（音檔播放、錄音、DoA）。"""

import numpy as np
import pytest

from reachy_mini_simulator.mock_media import MockMedia


class TestSoundPlayback:
    """測試音檔播放。"""

    def test_play_sound(self):
        """播放後 is_sound_playing 為 True。"""
        media = MockMedia()
        media.play_sound("/path/to/sound.wav")
        assert media.is_sound_playing()

    def test_stop_sound(self):
        """停止後 is_sound_playing 為 False。"""
        media = MockMedia()
        media.play_sound("/path/to/sound.wav")
        media.stop_sound()
        assert not media.is_sound_playing()

    def test_not_playing_initially(self):
        """初始不播放音檔。"""
        media = MockMedia()
        assert not media.is_sound_playing()


class TestRecording:
    """測試錄音功能。"""

    def test_start_recording(self):
        """開始錄音後 is_recording 為 True。"""
        media = MockMedia()
        media.start_recording()
        assert media.is_recording

    def test_stop_recording(self):
        """停止錄音後 is_recording 為 False。"""
        media = MockMedia()
        media.start_recording()
        media.stop_recording()
        assert not media.is_recording

    def test_not_recording_initially(self):
        """初始不錄音。"""
        media = MockMedia()
        assert not media.is_recording

    def test_get_audio_sample_while_recording(self):
        """錄音中取得樣本回傳非 None。"""
        media = MockMedia()
        media.start_recording()
        sample = media.get_audio_sample()
        assert sample is not None
        assert isinstance(sample, np.ndarray)
        assert sample.dtype == np.float32
        assert len(sample) > 0

    def test_get_audio_sample_not_recording(self):
        """未錄音時回傳 None。"""
        media = MockMedia()
        assert media.get_audio_sample() is None


class TestDoa:
    """測試聲源方向。"""

    def test_get_doa_range(self):
        """get_doa 回傳 0~360 範圍的值。"""
        media = MockMedia()
        for _ in range(20):
            doa = media.get_doa()
            assert 0.0 <= doa <= 360.0

    def test_get_doa_is_float(self):
        """get_doa 回傳浮點數。"""
        media = MockMedia()
        doa = media.get_doa()
        assert isinstance(doa, float)
