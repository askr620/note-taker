"""Audio capture adapter. Add future mixed sources by implementing Recorder."""
import sys
import threading
import wave
from typing import Protocol


class AudioError(RuntimeError):
    pass


class Recorder(Protocol):
    error: str | None
    source_name: str

    @property
    def duration(self) -> float: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def stop(self) -> None: ...


def audio_module():
    if sys.platform != 'win32':
        raise AudioError('System audio capture requires Windows. Run the backend on your Windows PC.')
    try:
        import pyaudiowpatch
        return pyaudiowpatch
    except ImportError as error:
        raise AudioError('Audio capture is unavailable. Install backend requirements, then restart. '
                         'Run python -m pyaudiowpatch to check devices.') from error


def list_devices():
    module = audio_module()
    try:
        with module.PyAudio() as audio:
            host = audio.get_host_api_info_by_type(module.paWASAPI)
            result = []
            for index in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(index)
                if info['hostApi'] != host['index'] or info['maxInputChannels'] < 1:
                    continue
                result.append({'id': index, 'name': info['name'],
                               'kind': 'system' if info.get('isLoopbackDevice') else 'microphone',
                               'sample_rate': int(info['defaultSampleRate']),
                               'channels': int(info['maxInputChannels'])})
            return sorted(result, key=lambda d: (d['kind'] != 'system', d['name']))
    except OSError as error:
        raise AudioError('Windows WASAPI is unavailable. Connect an audio device and refresh sources.') from error


class WasapiRecorder:
    """Bounded-memory PCM capture. Paused frames are discarded, never written."""
    def __init__(self, path, device_id):
        self.error = None
        self.frames = 0
        self.paused = False
        self.lock = threading.Lock()
        self.audio = self.stream = self.wav = self.file = None
        module = audio_module()
        devices = {d['id']: d for d in list_devices()}
        if device_id not in devices:
            raise AudioError('Audio source is no longer available. Refresh sources and select another device.')
        device = devices[device_id]
        self.source_name = device['name']
        self.rate, self.channels = device['sample_rate'], device['channels']
        try:
            self.audio = module.PyAudio()
            self.file = open(path, 'wb')
            self.wav = wave.open(self.file, 'wb')
            self.wav.setnchannels(self.channels)
            self.wav.setsampwidth(2)
            self.wav.setframerate(self.rate)
            self.wav.writeframes(b'')

            def callback(data, frame_count, time_info, status):
                try:
                    with self.lock:
                        if status:
                            raise AudioError('Audio device reported dropped frames. The partial recording was saved. '
                                             'Close other heavy apps and start a new meeting.')
                        if not self.paused:
                            if self.frames * self.channels * 2 + len(data) > 3_500_000_000:
                                raise AudioError('Recording reached the WAV size limit. Start a new meeting to continue.')
                            self.wav.writeframes(data)
                            self.file.flush()  # Keep a valid WAV header throughout capture.
                            self.frames += frame_count
                    return (None, module.paContinue)
                except Exception as error:
                    self.error = f'Audio capture stopped: {error}'
                    return (None, module.paAbort)

            self.stream = self.audio.open(format=module.paInt16, channels=self.channels,
                                          rate=self.rate, input=True, input_device_index=device_id,
                                          frames_per_buffer=2048, stream_callback=callback)
        except Exception as error:
            self.stop()
            raise AudioError(f'Cannot open this audio source: {error}. Refresh sources or select another device.') from error

    @property
    def duration(self):
        return self.frames / self.rate

    def check(self):
        if self.error is None and self.stream and not self.stream.is_active():
            self.error = 'Audio device disconnected or stopped. The partial recording was preserved.'
        return self.error

    def pause(self):
        with self.lock:
            self.paused = True

    def resume(self):
        with self.lock:
            self.paused = False

    def stop(self):
        try:
            if self.stream:
                try:
                    self.stream.stop_stream()
                finally:
                    self.stream.close()
                    self.stream = None
        finally:
            try:
                if self.wav:
                    self.wav.close()
                    self.wav = None
                if self.file:
                    self.file.close()
                    self.file = None
            finally:
                if self.audio:
                    self.audio.terminate()
                    self.audio = None


def audio_duration(path):
    try:
        with wave.open(str(path), 'rb') as source:
            return source.getnframes() / source.getframerate()
    except (OSError, EOFError, wave.Error):
        return 0
