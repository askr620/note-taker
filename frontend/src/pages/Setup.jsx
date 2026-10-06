import { useEffect, useState } from 'react'
import { ArrowLeft, AudioLines, Info, Mic, RefreshCw, ShieldCheck } from 'lucide-react'
import { ErrorBox, Loading, PageHeading, PrivacyNote } from '../components/Common'
import { useResource } from '../hooks/useResource'
import { api, post } from '../services/api'

export default function Setup({ existingId, onChange }) {
  const devices = useResource('/devices')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [device, setDevice] = useState('')
  const [consent, setConsent] = useState(false)
  const [meetingId, setMeetingId] = useState(existingId)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    let alive = true
    if (existingId) api(`/meetings/${existingId}`).then(m => {
      if (alive) { setTitle(m.title); setDescription(m.description) }
    }).catch(e => alive && setError(e.message))
    return () => { alive = false }
  }, [existingId])
  useEffect(() => {
    if (devices.data && !devices.data.devices.some(d => String(d.id) === device))
      setDevice(devices.data.devices.length ? String(devices.data.devices[0].id) : '')
  }, [devices.data, device])
  async function start(event) {
    event.preventDefault()
    setBusy(true); setError('')
    try {
      const id = meetingId || (await post('/meetings', { title: title.trim(), description })).id
      setMeetingId(id)
      await post(`/meetings/${id}/start`, { device_id: Number(device), consent_confirmed: consent })
      onChange(); location.hash = `/meeting/${id}`
    } catch (e) { setError(e.message); onChange() }
    finally { setBusy(false) }
  }
  return <><a className="back-link" href="#/"><ArrowLeft size={16} />All meetings</a><PageHeading eyebrow="MAKE SPACE TO LISTEN" title="Start a new meeting" description="Open Google Meet as usual. MeetNotes takes care of what you want to remember." />
    <div className="setup-grid"><form className="panel setup-form" onSubmit={start}><h2>The meeting essentials</h2><p className="muted">A title, an audio source, and you’re ready.</p><label>Meeting title<input required maxLength={200} placeholder="e.g. Weekly project catch-up" value={title} disabled={!!meetingId} onChange={e => setTitle(e.target.value)} /></label><label>Description <span className="optional">optional</span><textarea rows={3} maxLength={4000} placeholder="A little context for your future self…" value={description} disabled={!!meetingId} onChange={e => setDescription(e.target.value)} /></label><div className="label-row"><label htmlFor="audio-source">Audio source</label><button type="button" className="text-link" onClick={devices.refresh} disabled={devices.loading}><RefreshCw size={13} />Refresh</button></div>{devices.loading && !devices.data ? <Loading label="Finding audio devices…" /> : <select id="audio-source" value={device} onChange={e => setDevice(e.target.value)} required><option value="" disabled>Select an audio source</option>{devices.data?.devices.map(d => <option key={d.id} value={d.id}>{d.kind === 'system' ? 'System audio' : 'Microphone'} — {d.name}</option>)}</select>}<ErrorBox>{devices.error || devices.data?.error}</ErrorBox><p className="field-help">For Google Meet, choose the system audio device that matches Meet’s speaker output. Microphone captures only that input.</p><label className="checkbox-label"><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} required /><span>I have obtained any consent required to record and transcribe this meeting.</span></label><ErrorBox>{error}</ErrorBox><div className="form-actions"><a className="button secondary" href="#/">Cancel</a><button className="button primary" disabled={busy || !device || !consent || !title.trim()}><AudioLines size={17} />{busy ? 'Starting recording…' : 'Start Meeting'}</button></div>{meetingId && <p className="field-help">Meeting saved. If capture failed, choose another source and try again.</p>}</form>
    <aside className="setup-aside"><div className="aside-icon"><Mic size={26} /></div><h2>Present in the moment.<br />Prepared for what’s next.</h2><ol className="steps"><li><span>1</span><div><strong>Join your meeting</strong><p>Use Google Meet normally. No login or calendar access needed.</p></div></li><li><span>2</span><div><strong>Capture the conversation</strong><p>Pause or stop anytime. Keep the backend running while you record.</p></div></li><li><span>3</span><div><strong>Leave with clarity</strong><p>Whisper transcribes. Ollama organizes. Everything stays local.</p></div></li></ol><div className="info-note"><Info size={18} /><p>System audio captures other participants and other PC sounds. Your own microphone is a separate source in this MVP.</p></div><a href="#/settings" className="text-link"><ShieldCheck size={15} />Check your local models</a></aside></div><PrivacyNote /></>
}
