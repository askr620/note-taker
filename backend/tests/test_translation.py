import sys
from types import SimpleNamespace

import pytest

from app.schemas import Settings, Transcript
from app.services import transcription


@pytest.mark.parametrize('task,source,expected_language,output', [
    ('translate', 'hi', 'hi', 'en'),
    ('translate', 'auto', None, 'en'),
    ('transcribe', 'hi', 'hi', 'hi'),
])
def test_whisper_translation_options(tmp_path, monkeypatch, task, source, expected_language, output):
    model = tmp_path / 'base'
    model.mkdir()
    (model / 'model.bin').touch()
    monkeypatch.setattr(transcription, 'MODEL_DIR', tmp_path)
    captured = {}

    class Whisper:
        def __init__(self, path, **kwargs):
            assert kwargs['local_files_only'] is True

        def transcribe(self, path, **kwargs):
            captured.update(kwargs)
            return iter([SimpleNamespace(start=2.5, end=4.0, text=' Finish the work tomorrow. ')]), SimpleNamespace(language='hi')

    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=Whisper))
    result = transcription.transcribe(tmp_path / 'audio.wav', 'base', task, source)
    assert captured['task'] == task
    assert captured['language'] == expected_language
    assert result.language == 'hi'
    assert result.output_language == output
    assert result.task == task
    assert result.text == '[00:00:02] Finish the work tomorrow.'
    assert Transcript.model_validate_json(result.model_dump_json()) == result


def test_older_settings_and_transcripts_remain_readable():
    settings = Settings.model_validate({'ollama_model': 'llama3.2:3b', 'whisper_model': 'base'})
    assert settings.transcription_task == 'translate'
    assert settings.source_language == 'auto'
    old = Transcript.model_validate({'language': 'hi', 'segments': [], 'text': ''})
    assert old.task == 'transcribe'


def test_invalid_translation_options():
    with pytest.raises(ValueError):
        Settings(transcription_task='summarize')
    with pytest.raises(ValueError):
        Settings(source_language='invalid')
