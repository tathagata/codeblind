import logging
import re

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


# Example usage
if __name__ == "__main__":
    parser = VoiceParser()
    print(parser.speech_to_text())