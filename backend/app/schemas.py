from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal['created', 'recording', 'paused', 'recorded', 'transcribing',
                 'generating', 'completed', 'transcription_failed', 'notes_failed', 'interrupted']


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MeetingCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default='', max_length=4000)

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError('Enter a meeting title.')
        return value.strip()


class StartRequest(StrictModel):
    device_id: int = Field(ge=0)
    consent_confirmed: Literal[True]


class Settings(StrictModel):
    ollama_model: str = Field(default='llama3.2:3b', min_length=1, max_length=150, pattern=r'^[\w.\-:/]+$')
    whisper_model: Literal['tiny', 'base', 'small', 'medium'] = 'base'
    transcription_task: Literal['translate', 'transcribe'] = 'translate'
    source_language: Literal['auto', 'hi', 'en'] = 'auto'


class SettingsResponse(Settings):
    data_location: str
    model_location: str
    ollama_url: str


class ActionItem(StrictModel):
    task: str = Field(min_length=1, max_length=4000)
    owner: str = Field(default='Not specified', max_length=500)
    deadline: str = Field(default='Not specified', max_length=500)
    completed: bool = False

    @field_validator('owner', 'deadline')
    @classmethod
    def empty_to_unspecified(cls, value):
        return value.strip() or 'Not specified'


class Notes(StrictModel):
    summary: str = Field(default='', max_length=20000)
    key_points: list[str] = Field(default_factory=list, max_length=2000)
    decisions: list[str] = Field(default_factory=list, max_length=2000)
    action_items: list[ActionItem] = Field(default_factory=list, max_length=2000)
    open_questions: list[str] = Field(default_factory=list, max_length=2000)
    important_dates: list[str] = Field(default_factory=list, max_length=2000)

    @field_validator('key_points', 'decisions', 'open_questions', 'important_dates')
    @classmethod
    def clean_entries(cls, values):
        if any(len(value) > 10000 for value in values):
            raise ValueError('Each note entry must be at most 10,000 characters.')
        return [value.strip() for value in values if value.strip()]


class Segment(StrictModel):
    start: float
    end: float
    text: str


class Transcript(StrictModel):
    language: str
    task: Literal['translate', 'transcribe'] = 'transcribe'
    output_language: str | None = None
    segments: list[Segment]
    text: str


class MeetingResponse(BaseModel):
    id: str
    title: str
    description: str
    date: str
    start_time: str | None
    end_time: str | None
    duration: float
    audio_path: str | None
    transcript_path: str | None
    notes_path: str | None
    status: Status
    created_at: str
    error: str | None
    audio_source: str | None
    notes_text: str
    action_count: int
    key_point_count: int
    notes: Notes | None
    snippet: str | None = None


class MeetingListResponse(BaseModel):
    id: str
    title: str
    description: str
    date: str
    duration: float
    status: Status
    action_count: int
    key_point_count: int
    summary: str
    snippet: str | None = None


class Device(StrictModel):
    id: int
    name: str
    kind: Literal['system', 'microphone']
    sample_rate: int
    channels: int


class DeviceList(StrictModel):
    devices: list[Device]
    error: str | None = None
