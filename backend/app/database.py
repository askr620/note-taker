import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from .config import DATA_DIR
from .schemas import Notes, Settings


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    db = sqlite3.connect(DATA_DIR / 'database' / 'meetnotes.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    for folder in ('recordings', 'transcripts', 'notes', 'database'):
        (DATA_DIR / folder).mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS meetings (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
            date TEXT NOT NULL, start_time TEXT, end_time TEXT, duration REAL NOT NULL DEFAULT 0,
            audio_path TEXT, transcript_path TEXT, notes_path TEXT,
            status TEXT NOT NULL DEFAULT 'created', created_at TEXT NOT NULL,
            error TEXT, audio_source TEXT, transcript_text TEXT NOT NULL DEFAULT '',
            notes_json TEXT, notes_text TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY, meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
            task TEXT NOT NULL, owner TEXT NOT NULL, deadline TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1))
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY, meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
            decision TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
        CREATE VIRTUAL TABLE IF NOT EXISTS meeting_search USING fts5(
            meeting_id UNINDEXED, title, transcript, notes, actions, tokenize='unicode61'
        );
        ''')
        db.execute('INSERT OR IGNORE INTO settings VALUES(1, ?)', (Settings().model_dump_json(),))


def get_settings():
    with connection() as db:
        return Settings.model_validate_json(db.execute('SELECT value FROM settings WHERE id=1').fetchone()[0])


def save_settings(settings):
    with connection() as db:
        db.execute('UPDATE settings SET value=? WHERE id=1', (settings.model_dump_json(),))


def index_meeting(db, meeting_id):
    row = db.execute('SELECT * FROM meetings WHERE id=?', (meeting_id,)).fetchone()
    actions = db.execute('SELECT task,owner,deadline FROM action_items WHERE meeting_id=?', (meeting_id,)).fetchall()
    db.execute('DELETE FROM meeting_search WHERE meeting_id=?', (meeting_id,))
    db.execute('INSERT INTO meeting_search VALUES(?,?,?,?,?)', (
        meeting_id, row['title'], row['transcript_text'], row['notes_text'],
        ' '.join(' '.join(a) for a in actions)))


def create_meeting(payload):
    meeting_id, date = str(uuid4()), now()
    with connection() as db:
        db.execute('INSERT INTO meetings(id,title,description,date,created_at) VALUES(?,?,?,?,?)',
                   (meeting_id, payload.title, payload.description, date, date))
        index_meeting(db, meeting_id)
    return get_meeting(meeting_id)


def serialize(row):
    value = dict(row)
    notes = json.loads(value['notes_json']) if value['notes_json'] else None
    value.update(notes=notes, action_count=len(notes['action_items']) if notes else 0,
                 key_point_count=len(notes['key_points']) if notes else 0,
                 summary=notes['summary'] if notes else '')
    return value


def get_meeting(meeting_id):
    with connection() as db:
        row = db.execute('SELECT * FROM meetings WHERE id=?', (meeting_id,)).fetchone()
    if row is None:
        raise KeyError('Meeting not found.')
    return serialize(row)


def list_meetings(query=''):
    with connection() as db:
        if query.strip():
            # Quote user terms: FTS operators, quotes and punctuation are never executed as syntax.
            tokens = query.split()[:30]
            expression = ' AND '.join('"' + token.replace('"', '""') + '"' for token in tokens)
            rows = db.execute('''SELECT m.*, snippet(meeting_search, -1, '', '', ' … ', 24) AS snippet
                FROM meeting_search JOIN meetings m ON m.id=meeting_search.meeting_id
                WHERE meeting_search MATCH ? ORDER BY rank, m.created_at DESC''', (expression,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM meetings ORDER BY created_at DESC').fetchall()
    return [serialize(row) for row in rows]


def update_meeting(meeting_id, **values):
    allowed = {'start_time', 'end_time', 'duration', 'audio_path', 'transcript_path', 'notes_path',
               'status', 'error', 'audio_source', 'transcript_text'}
    if not values or not values.keys() <= allowed:
        raise ValueError('Invalid meeting update')
    with connection() as db:
        db.execute('UPDATE meetings SET ' + ','.join(f'{key}=?' for key in values) + ' WHERE id=?',
                   (*values.values(), meeting_id))
        if 'transcript_text' in values:
            index_meeting(db, meeting_id)


def save_notes(meeting_id: str, notes: Notes, markdown: str, path: str):
    with connection() as db:
        db.execute('UPDATE meetings SET notes_json=?,notes_text=?,notes_path=?,status=?,error=NULL WHERE id=?',
                   (notes.model_dump_json(), markdown, path, 'completed', meeting_id))
        db.execute('DELETE FROM action_items WHERE meeting_id=?', (meeting_id,))
        db.execute('DELETE FROM decisions WHERE meeting_id=?', (meeting_id,))
        db.executemany('INSERT INTO action_items(meeting_id,task,owner,deadline,completed) VALUES(?,?,?,?,?)',
                       [(meeting_id, a.task, a.owner, a.deadline, int(a.completed)) for a in notes.action_items])
        db.executemany('INSERT INTO decisions(meeting_id,decision) VALUES(?,?)',
                       [(meeting_id, d) for d in notes.decisions])
        index_meeting(db, meeting_id)


def delete_meeting(meeting_id):
    with connection() as db:
        db.execute('DELETE FROM meeting_search WHERE meeting_id=?', (meeting_id,))
        db.execute('DELETE FROM meetings WHERE id=?', (meeting_id,))
