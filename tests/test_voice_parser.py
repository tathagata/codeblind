import pytest
from unittest.mock import MagicMock, patch, call

from voice_parser import VoiceParser, VoiceParserError, HandyVoiceParser


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


class TestHandyVoiceParser:
    def _make_parser(self, **kwargs):
        """Create a HandyVoiceParser with a mocked pyperclip."""
        mock_pyperclip = MagicMock()
        parser = HandyVoiceParser(**kwargs)
        parser._pyperclip = mock_pyperclip
        return parser, mock_pyperclip

    # --- trigger() ---

    def test_trigger_calls_handy_toggle_transcription(self):
        parser, _ = self._make_parser(handy_executable="handy")
        with patch("voice_parser.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            parser.trigger()
        mock_run.assert_called_once_with(
            ["handy", "--toggle-transcription"],
            capture_output=True,
            text=True,
        )

    def test_trigger_raises_when_executable_not_found(self):
        parser, _ = self._make_parser(handy_executable="handy")
        with patch("voice_parser.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(VoiceParserError, match="not found"):
                parser.trigger()

    def test_trigger_raises_on_nonzero_exit_code(self):
        parser, _ = self._make_parser(handy_executable="handy")
        with patch("voice_parser.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="some error")
            with pytest.raises(VoiceParserError, match="exit code 1"):
                parser.trigger()

    # --- wait_for_transcript() ---

    def test_wait_for_transcript_returns_new_clipboard_content(self):
        parser, mock_pyperclip = self._make_parser(timeout=5, poll_interval=0.01)
        mock_pyperclip.paste.side_effect = ["old text", "old text", "new transcript"]
        result = parser.wait_for_transcript(previous_clipboard="old text")
        assert result == "new transcript"

    def test_wait_for_transcript_strips_whitespace(self):
        parser, mock_pyperclip = self._make_parser(timeout=5, poll_interval=0.01)
        mock_pyperclip.paste.return_value = "  transcribed text  "
        result = parser.wait_for_transcript(previous_clipboard="")
        assert result == "transcribed text"

    def test_wait_for_transcript_times_out(self):
        parser, mock_pyperclip = self._make_parser(timeout=0.05, poll_interval=0.01)
        mock_pyperclip.paste.return_value = "unchanged"
        with pytest.raises(VoiceParserError, match="Timed out"):
            parser.wait_for_transcript(previous_clipboard="unchanged")

    def test_wait_for_transcript_raises_without_pyperclip(self):
        parser, _ = self._make_parser()
        parser._pyperclip = None
        with pytest.raises(VoiceParserError, match="pyperclip is required"):
            parser.wait_for_transcript()

    def test_wait_for_transcript_raises_on_clipboard_error(self):
        parser, mock_pyperclip = self._make_parser(timeout=5, poll_interval=0.01)
        mock_pyperclip.paste.side_effect = Exception("clipboard unavailable")
        with pytest.raises(VoiceParserError, match="Failed to read clipboard"):
            parser.wait_for_transcript(previous_clipboard="")

    # --- speech_to_text() ---

    def test_speech_to_text_returns_sanitized_transcript(self):
        parser, mock_pyperclip = self._make_parser(timeout=5, poll_interval=0.01)
        mock_pyperclip.paste.side_effect = ["", "  write  a  sort  function  "]
        with patch("voice_parser.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            result = parser.speech_to_text()
        assert result == "write a sort function"

    def test_speech_to_text_raises_on_empty_transcript(self):
        parser, mock_pyperclip = self._make_parser(timeout=5, poll_interval=0.01)
        mock_pyperclip.paste.side_effect = ["old", "   "]
        with patch("voice_parser.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            with pytest.raises(VoiceParserError, match="empty transcript"):
                parser.speech_to_text()

    def test_speech_to_text_raises_without_pyperclip(self):
        parser, _ = self._make_parser()
        parser._pyperclip = None
        with pytest.raises(VoiceParserError, match="pyperclip is required"):
            parser.speech_to_text()

    def test_speech_to_text_triggers_handy_once(self):
        parser, mock_pyperclip = self._make_parser(timeout=5, poll_interval=0.01)
        mock_pyperclip.paste.side_effect = ["before", "after transcription"]
        with patch("voice_parser.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")
            parser.speech_to_text()
        mock_run.assert_called_once()

    def test_default_executable_is_handy(self):
        parser = HandyVoiceParser()
        assert parser._executable == "handy"

    def test_custom_executable_is_used(self):
        parser = HandyVoiceParser(handy_executable="/usr/local/bin/handy")
        assert parser._executable == "/usr/local/bin/handy"
