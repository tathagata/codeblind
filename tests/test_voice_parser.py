from voice_parser import VoiceParser


def test_voice_parser_instantiation():
    parser = VoiceParser()
    assert isinstance(parser, VoiceParser)


def test_speech_to_text_prints_empty_string(capsys):
    parser = VoiceParser()
    parser.speech_to_text()
    captured = capsys.readouterr()
    assert captured.out == "\n"


def test_speech_to_text_returns_none():
    parser = VoiceParser()
    result = parser.speech_to_text()
    assert result is None
