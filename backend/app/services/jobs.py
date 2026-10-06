import threading
from concurrent.futures import ThreadPoolExecutor

from .. import database as db
from .audio import WasapiRecorder, audio_duration
from .notes import notes_markdown
from .ollama import generate_notes
from .storage import resolve, write_json, write_text
from .transcription import transcribe

BUSY = {'recording', 'paused', 'transcribing', 'generating'}


class Conflict(RuntimeError):
    pass


class MeetingService:
    def __init__(self):
        self.lock = threading.RLock()
        self.recorder = None
        self.active_id = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='meetnotes-processing')

    def recover(self):
        for meeting in db.list_meetings():
            if meeting['status'] in BUSY:
                duration = audio_duration(resolve(meeting['audio_path'])) if meeting['audio_path'] else 0
                status = 'notes_failed' if meeting['transcript_path'] else 'interrupted'
                db.update_meeting(meeting['id'], status=status, duration=duration,
                                  end_time=meeting['end_time'] or db.now(),
                                  error='The backend stopped before this meeting finished. Saved files were preserved. '
                                        'Use the retry button to continue processing.')

    def refresh(self):
        with self.lock:
            if self.recorder and self.recorder.check():
                self._stop_capture('interrupted', self.recorder.error)

    def get(self, meeting_id):
        with self.lock:
            self.refresh()
            meeting = db.get_meeting(meeting_id)
            if self.active_id == meeting_id and self.recorder:
                meeting['duration'] = self.recorder.duration
            return meeting

    def start(self, meeting_id, device_id):
        with self.lock:
            self.refresh()
            meeting = db.get_meeting(meeting_id)
            if self.recorder:
                raise Conflict('Another meeting is recording. Stop it before starting a new one.')
            if meeting['status'] != 'created':
                raise Conflict('This meeting has already started. Create a new meeting to record again.')
            path = f'recordings/{meeting_id}.wav'
            self.recorder = WasapiRecorder(resolve(path), device_id)
            self.active_id = meeting_id
            try:
                db.update_meeting(meeting_id, status='recording', start_time=db.now(), audio_path=path,
                                  audio_source=self.recorder.source_name, error=None)
            except Exception:
                self.recorder.stop()
                self.recorder = self.active_id = None
                raise
            return self.get(meeting_id)

    def pause(self, meeting_id, resume=False):
        with self.lock:
            self.refresh()
            meeting = db.get_meeting(meeting_id)
            expected = 'paused' if resume else 'recording'
            if self.active_id != meeting_id or meeting['status'] != expected:
                raise Conflict(f'Only a {expected} meeting can be {"resumed" if resume else "paused"}.')
            (self.recorder.resume if resume else self.recorder.pause)()
            db.update_meeting(meeting_id, status='recording' if resume else 'paused', duration=self.recorder.duration)
            return self.get(meeting_id)

    def _stop_capture(self, status='recorded', error=None):
        recorder, meeting_id = self.recorder, self.active_id
        try:
            recorder.stop()
        except Exception as exc:
            status, error = 'interrupted', f'Audio device stopped unexpectedly: {exc}. Saved audio was preserved.'
        finally:
            duration = recorder.duration
            self.recorder = self.active_id = None
            db.update_meeting(meeting_id, status=status, error=error, end_time=db.now(), duration=duration)

    def stop(self, meeting_id):
        with self.lock:
            self.refresh()
            if self.active_id != meeting_id:
                raise Conflict('This meeting is no longer recording. Use Retry Transcription for a saved recording.')
            self._stop_capture()
            if db.get_meeting(meeting_id)['status'] == 'recorded':
                self.process(meeting_id)
            return self.get(meeting_id)

    def process(self, meeting_id, notes_only=False):
        with self.lock:
            meeting = db.get_meeting(meeting_id)
            allowed = {'notes_failed', 'completed'} if notes_only else {'recorded', 'interrupted', 'transcription_failed'}
            if meeting['status'] not in allowed:
                raise Conflict('This meeting cannot be processed in its current state.')
            field = 'transcript_path' if notes_only else 'audio_path'
            if not meeting[field] or not resolve(meeting[field]).is_file():
                raise Conflict('The saved input file is missing. Check the data folder or restore your backup.')
            settings = db.get_settings()
            db.update_meeting(meeting_id, status='generating' if notes_only else 'transcribing', error=None)
            self.executor.submit(self._process, meeting_id, settings, notes_only)
            return self.get(meeting_id)

    def _process(self, meeting_id, settings, notes_only):
        stage = 'notes_failed' if notes_only else 'transcription_failed'
        try:
            meeting = db.get_meeting(meeting_id)
            if not notes_only:
                transcript = transcribe(resolve(meeting['audio_path']), settings.whisper_model,
                                        settings.transcription_task, settings.source_language)
                path = f'transcripts/{meeting_id}.json'
                write_json(path, transcript.model_dump())
                write_text(f'transcripts/{meeting_id}.txt', transcript.text)
                db.update_meeting(meeting_id, transcript_path=path, transcript_text=transcript.text, status='generating')
                stage = 'notes_failed'
                meeting = db.get_meeting(meeting_id)
            notes = generate_notes(meeting['transcript_text'], settings.ollama_model)
            self.save_notes(meeting_id, notes, processing=True)
        except Exception as error:
            db.update_meeting(meeting_id, status=stage, error=str(error)[:3000] or 'Processing failed. Please retry.')

    def save_notes(self, meeting_id, notes, processing=False):
        with self.lock:
            meeting = db.get_meeting(meeting_id)
            if not processing and (meeting['status'] in BUSY or not meeting['transcript_path']):
                raise Conflict('Wait for processing to finish before editing notes.')
            markdown = notes_markdown(notes)
            path = f'notes/{meeting_id}.md'
            write_text(path, markdown)
            write_json(f'notes/{meeting_id}.json', notes.model_dump())
            db.save_notes(meeting_id, notes, markdown, path)
            return self.get(meeting_id)

    def delete(self, meeting_id):
        with self.lock:
            meeting = self.get(meeting_id)
            if meeting['status'] in BUSY:
                raise Conflict('Stop recording and wait for processing to finish before deleting this meeting.')
            for path in [meeting['audio_path'], meeting['transcript_path'], meeting['notes_path'],
                         f'transcripts/{meeting_id}.txt', f'notes/{meeting_id}.json']:
                if path:
                    resolve(path).unlink(missing_ok=True)
            db.delete_meeting(meeting_id)

    def close(self):
        with self.lock:
            if self.recorder:
                self._stop_capture('interrupted', 'The backend closed. Retry transcription to process the saved recording.')
        self.executor.shutdown(wait=True)
