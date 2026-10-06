import json
import os
import tempfile
from pathlib import Path

from ..config import DATA_DIR


def resolve(relative: str) -> Path:
    path = (DATA_DIR / relative).resolve()
    if not path.is_relative_to(DATA_DIR):
        raise ValueError('Invalid storage path')
    return path


def write_text(relative: str, text: str):
    path = resolve(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically, preserving the previous version on a failed write.
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(relative: str, value):
    write_text(relative, json.dumps(value, ensure_ascii=False, indent=2))


def timestamp(seconds):
    value = max(0, int(seconds))
    return f'{value // 3600:02d}:{value // 60 % 60:02d}:{value % 60:02d}'
