import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parents[1]
load_dotenv(BASE / '.env')


def configured_path(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default)).expanduser()
    return (value if value.is_absolute() else BASE / value).resolve()


DATA_DIR = configured_path('MEETNOTES_DATA_DIR', '../data')
MODEL_DIR = configured_path('MEETNOTES_MODEL_DIR', './models')
OLLAMA_URL = os.getenv('MEETNOTES_OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
parsed = urlsplit(OLLAMA_URL)
if (parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
        or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
    raise ValueError('MEETNOTES_OLLAMA_URL must be an HTTP loopback address, e.g. http://127.0.0.1:11434')

ORIGINS = {'http://localhost:5173', 'http://127.0.0.1:5173',
           'http://localhost:8000', 'http://127.0.0.1:8000'}
