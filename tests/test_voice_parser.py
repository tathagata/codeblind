import pytest
from unittest.mock import MagicMock

from voice_parser import VoiceParser, VoiceParserError


class TestVoiceParserSanitize:
    def test_sanitize_valid_input(self):
        parser = VoiceParser(recognizer=MagicMock())
        assert parser.sanitize("  Hello   World  ") == "Hello World"

    def test_sanitize_strips_extra_spaces(self):
        parser = VoiceParser(recognizer=MagicMock())
        assert parser.sanitize("generate   fibonacci") == "generate fibonacci"

    def test_sanitize_empty_raises(self):
        parser = VoiceParser(recognizer=MagicMock())
        with pytest.raises(VoiceParserError):
            parser.sanitize("")

    def test_sanitize_whitespace_only_raises(self):
        parser = VoiceParser(recognizer=MagicMock())
        with pytest.raises(VoiceParserError):
            parser.sanitize("   ")


class TestVoiceParserTranscribe:
    def _make_parser(self):
        import speech_recognition as sr

        mock_recognizer = MagicMock()
        parser = VoiceParser(recognizer=mock_recognizer)
        return parser, mock_recognizer, sr

    def test_transcribe_returns_text(self):
        parser, mock_recognizer, _ = self._make_parser()
        mock_audio = MagicMock()
        mock_recognizer.recognize_google.return_value = "generate fibonacci"
        assert parser.transcribe(mock_audio) == "generate fibonacci"

    def test_transcribe_unknown_value_raises(self):
        parser, mock_recognizer, sr = self._make_parser()
        mock_recognizer.recognize_google.side_effect = sr.UnknownValueError()
        with pytest.raises(VoiceParserError, match="unintelligible"):
            parser.transcribe(MagicMock())

    def test_transcribe_request_error_raises(self):
        parser, mock_recognizer, sr = self._make_parser()
        mock_recognizer.recognize_google.side_effect = sr.RequestError("service down")
        with pytest.raises(VoiceParserError, match="service error"):
            parser.transcribe(MagicMock())
