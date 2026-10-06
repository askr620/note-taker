import { useEffect, useState } from 'react'
import { ArrowLeft, CalendarDays, CheckCheck, Clock3, Copy, Download, FileText, Pause, Pencil, Play, Plus, RefreshCw, Search, Square, Trash2, X } from 'lucide-react'
import { EmptyState, ErrorBox, Loading, PageHeading, SectionList, Status } from '../components/Common'
import { useResource } from '../hooks/useResource'
import { api, busyStatuses, date, downloadMeeting, post, put, time } from '../services/api'

const EMPTY_NOTES = { summary: '', key_points: [], decisions: [], action_items: [], open_questions: [], important_dates: [] }

export default function Meeting({ id, onChange }) {
  const resource = useResource(`/meetings/${id}`, 2000)
  const meeting = resource.data
  const transcript = useResource(meeting?.transcript_path ? `/meetings/${id}/transcript` : null)
  const [tab, setTab] = useState('overview')
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [draft, setDraft] = useState(null)
  const [format, setFormat] = useState('md')
  useEffect(() => {
    if (!draft) return
    const warn = event => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [draft])
  async function act(task, message = '') {
    setBusy(true); setError(''); setNotice('')
    try { await task(); resource.refresh(); onChange(); setNotice(message) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }
  const command = endpoint => act(() => post(`/meetings/${id}/${endpoint}`))
  if (!meeting) return resource.error ? <ErrorBox onRetry={resource.refresh}>{resource.error}</ErrorBox> : <Loading />
  const recording = ['recording', 'paused'].includes(meeting.status)
  const processing = ['transcribing', 'generating'].includes(meeting.status)
  const notes = meeting.notes
  const locked = busy || busyStatuses.includes(meeting.status)
  const filtered = transcript.data?.segments.filter(segment => segment.text.toLocaleLowerCase().includes(query.toLocaleLowerCase())) || []
  const changeTab = next => {
    if (draft && !window.confirm('Discard unsaved note edits?')) return
    setDraft(null); setTab(next)
  }
  return <><a className="back-link" href="#/"><ArrowLeft size={16} />All meetings</a>
    <PageHeading eyebrow="THE CONVERSATION, CAPTURED" title={meeting.title}><Status status={meeting.status} /></PageHeading>
    <div className="detail-meta"><span><CalendarDays size={15} />{date(meeting.date)}</span><span><Clock3 size={15} />{time(meeting.duration)} recorded</span>{meeting.audio_source && <span className="source-name">{meeting.audio_source}</span>}</div>
    {meeting.description && <p className="detail-description">{meeting.description}</p>}
    <ErrorBox onRetry={resource.refresh}>{resource.error}</ErrorBox><ErrorBox>{error || meeting.error}</ErrorBox>
    {notice && <div className="success-note" role="status">{notice}</div>}
    {recording && <div className={`recording-panel ${meeting.status === 'paused' ? 'is-paused' : ''}`}><div><span className="recording-label"><i />{meeting.status === 'paused' ? 'Recording paused' : 'Recording in progress'}</span><strong className="timer">{time(meeting.duration)}</strong><p>{meeting.status === 'paused' ? 'Paused audio is not saved. Resume when you’re ready.' : 'Audio is being saved on this computer. Keep the backend running.'}</p></div><div className="recording-actions"><button className="button secondary" disabled={busy} onClick={() => command(meeting.status === 'paused' ? 'resume' : 'pause')}>{meeting.status === 'paused' ? <Play size={16} /> : <Pause size={16} />}{meeting.status === 'paused' ? 'Resume' : 'Pause'}</button><button className="button danger" disabled={busy} onClick={() => command('stop')}><Square size={14} fill="currentColor" />Stop Meeting</button></div></div>}
    {processing && <div className="processing-panel"><Loading label={meeting.status === 'transcribing' ? 'Transcribing locally with Whisper…' : 'Writing your notes with local Ollama…'} /><p>Your recording is saved. Processing time depends on meeting length and your PC. You can leave this page; keep the backend running.</p></div>}
    {['recorded', 'interrupted', 'transcription_failed'].includes(meeting.status) && meeting.audio_path && <button className="button secondary retry-button" disabled={busy} onClick={() => command('transcribe')}><RefreshCw size={16} />Retry Transcription</button>}
    {meeting.status === 'notes_failed' && <button className="button secondary retry-button" disabled={busy} onClick={() => command('generate-notes')}><RefreshCw size={16} />Retry AI Summary</button>}
    {meeting.status === 'created' && <div className="panel draft-panel"><p>This meeting is saved and ready to record.</p><a className="button primary" href={`#/new?id=${id}`}><Play size={16} />Choose audio & start</a></div>}
    <div className="details-toolbar"><div className="tabs" role="tablist" aria-label="Meeting details">{['overview', 'notes', 'transcript'].map(value => <button role="tab" aria-selected={tab === value} aria-controls="meeting-tabpanel" id={`tab-${value}`} className={tab === value ? 'active' : ''} key={value} onClick={() => changeTab(value)}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div><div className="export-controls"><select aria-label="Export format" value={format} onChange={e => setFormat(e.target.value)}><option value="md">Markdown</option><option value="txt">Text</option><option value="docx">Word</option><option value="pdf">PDF</option></select><button className="button secondary small" disabled={busy || !meeting.transcript_path || !!draft} onClick={() => act(() => downloadMeeting(id, format))}><Download size={15} />Export</button></div></div>
    <div id="meeting-tabpanel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
    {tab === 'overview' && (notes ? <div className="overview-grid"><div className="panel document"><div className="document-eyebrow"><FileText size={16} />THE BIG PICTURE</div><section className="notes-section summary-section"><h2>Meeting summary</h2><p>{notes.summary || 'No summary recorded.'}</p></section><SectionList title="Key discussion points" items={notes.key_points} /><SectionList title="Decisions" items={notes.decisions} /><SectionList title="Open questions" items={notes.open_questions} /><SectionList title="Important dates" items={notes.important_dates} /></div><div className="panel action-panel"><h2><CheckCheck size={20} />Next steps<span className="count-tag">{notes.action_items.length}</span></h2><p className="muted">A little momentum for what’s next.</p>{notes.action_items.length ? notes.action_items.map((item, index) => <label className={`action-item ${item.completed ? 'completed' : ''}`} key={index}><input type="checkbox" checked={item.completed} disabled={locked} onChange={() => act(() => put(`/meetings/${id}/notes`, { ...notes, action_items: notes.action_items.map((a, i) => i === index ? { ...a, completed: !a.completed } : a) }))} /><div><strong>{item.task}</strong><small>Owner: {item.owner}</small><small>Deadline: {item.deadline}</small></div></label>) : <p className="muted">No action items identified.</p>}</div></div> : <EmptyState title="Clarity is on its way">{processing ? 'Your notes will appear when local processing is complete.' : 'Record and process this meeting to see its summary, decisions, and next steps.'}</EmptyState>)}
    {tab === 'notes' && <div className="panel document"><div className="document-toolbar"><h2>Meeting notes</h2><div className="inline-actions">{!draft && <><button className="button secondary small" disabled={locked || !meeting.transcript_path} onClick={() => setDraft(structuredClone(notes || EMPTY_NOTES))}><Pencil size={14} />Edit</button><button className="button secondary small" disabled={!notes || busy} onClick={() => act(() => navigator.clipboard.writeText(meeting.notes_text), 'Notes copied to clipboard.')}><Copy size={14} />Copy</button>{notes && <button className="icon-button" title="Regenerate notes" aria-label="Regenerate notes" disabled={locked} onClick={() => { if (window.confirm('Regenerate notes? This will replace your edits and completed action items after successful generation.')) command('generate-notes') }}><RefreshCw size={15} /></button>}</>}</div></div>{draft ? <NotesEditor draft={draft} setDraft={setDraft} busy={busy} onCancel={() => setDraft(null)} onSave={() => act(async () => { await put(`/meetings/${id}/notes`, draft); setDraft(null) }, 'Notes saved locally.')} /> : notes ? <><section className="notes-section"><h3>Summary</h3><p>{notes.summary}</p></section><SectionList title="Key discussion points" items={notes.key_points} /><SectionList title="Decisions" items={notes.decisions} /><section className="notes-section"><h3>Action items</h3>{notes.action_items.length ? notes.action_items.map((a,i) => <div className="document-action" key={i}><strong>{a.completed ? '✓ ' : ''}{a.task}</strong><p>Owner: {a.owner}<br />Deadline: {a.deadline}</p></div>) : <p className="muted">None recorded.</p>}</section><SectionList title="Open questions" items={notes.open_questions} /><SectionList title="Important dates" items={notes.important_dates} /><p className="ai-note">Generated locally from your transcript. Review names, decisions, and dates before relying on them.</p></> : <EmptyState title="No notes yet">After transcription, generate an AI summary or use Edit to write your own notes.</EmptyState>}</div>}
    {tab === 'transcript' && <div className="panel document"><div className="document-toolbar"><div><h2>Full transcript</h2>{transcript.data && <p className="muted">{transcript.data.task === 'translate' ? 'Translated to English' : 'Original-language transcript'} · Detected speech: {transcript.data.language}</p>}<p className="muted">Timestamps refer to recorded audio, excluding pauses. Speakers are not identified.</p></div></div>{meeting.audio_path && !recording && <audio className="audio-player" controls preload="none" src={`/api/meetings/${id}/audio`}>Your browser does not support audio playback.</audio>}<label className="search-input transcript-search"><Search size={17} /><input aria-label="Search transcript" value={query} onChange={e => setQuery(e.target.value)} placeholder="Find something in the conversation…" /></label><ErrorBox onRetry={transcript.refresh}>{transcript.error}</ErrorBox>{!meeting.transcript_path ? <EmptyState title="No transcript yet">Your timestamped transcript appears after Whisper finishes processing.</EmptyState> : transcript.loading && !transcript.data ? <Loading /> : filtered.length ? <div className="transcript-lines">{filtered.map((segment, i) => <div className="transcript-line" key={i}><time>{time(segment.start)}</time><p>{segment.text}</p></div>)}</div> : <p className="muted">No transcript lines match your search.</p>}</div>}
    </div>
    <div className="detail-bottom"><span>Saved locally · Private by default</span><button className="text-link delete-link" disabled={locked || !!draft} onClick={() => { if (window.confirm('Permanently delete this meeting, its recording, transcript, and notes? This cannot be undone.')) act(async () => { await api(`/meetings/${id}`, { method: 'DELETE' }); location.hash = '/' }) }}><Trash2 size={14} />Delete meeting</button></div>
  </>
}

function NotesEditor({ draft, setDraft, onSave, onCancel, busy }) {
  const update = (key, value) => setDraft({ ...draft, [key]: value })
  const actionUpdate = (index, key, value) => update('action_items', draft.action_items.map((a,i) => i === index ? { ...a, [key]: value } : a))
  return <form className="notes-editor" onSubmit={e => { e.preventDefault(); onSave() }}><label>Summary<textarea rows={5} maxLength={20000} value={draft.summary} onChange={e => update('summary', e.target.value)} /></label>{[['key_points','Key discussion points'],['decisions','Decisions'],['open_questions','Open questions'],['important_dates','Important dates']].map(([key, label]) => <label key={key}>{label}<span className="field-help">One item per line.</span><textarea rows={3} value={draft[key].join('\n')} onChange={e => update(key, e.target.value.split('\n'))} /></label>)}<h3>Action items</h3>{draft.action_items.map((a,i) => <div className="action-editor" key={i}><label>Task<input required maxLength={4000} value={a.task} onChange={e => actionUpdate(i, 'task', e.target.value)} /></label><div className="two-columns"><label>Owner<input maxLength={500} value={a.owner} onChange={e => actionUpdate(i, 'owner', e.target.value)} /></label><label>Deadline<input maxLength={500} value={a.deadline} onChange={e => actionUpdate(i, 'deadline', e.target.value)} /></label></div><button className="text-link delete-link" type="button" onClick={() => update('action_items', draft.action_items.filter((_, index) => i !== index))}><X size={14} />Remove action</button></div>)}<button type="button" className="button secondary small" onClick={() => update('action_items', [...draft.action_items, {task:'', owner:'Not specified', deadline:'Not specified', completed:false}])}><Plus size={14} />Add action item</button><div className="form-actions"><button type="button" className="button secondary" disabled={busy} onClick={onCancel}>Cancel</button><button className="button primary" disabled={busy}>{busy ? 'Saving…' : 'Save notes'}</button></div></form>
}
