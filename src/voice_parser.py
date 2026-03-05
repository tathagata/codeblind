import logging
import re
import subprocess
import time

logger = logging.getLogger(__name__)


class VoiceParserError(Exception):
    """Raised when voice parsing fails."""


class VoiceParser:
    """Converts voice input to text using the SpeechRecognition library."""

    def __init__(self, recognizer=None):
        try:
            import speech_recognition as sr
            self._sr = sr
            self._recognizer = recognizer or sr.Recognizer()
        except ImportError:
            self._sr = None
            self._recognizer = recognizer
            logger.warning("speech_recognition library not available.")

    def listen(self):
        """Capture audio from the microphone and return an AudioData object."""
        if self._sr is None:
            raise VoiceParserError("speech_recognition library is not installed.")
        logger.info("Listening...")
        try:
            with self._sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(source)
            return audio
        except self._sr.WaitTimeoutError as e:
            raise VoiceParserError("No speech detected within the timeout period.") from e
        except Exception as e:
            raise VoiceParserError(f"Error capturing audio: {e}") from e

    def transcribe(self, audio):
        """Convert AudioData to text using Google Speech Recognition."""
        if self._sr is None:
            raise VoiceParserError("speech_recognition library is not installed.")
        logger.info("Processing speech to text...")
        try:
            text = self._recognizer.recognize_google(audio)
            logger.info("Transcribed: %s", text)
            return text
        except self._sr.UnknownValueError as e:
            raise VoiceParserError("Speech was unintelligible.") from e
        except self._sr.RequestError as e:
            raise VoiceParserError(f"Speech recognition service error: {e}") from e

    def sanitize(self, text):
        """Validate and sanitize transcribed text."""
        if not text or not text.strip():
            raise VoiceParserError("Transcribed text is empty.")
        return re.sub(r"\s+", " ", text.strip())

    def speech_to_text(self):
        """Full pipeline: listen -> transcribe -> sanitize -> return text."""
        audio = self.listen()
        raw_text = self.transcribe(audio)
        return self.sanitize(raw_text)


class HandyVoiceParser:
    """Delegates voice input to a running Handy instance (https://github.com/cjpais/Handy).

    Handy is a free, open-source, offline speech-to-text desktop application.
    This class triggers Handy's transcription via its CLI flag and monitors the
    clipboard for the resulting text, providing the same ``speech_to_text``
    interface as :class:`VoiceParser`.

    Handy must be installed and running before calling :meth:`speech_to_text`.
    See https://github.com/cjpais/Handy for installation instructions.
    """

    DEFAULT_HANDY_EXECUTABLE = "handy"
    DEFAULT_TIMEOUT = 30
    DEFAULT_POLL_INTERVAL = 0.25

    def __init__(self, handy_executable=None, timeout=None, poll_interval=None):
        self._executable = handy_executable or self.DEFAULT_HANDY_EXECUTABLE
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self._poll_interval = poll_interval if poll_interval is not None else self.DEFAULT_POLL_INTERVAL
        try:
            import pyperclip
            self._pyperclip = pyperclip
        except ImportError:
            self._pyperclip = None
            logger.warning("pyperclip library not available. Install it with: pip install pyperclip")

    def trigger(self):
        """Toggle Handy transcription by invoking the CLI flag.

        Sends ``--toggle-transcription`` to a running Handy instance.
        Raises :class:`VoiceParserError` if the Handy executable is not found
        or returns a non-zero exit code.
        """
        try:
            result = subprocess.run(
                [self._executable, "--toggle-transcription"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise VoiceParserError(
                    f"Handy returned exit code {result.returncode}: {result.stderr.strip()}"
                )
            logger.info("Handy transcription toggled.")
        except FileNotFoundError as e:
            raise VoiceParserError(
                f"Handy executable not found: '{self._executable}'. "
                "Ensure Handy is installed and available in PATH."
            ) from e

    def wait_for_transcript(self, previous_clipboard=""):
        """Wait for Handy to paste new text to the clipboard.

        Polls the clipboard until its content changes from *previous_clipboard*
        or until *timeout* seconds have elapsed.

        Returns the new clipboard content (stripped of surrounding whitespace).
        Raises :class:`VoiceParserError` on timeout or if pyperclip is unavailable.
        """
        if self._pyperclip is None:
            raise VoiceParserError(
                "pyperclip is required to read Handy's transcript from the clipboard. "
                "Install it with: pip install pyperclip"
            )
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            try:
                current = self._pyperclip.paste()
            except Exception as e:
                raise VoiceParserError(f"Failed to read clipboard: {e}") from e
            if current != previous_clipboard:
                logger.info("Handy transcript received from clipboard.")
                return current.strip()
            time.sleep(self._poll_interval)
        raise VoiceParserError(
            f"Timed out waiting for Handy transcript after {self._timeout}s. "
            "Ensure Handy is running and has finished transcribing."
        )

    def speech_to_text(self):
        """Delegate voice capture to Handy and return the transcribed text.

        Captures the current clipboard content, triggers Handy transcription,
        waits for the clipboard to be updated with the transcript, sanitizes
        the result, and returns it.

        The sanitization step reuses :meth:`VoiceParser.sanitize` logic:
        collapses internal whitespace and raises :class:`VoiceParserError` for
        empty results.
        """
        if self._pyperclip is None:
            raise VoiceParserError(
                "pyperclip is required for HandyVoiceParser. "
                "Install it with: pip install pyperclip"
            )
        try:
            previous = self._pyperclip.paste()
        except Exception as e:
            raise VoiceParserError(f"Failed to read clipboard: {e}") from e

        self.trigger()
        raw_text = self.wait_for_transcript(previous_clipboard=previous)

        if not raw_text:
            raise VoiceParserError("Handy returned an empty transcript.")
        return re.sub(r"\s+", " ", raw_text.strip())


# Example usage
if __name__ == "__main__":
    parser = VoiceParser()
    print(parser.speech_to_text())