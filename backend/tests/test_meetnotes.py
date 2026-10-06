import io
import json
import sqlite3
import threading
import time
import wave
import zipfile

import pytest
from fastapi.testclient import TestClient

from app import database as db
from app import main
from app.routes import api as routes
from app.schemas import ActionItem, Notes, Segment, Transcript
from app.services import jobs, ollama, storage


@pytest.fixture
def client(tmp_path, monkeypatch):
    for module in (db, main, routes, storage):
        monkeypatch.setattr(module, 'DATA_DIR', tmp_path)
    with TestClient(main.app) as instance:
        yield instance


def create(client, title='API planning'):
    response = client.post('/api/meetings', json={'title': title, 'description': 'Roadmap review'})
    assert response.status_code == 201
    return response.json()['id']


def audio_file(meeting_id):
    relative = f'recordings/{meeting_id}.wav'
    with wave.open(str(storage.resolve(relative)), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\0\0' * 16000)
    db.update_meeting(meeting_id, audio_path=relative, status='recorded', duration=1)
    return storage.resolve(relative)


def wait_for(client, meeting_id, expected):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        meeting = client.get(f'/api/meetings/{meeting_id}').json()
        if meeting['status'] in expected:
            return meeting
        time.sleep(0.01)
    pytest.fail(f'Processing did not reach {expected}; last status: {meeting}')


def transcript_fixture(*args):
    return Transcript(language='en', text='[00:00:00] Priya will build the API by Friday.',
                      segments=[Segment(start=0, end=1, text='Priya will build the API by Friday.')])


def notes_fixture(*args):
    return Notes(summary='The team discussed API delivery.', key_points=['API delivery'],
                 decisions=['Use SQLite'], action_items=[ActionItem(task='Build the API', owner='Priya', deadline='Friday')])


def test_validation_and_local_browser_boundary(client):
    assert client.post('/api/meetings', json={'title': '  '}).status_code == 422
    assert client.post('/api/meetings', json={'title': 'x'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/meetings', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/meetings', headers={'Host': 'evil.example'}).status_code == 400
    assert client.post('/api/meetings', json={'title': 'Allowed'}, headers={'Origin': 'http://localhost:5173'}).status_code == 201
    assert client.get('/api/meetings/missing').status_code == 404


def test_successful_pipeline_search_edit_exports_and_delete(client, monkeypatch):
    monkeypatch.setattr(jobs, 'transcribe', transcript_fixture)
    monkeypatch.setattr(jobs, 'generate_notes', notes_fixture)
    meeting_id = create(client)
    recording = audio_file(meeting_id)
    assert client.post(f'/api/meetings/{meeting_id}/transcribe').status_code == 202
    meeting = wait_for(client, meeting_id, {'completed'})
    assert recording.exists()
    assert meeting['action_count'] == 1
    assert client.get(f'/api/meetings/{meeting_id}/transcript').json()['segments'][0]['start'] == 0
    for query in ['planning', 'Priya', 'SQLite', 'delivery']:
        assert client.get('/api/search', params={'q': query}).json()[0]['id'] == meeting_id
    for query in ['"', '*', 'AND OR', 'x:y', '()']:
        assert client.get('/api/search', params={'q': query}).status_code == 200
    payload = notes_fixture().model_dump()
    payload['action_items'][0]['completed'] = True
    payload['action_items'][0]['task'] = 'Write zebra documentation'
    response = client.put(f'/api/meetings/{meeting_id}/notes', json=payload)
    assert response.status_code == 200
    assert client.get('/api/search?q=zebra').json()[0]['id'] == meeting_id
    with db.connection() as connection:
        assert connection.execute('SELECT completed FROM action_items').fetchone()[0] == 1
        assert connection.execute('SELECT COUNT(*) FROM decisions').fetchone()[0] == 1
    assert '[x] Write zebra' in storage.resolve(meeting['notes_path']).read_text(encoding='utf-8')
    for format in ['md', 'txt', 'pdf', 'docx']:
        response = client.get(f'/api/meetings/{meeting_id}/export?format={format}')
        assert response.status_code == 200
        if format == 'pdf':
            assert response.content.startswith(b'%PDF')
        elif format == 'docx':
            with zipfile.ZipFile(io.BytesIO(response.content)) as document:
                assert b'Transcript' in document.read('word/document.xml')
                assert b'zebra' in document.read('word/document.xml')
        else:
            assert 'Transcript' in response.text and 'zebra' in response.text
    assert client.get(f'/api/meetings/{meeting_id}/audio').content[:4] == b'RIFF'
    assert client.delete(f'/api/meetings/{meeting_id}').status_code == 204
    assert not recording.exists()
    assert client.get('/api/search?q=zebra').json() == []
    with db.connection() as connection:
        assert connection.execute('SELECT COUNT(*) FROM action_items').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM decisions').fetchone()[0] == 0


def test_failures_preserve_recording_and_transcript_and_allow_retry(client, monkeypatch):
    meeting_id = create(client)
    recording = audio_file(meeting_id)
    original = recording.read_bytes()
    def fail(*args):
        raise RuntimeError('Test model unavailable')
    monkeypatch.setattr(jobs, 'transcribe', fail)
    client.post(f'/api/meetings/{meeting_id}/transcribe')
    wait_for(client, meeting_id, {'transcription_failed'})
    assert recording.read_bytes() == original
    monkeypatch.setattr(jobs, 'transcribe', transcript_fixture)
    monkeypatch.setattr(jobs, 'generate_notes', fail)
    client.post(f'/api/meetings/{meeting_id}/transcribe')
    meeting = wait_for(client, meeting_id, {'notes_failed'})
    assert storage.resolve(meeting['transcript_path']).exists()
    assert recording.read_bytes() == original
    monkeypatch.setattr(jobs, 'generate_notes', notes_fixture)
    client.post(f'/api/meetings/{meeting_id}/generate-notes')
    assert wait_for(client, meeting_id, {'completed'})['notes']['summary']


def test_inflight_job_cannot_be_deleted_duplicated_or_edited(client, monkeypatch):
    started, finish = threading.Event(), threading.Event()
    def transcribe(*args):
        started.set()
        assert finish.wait(5)
        return transcript_fixture()
    monkeypatch.setattr(jobs, 'transcribe', transcribe)
    monkeypatch.setattr(jobs, 'generate_notes', notes_fixture)
    meeting_id = create(client)
    audio_file(meeting_id)
    try:
        client.post(f'/api/meetings/{meeting_id}/transcribe')
        assert started.wait(3)
        assert client.delete(f'/api/meetings/{meeting_id}').status_code == 409
        assert client.post(f'/api/meetings/{meeting_id}/transcribe').status_code == 409
        assert client.put(f'/api/meetings/{meeting_id}/notes', json=Notes().model_dump()).status_code == 409
    finally:
        finish.set()
    wait_for(client, meeting_id, {'completed'})


class FakeRecorder:
    def __init__(self, path, device_id):
        self.source_name = 'Test loopback'
        self.duration = 1
        self.error = None
        self.paused = False
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b'\0\0' * 16000)
    def pause(self): self.paused = True
    def resume(self): self.paused = False
    def stop(self): pass
    def check(self): return self.error


def test_recording_state_machine_and_consent(client, monkeypatch):
    monkeypatch.setattr(jobs, 'WasapiRecorder', FakeRecorder)
    monkeypatch.setattr(jobs, 'transcribe', transcript_fixture)
    monkeypatch.setattr(jobs, 'generate_notes', notes_fixture)
    first, second = create(client), create(client)
    start = {'device_id': 1, 'consent_confirmed': True}
    assert client.post(f'/api/meetings/{first}/start', json={'device_id': 1, 'consent_confirmed': False}).status_code == 422
    assert client.post(f'/api/meetings/{first}/start', json=start).json()['status'] == 'recording'
    assert client.post(f'/api/meetings/{second}/start', json=start).status_code == 409
    assert client.get(f'/api/meetings/{first}/audio').status_code == 409
    assert client.post(f'/api/meetings/{first}/resume').status_code == 409
    assert client.post(f'/api/meetings/{first}/pause').json()['status'] == 'paused'
    assert main.app.state.meetings.recorder.paused
    assert client.post(f'/api/meetings/{first}/pause').status_code == 409
    assert client.post(f'/api/meetings/{first}/resume').json()['status'] == 'recording'
    assert not main.app.state.meetings.recorder.paused
    assert client.post(f'/api/meetings/{first}/stop').status_code == 200
    wait_for(client, first, {'completed'})
    assert client.post(f'/api/meetings/{first}/start', json=start).status_code == 409


def test_device_failure_keeps_partial_audio(client, monkeypatch):
    monkeypatch.setattr(jobs, 'WasapiRecorder', FakeRecorder)
    meeting_id = create(client)
    client.post(f'/api/meetings/{meeting_id}/start', json={'device_id': 1, 'consent_confirmed': True})
    main.app.state.meetings.recorder.error = 'Device disconnected'
    meeting = client.get(f'/api/meetings/{meeting_id}').json()
    assert meeting['status'] == 'interrupted'
    assert storage.resolve(meeting['audio_path']).exists()


def test_restart_recovery_preserves_audio(client):
    meeting_id = create(client)
    recording = audio_file(meeting_id)
    db.update_meeting(meeting_id, status='recording', duration=0)
    main.app.state.meetings.recover()
    meeting = client.get(f'/api/meetings/{meeting_id}').json()
    assert meeting['status'] == 'interrupted'
    assert meeting['duration'] == 1
    assert recording.exists()


def test_database_foreign_keys_and_storage_boundaries(client):
    with db.connection() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO decisions(meeting_id,decision) VALUES('missing','bad')")
    with pytest.raises(ValueError):
        storage.resolve('../outside.txt')


def test_settings_validation_and_persistence(client):
    assert client.put('/api/settings', json={'ollama_model': 'llama3.2:1b', 'whisper_model': 'tiny'}).status_code == 200
    assert client.get('/api/settings').json()['whisper_model'] == 'tiny'
    assert client.put('/api/settings', json={'whisper_model': 'imaginary'}).status_code == 422
    assert client.put('/api/settings', json={'data_location': 'C:/outside'}).status_code == 422
    assert client.put('/api/settings', json={'transcription_task': 'translate', 'source_language': 'hi'}).status_code == 200
    saved = client.get('/api/settings').json()
    assert saved['transcription_task'] == 'translate'
    assert saved['source_language'] == 'hi'


def test_missing_whisper_never_downloads(client, tmp_path, monkeypatch):
    from app.services import transcription
    monkeypatch.setattr(transcription, 'MODEL_DIR', tmp_path / 'absent-models')
    with pytest.raises(RuntimeError, match='download_model.py base'):
        transcription.transcribe(tmp_path / 'anything.wav', 'base')


def test_model_grounding_and_unspecified_owner(monkeypatch):
    source = 'We will build the API.'
    extraction = ollama.Extraction(summary=[ollama.Evidence(text='The team discussed the API.', quote=source)],
        key_points=[], decisions=[], open_questions=[], important_dates=[],
        action_items=[ollama.ExtractedAction(task='Build the API', owner='Invented person', deadline='Friday', quote=source)])
    monkeypatch.setattr(ollama, 'ensure_local', lambda model: None)
    monkeypatch.setattr(ollama, 'generate', lambda *args: extraction)
    notes = ollama.generate_notes(source, 'local')
    assert notes.action_items[0].owner == 'Not specified'
    assert notes.action_items[0].deadline == 'Not specified'
    extraction.summary[0].quote = 'Fabricated source sentence'
    with pytest.raises(RuntimeError, match='unsupported'):
        ollama.generate_notes(source, 'local')


def test_remote_models_rejected(monkeypatch):
    monkeypatch.setattr(ollama, 'installed_models', lambda: ['remote-alias:latest'])
    monkeypatch.setattr(ollama, 'request', lambda *args, **kwargs: {'remote_host': 'https://example.com'})
    with pytest.raises(RuntimeError, match='remote service'):
        ollama.ensure_local('remote-alias:latest')
    with pytest.raises(RuntimeError, match='Cloud models'):
        ollama.ensure_local('model:cloud')


def test_long_transcript_is_not_truncated():
    source = '\n'.join(f'line {i}: ' + 'a' * 130 for i in range(1000))
    result = list(ollama.chunks(source))
    assert len(result) > 1
    assert '\n'.join(result) == source
    assert all(len(chunk) <= 5000 for chunk in result)


def test_pcm_capture_discards_paused_frames_and_flushes_valid_wav(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services import audio
    capture = {}
    class Stream:
        def stop_stream(self): pass
        def close(self): pass
        def is_active(self): return True
    class Driver:
        def open(self, **kwargs):
            capture['callback'] = kwargs['stream_callback']
            return Stream()
        def terminate(self): pass
    monkeypatch.setattr(audio, 'audio_module', lambda: SimpleNamespace(
        PyAudio=Driver, paInt16=8, paContinue=0, paAbort=2))
    monkeypatch.setattr(audio, 'list_devices', lambda: [
        {'id': 1, 'name': 'Test', 'sample_rate': 16000, 'channels': 1}])
    path = tmp_path / 'capture.wav'
    recorder = audio.WasapiRecorder(path, 1)
    callback = capture['callback']
    first, paused, last = b'\x01\x00' * 160, b'\x02\x00' * 160, b'\x03\x00' * 160
    callback(first, 160, None, 0)
    recorder.pause()
    callback(paused, 160, None, 0)
    recorder.resume()
    callback(last, 160, None, 0)
    # Read while still capturing: the on-disk header already contains committed frames.
    with wave.open(str(path), 'rb') as wav:
        assert wav.getnframes() == 320
        assert wav.readframes(320) == first + last
    assert recorder.duration == pytest.approx(0.02)
    recorder.stop()


def test_meeting_list_does_not_transfer_entire_transcripts(client):
    meeting_id = create(client)
    db.update_meeting(meeting_id, transcript_text='Private long transcript' * 100)
    item = client.get('/api/meetings').json()[0]
    assert item['id'] == meeting_id
    assert 'transcript_text' not in item and 'notes_json' not in item and 'notes_text' not in item


def test_note_edits_normalize_empty_lines(client):
    meeting_id = create(client)
    audio_file(meeting_id)
    path = f'transcripts/{meeting_id}.json'
    storage.write_json(path, transcript_fixture().model_dump())
    db.update_meeting(meeting_id, transcript_path=path)
    response = client.put(f'/api/meetings/{meeting_id}/notes', json={'key_points': [' one ', '', '  ']})
    assert response.status_code == 200
    assert response.json()['notes']['key_points'] == ['one']
