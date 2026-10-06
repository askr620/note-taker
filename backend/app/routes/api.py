import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse

from .. import database as db
from ..config import DATA_DIR, MODEL_DIR, OLLAMA_URL
from ..schemas import (DeviceList, MeetingCreate, MeetingResponse, MeetingListResponse, Notes, Settings,
                       SettingsResponse, StartRequest, Transcript)
from ..services.audio import AudioError, list_devices
from ..services.export import export
from ..services.ollama import installed_models
from ..services.storage import resolve

router = APIRouter(prefix='/api')


def service(request: Request):
    return request.app.state.meetings


@router.get('/health')
def health():
    return {'status': 'ok', 'privacy': 'local-only'}


@router.get('/meetings', response_model=list[MeetingListResponse])
def meetings(request: Request, q: str = Query('', max_length=500)):
    service(request).refresh()
    return db.list_meetings(q)


@router.get('/search', response_model=list[MeetingListResponse])
def search(request: Request, q: str = Query('', max_length=500)):
    return meetings(request, q)


@router.post('/meetings', response_model=MeetingResponse, status_code=201)
def create(payload: MeetingCreate):
    return db.create_meeting(payload)


@router.get('/meetings/{meeting_id}', response_model=MeetingResponse)
def get_meeting(meeting_id: str, request: Request):
    return service(request).get(meeting_id)


@router.delete('/meetings/{meeting_id}', status_code=204)
def delete_meeting(meeting_id: str, request: Request):
    service(request).delete(meeting_id)
    return Response(status_code=204)


@router.post('/meetings/{meeting_id}/start', response_model=MeetingResponse)
def start(meeting_id: str, payload: StartRequest, request: Request):
    return service(request).start(meeting_id, payload.device_id)


@router.post('/meetings/{meeting_id}/pause', response_model=MeetingResponse)
def pause(meeting_id: str, request: Request):
    return service(request).pause(meeting_id)


@router.post('/meetings/{meeting_id}/resume', response_model=MeetingResponse)
def resume(meeting_id: str, request: Request):
    return service(request).pause(meeting_id, resume=True)


@router.post('/meetings/{meeting_id}/stop', response_model=MeetingResponse)
def stop(meeting_id: str, request: Request):
    return service(request).stop(meeting_id)


@router.post('/meetings/{meeting_id}/transcribe', response_model=MeetingResponse, status_code=202)
def transcribe(meeting_id: str, request: Request):
    return service(request).process(meeting_id)


@router.post('/meetings/{meeting_id}/generate-notes', response_model=MeetingResponse, status_code=202)
def generate_notes(meeting_id: str, request: Request):
    return service(request).process(meeting_id, notes_only=True)


@router.get('/meetings/{meeting_id}/transcript', response_model=Transcript)
def transcript(meeting_id: str):
    meeting = db.get_meeting(meeting_id)
    if not meeting['transcript_path'] or not resolve(meeting['transcript_path']).is_file():
        raise HTTPException(404, 'Transcript is not available yet.')
    return json.loads(resolve(meeting['transcript_path']).read_text(encoding='utf-8'))


@router.get('/meetings/{meeting_id}/notes', response_model=Notes)
def notes(meeting_id: str):
    meeting = db.get_meeting(meeting_id)
    if meeting['notes'] is None:
        raise HTTPException(404, 'Notes are not available yet.')
    return meeting['notes']


@router.put('/meetings/{meeting_id}/notes', response_model=MeetingResponse)
def save_notes(meeting_id: str, payload: Notes, request: Request):
    return service(request).save_notes(meeting_id, payload)


@router.get('/meetings/{meeting_id}/audio')
def audio(meeting_id: str, request: Request):
    meeting = service(request).get(meeting_id)
    if meeting['status'] in {'recording', 'paused'}:
        raise HTTPException(409, 'Stop recording before playing the audio.')
    if not meeting['audio_path'] or not resolve(meeting['audio_path']).is_file():
        raise HTTPException(404, 'Recording is not available.')
    return FileResponse(resolve(meeting['audio_path']), media_type='audio/wav',
                        filename=f'meetnotes-{meeting_id}.wav')


@router.get('/meetings/{meeting_id}/export')
def export_meeting(meeting_id: str, format: Literal['md', 'txt', 'docx', 'pdf'] = 'md'):
    meeting = db.get_meeting(meeting_id)
    content, mime = export(meeting, format)
    return Response(content, media_type=mime, headers={
        'Content-Disposition': f'attachment; filename="meetnotes-{meeting_id}.{format}"'})


@router.get('/devices', response_model=DeviceList)
def devices():
    try:
        available = list_devices()
        return {'devices': available, 'error': None if available else 'No audio inputs found. Connect a device and refresh.'}
    except AudioError as error:
        return {'devices': [], 'error': str(error)}


@router.get('/settings', response_model=SettingsResponse)
def settings():
    return {**db.get_settings().model_dump(), 'data_location': str(DATA_DIR),
            'model_location': str(MODEL_DIR), 'ollama_url': OLLAMA_URL}


@router.put('/settings', response_model=SettingsResponse)
def update_settings(payload: Settings):
    db.save_settings(payload)
    return settings()


@router.get('/system')
def system():
    try:
        models, error = installed_models(), None
    except Exception as exc:
        models, error = [], str(exc)
    return {'ollama_models': models, 'ollama_error': error,
            'whisper_models': [name for name in ('tiny', 'base', 'small', 'medium')
                               if (MODEL_DIR / name / 'model.bin').is_file()]}
