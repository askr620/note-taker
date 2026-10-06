import { AlertCircle, ArrowUpRight, AudioLines, Check, LoaderCircle, ShieldCheck } from 'lucide-react'

export function Logo() {
  return <a className="brand" href="#/"><span className="brand-mark"><AudioLines size={23} /></span>MeetNotes<span className="brand-dot">.</span></a>
}

export function ErrorBox({ children, onRetry }) {
  if (!children) return null
  return <div className="error-box" role="alert"><AlertCircle size={19} /><div>{children}</div>{onRetry && <button onClick={onRetry}>Retry</button>}</div>
}

export function Loading({ label = 'Loading your workspace…' }) {
  return <div className="loading" role="status"><LoaderCircle className="spin" size={22} />{label}</div>
}

const labels = { created: 'Not started', recording: 'Recording', paused: 'Paused', recorded: 'Recorded',
  transcribing: 'Transcribing', generating: 'Writing notes', completed: 'Ready',
  transcription_failed: 'Needs transcription', notes_failed: 'Needs summary', interrupted: 'Interrupted' }

export function Status({ status }) {
  return <span className={`status status-${status}`}>{status === 'completed' ? <Check size={12} /> : <span className="status-dot" />}{labels[status] || status}</span>
}

export function PrivacyNote() {
  return <div className="privacy-note"><ShieldCheck size={16} /><span>Stored on your device. Processed locally. Always yours.</span></div>
}

export function EmptyState({ icon: Icon = AudioLines, title, children, action }) {
  return <div className="empty-state"><div className="empty-icon"><Icon size={30} strokeWidth={1.4} /></div><h3>{title}</h3><p>{children}</p>{action}</div>
}

export function PageHeading({ eyebrow, title, description, children }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{children}</div>
}

export function SectionList({ title, items = [] }) {
  return <section className="notes-section"><h3>{title}</h3>{items.length ? <ul>{items.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="muted">None recorded.</p>}</section>
}
