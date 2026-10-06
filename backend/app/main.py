import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import database
from .config import DATA_DIR, ORIGINS
from .routes.api import router
from .services.audio import AudioError
from .services.jobs import Conflict, MeetingService


@asynccontextmanager
async def lifespan(app):
    (DATA_DIR / 'database').mkdir(parents=True, exist_ok=True)
    lock = open(DATA_DIR / 'database' / 'server.lock', 'a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if lock.tell() == 0:
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        raise RuntimeError('Another MeetNotes backend is using this data directory. Run only one backend worker.')
    try:
        database.initialize()
        app.state.meetings = MeetingService()
        app.state.meetings.recover()
        yield
    finally:
        if hasattr(app.state, 'meetings'):
            app.state.meetings.close()
        lock.close()


app = FastAPI(title='MeetNotes Local API', version='1.0.0', lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])
app.add_middleware(CORSMiddleware, allow_origins=sorted(ORIGINS), allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
                   allow_headers=['Content-Type'], allow_credentials=False)


@app.middleware('http')
async def local_requests_only(request: Request, call_next):
    origin = request.headers.get('origin')
    if (origin and origin not in ORIGINS) or request.headers.get('sec-fetch-site') == 'cross-site':
        return JSONResponse({'detail': 'MeetNotes accepts only local application requests.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response


@app.exception_handler(KeyError)
async def missing(request, error):
    return JSONResponse({'detail': 'Meeting not found.'}, status_code=404)


@app.exception_handler(Conflict)
async def conflict(request, error):
    return JSONResponse({'detail': str(error)}, status_code=409)


@app.exception_handler(AudioError)
async def audio_error(request, error):
    return JSONResponse({'detail': str(error)}, status_code=503)


@app.exception_handler(Exception)
async def unexpected(request, error):
    logging.exception('MeetNotes request failed')
    return JSONResponse({'detail': 'The request failed. Check the backend terminal and available disk space. '
                                   'Existing recordings are preserved.'}, status_code=500)


app.include_router(router)
frontend = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
if frontend.is_dir():
    app.mount('/', StaticFiles(directory=frontend, html=True), name='frontend')
