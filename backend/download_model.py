"""Explicit, network-enabled setup; never called by meeting processing."""
import argparse
from app.config import MODEL_DIR

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download a faster-whisper model for offline use.')
    parser.add_argument('model', choices=['tiny', 'base', 'small', 'medium'], nargs='?', default='base')
    args = parser.parse_args()
    from faster_whisper.utils import download_model
    target = MODEL_DIR / args.model
    print(f'Downloading {args.model} from Hugging Face to {target}. No meeting data is sent.')
    download_model(args.model, output_dir=str(target))
    print('Model ready for offline transcription.')
