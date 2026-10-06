"""Opt-in real inference test; it never downloads a model or audio."""
import os
from pathlib import Path

import pytest


@pytest.mark.skipif(not os.getenv('MEETNOTES_TEST_AUDIO'), reason='Set MEETNOTES_TEST_AUDIO to a spoken audio fixture')
def test_real_offline_transcription(monkeypatch):
    monkeypatch.setenv('HF_HUB_OFFLINE', '1')
    from app.services.transcription import transcribe
    result = transcribe(Path(os.environ['MEETNOTES_TEST_AUDIO']), 'base')
    assert result.text.strip()
    assert result.segments
    assert all(segment.end >= segment.start >= 0 for segment in result.segments)
