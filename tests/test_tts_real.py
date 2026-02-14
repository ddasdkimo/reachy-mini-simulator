"""TTS 引擎 real 模式測試。

測試 TTSEngine 透過 robot.media 推送音訊到機器人喇叭的功能，
以及 robot=None 時維持原有 sounddevice 播放行為。
"""

from unittest.mock import MagicMock, patch, call

import numpy as np
import pytest

from reachy_mini_simulator.tts_engine import TTSEngine, TTS_SAMPLE_RATE


def _make_mock_robot(sample_rate=24000):
    """建立帶有 mock media 的 robot 物件。"""
    robot = MagicMock()
    robot.media.get_output_audio_samplerate.return_value = sample_rate
    robot.media.is_playing = False
    return robot


class TestTTSWithMockRobot:
    """測試 TTS 透過 mock robot media 推送音訊。"""

    def test_robot_param_stored(self):
        """robot 參數正確存儲。"""
        robot = _make_mock_robot()
        tts = TTSEngine(robot=robot, api_key="fake-key")
        assert tts._robot is robot

    def test_robot_sample_rate_from_media(self):
        """從 robot.media.get_output_audio_samplerate() 取得取樣率。"""
        robot = _make_mock_robot(sample_rate=44100)
        tts = TTSEngine(robot=robot, api_key="fake-key")
        assert tts._robot_sample_rate == 44100
        robot.media.get_output_audio_samplerate.assert_called_once()

    def test_robot_sample_rate_fallback(self):
        """robot.media 取樣率取得失敗時使用預設值。"""
        robot = MagicMock()
        robot.media.get_output_audio_samplerate.side_effect = RuntimeError("SDK error")
        tts = TTSEngine(robot=robot, api_key="fake-key", output_sample_rate=16000)
        assert tts._robot_sample_rate == 16000

    def test_speak_calls_media_api(self):
        """speak() 透過 robot.media 呼叫 start_playing/push_audio_sample/stop_playing。"""
        robot = _make_mock_robot(sample_rate=24000)

        # 產生假 PCM 回應（24kHz, 16-bit, 0.1 秒 = 2400 samples）
        fake_pcm = np.zeros(2400, dtype=np.int16).tobytes()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_pcm

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response

        tts = TTSEngine(robot=robot, api_key="fake-key")
        tts._client = mock_client
        tts._api_available = True

        # 直接呼叫 _synthesize_and_play 避免執行緒
        tts._synthesize_and_play("測試")

        robot.media.start_playing.assert_called_once()
        robot.media.stop_playing.assert_called_once()
        assert robot.media.push_audio_sample.call_count >= 1
        # 確認推送的是 float32 陣列
        pushed = robot.media.push_audio_sample.call_args[0][0]
        assert pushed.dtype == np.float32

    def test_speak_stop_playing_on_error(self):
        """push_audio_sample 出錯時仍會呼叫 stop_playing。"""
        robot = _make_mock_robot(sample_rate=24000)
        robot.media.push_audio_sample.side_effect = RuntimeError("push failed")

        fake_pcm = np.zeros(2400, dtype=np.int16).tobytes()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_pcm

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response

        tts = TTSEngine(robot=robot, api_key="fake-key")
        tts._client = mock_client
        tts._api_available = True

        with pytest.raises(RuntimeError, match="push failed"):
            tts._synthesize_and_play("測試")

        # stop_playing 必須在 finally 中被呼叫
        robot.media.stop_playing.assert_called_once()

    def test_chunk_size_100ms(self):
        """chunk size 為 sample_rate // 10（100ms）。"""
        robot = _make_mock_robot(sample_rate=48000)

        # 0.2 秒 = 4800 samples @ 24kHz, 重新取樣至 48kHz ≈ 9600 samples
        # chunk_size = 48000 // 10 = 4800, 應推送 2 chunks
        fake_pcm = np.zeros(4800, dtype=np.int16).tobytes()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_pcm

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response

        tts = TTSEngine(robot=robot, api_key="fake-key")
        tts._client = mock_client
        tts._api_available = True

        tts._synthesize_and_play("測試")

        assert robot.media.push_audio_sample.call_count == 2


class TestTTSWithoutRobot:
    """測試無 robot 時維持現有行為。"""

    def test_no_robot_defaults(self):
        """robot=None 時 _robot 為 None。"""
        tts = TTSEngine(api_key="fake-key")
        assert tts._robot is None

    def test_no_robot_uses_sounddevice(self):
        """robot=None 時使用 sounddevice 播放。"""
        fake_pcm = np.zeros(2400, dtype=np.int16).tobytes()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_pcm

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response

        tts = TTSEngine(api_key="fake-key")
        tts._client = mock_client
        tts._api_available = True

        with patch("reachy_mini_simulator.tts_engine.sd") as mock_sd:
            tts._synthesize_and_play("測試")
            mock_sd.play.assert_called_once()
            mock_sd.wait.assert_called_once()

    def test_backward_compatible_no_args(self):
        """不傳 robot 參數時行為與原版一致。"""
        tts = TTSEngine()
        assert tts._robot is None
        assert tts._robot_sample_rate == 24000


class TestTTSCallbacks:
    """測試 callback 正確觸發。"""

    def test_on_speak_start_called(self):
        """on_speak_start 在合成前被呼叫。"""
        callback = MagicMock()
        tts = TTSEngine(api_key="fake-key", on_speak_start=callback)
        tts._api_available = True

        fake_pcm = np.zeros(2400, dtype=np.int16).tobytes()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_pcm

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        tts._client = mock_client

        with patch("reachy_mini_simulator.tts_engine.sd"):
            tts._process("測試")

        callback.assert_called_once()

    def test_on_speak_end_called(self):
        """on_speak_end 在播放完畢後被呼叫。"""
        callback = MagicMock()
        tts = TTSEngine(api_key="fake-key", on_speak_end=callback)
        tts._api_available = True

        fake_pcm = np.zeros(2400, dtype=np.int16).tobytes()
        mock_response = MagicMock()
        mock_response.read.return_value = fake_pcm

        mock_client = MagicMock()
        mock_client.audio.speech.create.return_value = mock_response
        tts._client = mock_client

        with patch("reachy_mini_simulator.tts_engine.sd"):
            tts._process("測試")

        callback.assert_called_once()

    def test_on_speak_end_called_on_error(self):
        """合成出錯時 on_speak_end 仍會被呼叫。"""
        end_cb = MagicMock()
        tts = TTSEngine(api_key="fake-key", on_speak_end=end_cb)
        tts._api_available = True

        mock_client = MagicMock()
        mock_client.audio.speech.create.side_effect = RuntimeError("API error")
        tts._client = mock_client

        # _process 會 catch 由 _synthesize_and_play 的例外，on_speak_end 在 finally
        # 但 _process 本身不 catch，由 _run 的 try/except 處理
        # 所以測試 _process 會 raise，但 on_speak_end 仍被呼叫
        with pytest.raises(RuntimeError):
            tts._process("測試")

        end_cb.assert_called_once()

    def test_callbacks_via_constructor(self):
        """透過建構子傳入 callback。"""
        start_cb = MagicMock()
        end_cb = MagicMock()
        tts = TTSEngine(on_speak_start=start_cb, on_speak_end=end_cb)
        assert tts.on_speak_start is start_cb
        assert tts.on_speak_end is end_cb
