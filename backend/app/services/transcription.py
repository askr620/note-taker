from ..config import MODEL_DIR
from ..schemas import Segment, Transcript
from .storage import timestamp


def transcribe(path, model_name: str, task: str = 'transcribe', source_language: str = 'auto') -> Transcript:
    if task not in {'translate', 'transcribe'} or source_language not in {'auto', 'hi', 'en'}:
        raise ValueError('Unsupported transcription task or source language.')
    model_path = MODEL_DIR / model_name
    if not (model_path / 'model.bin').is_file():
        raise RuntimeError(f'Whisper model "{model_name}" is not installed. In backend, run '
                           f'python download_model.py {model_name}, then retry transcription. '
                           'Only this explicit setup command downloads model files.')
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise RuntimeError('faster-whisper is unavailable. Install backend requirements and restart.') from error
    model = WhisperModel(str(model_path), device='cpu', compute_type='int8', local_files_only=True)
    segments, info = model.transcribe(str(path), beam_size=5, vad_filter=True,
                                      task=task, language=None if source_language == 'auto' else source_language,
                                      condition_on_previous_text=False)
    result = [Segment(start=s.start, end=s.end, text=s.text.strip()) for s in segments if s.text.strip()]
    if not result:
        raise RuntimeError('No speech was detected. Listen to the saved recording and check the selected '
                           'audio source. You can retry with another Whisper model in Settings.')
    return Transcript(language=info.language, task=task,
                      output_language='en' if task == 'translate' else info.language, segments=result,
                      text='\n'.join(f'[{timestamp(s.start)}] {s.text}' for s in result))
