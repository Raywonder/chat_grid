import sys

from chat_grid_native.screen_reader import MAX_SPEECH_LENGTH, ScreenReaderSpeech


def test_missing_screen_reader_is_safe(monkeypatch):
    speech = ScreenReaderSpeech()
    speech.library = None
    assert speech.available() is False
    if sys.platform == "darwin":
        monkeypatch.setattr("chat_grid_native.screen_reader.subprocess.Popen", lambda *args, **kwargs: object())
        assert speech.speak("hello") is True
    else:
        assert speech.speak("hello") is False


def test_speech_is_bounded():
    assert MAX_SPEECH_LENGTH == 2000
