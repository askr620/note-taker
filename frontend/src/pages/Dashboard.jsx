import { useEffect, useState } from 'react'
import { ArrowRight, ArrowUpRight, AudioLines, CalendarDays, CheckCheck, Clock3, FileText, Plus, Search, X } from 'lucide-react'
import { EmptyState, ErrorBox, Loading, PageHeading, PrivacyNote, Status } from '../components/Common'
import { useResource } from '../hooks/useResource'
import { date } from '../services/api'

export default function Dashboard({ meetings }) {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  useEffect(() => { const timer = setTimeout(() => setSearch(query.trim()), 250); return () => clearTimeout(timer) }, [query])
  const results = useResource(search ? `/search?q=${encodeURIComponent(search)}` : null, search ? 4000 : 0)
  const source = search ? results : meetings
  const all = meetings.data || []
  const items = source.data || []
  const minutes = Math.round(all.reduce((sum, m) => sum + m.duration, 0) / 60)
  const actions = all.reduce((sum, m) => sum + m.action_count, 0)
  return <>
    <PageHeading eyebrow="A CLEARER HEAD STARTS HERE" title="Your meetings, remembered." description="Be in the conversation. We’ll help you keep the important parts." />
    <section className="welcome-panel"><div className="welcome-copy"><span className="pill"><span />LESS NOTE-TAKING. MORE LISTENING.</span><h2>Good conversations.<br /><span>Nothing lost.</span></h2><p>Turn your meetings into clear notes, decisions,<br className="desktop-break" /> and next steps. All on your own device.</p><a className="button primary" href="#/new"><Plus size={17} />Start Meeting<ArrowUpRight size={16} /></a></div><div className="meeting-illustration" aria-hidden="true"><div className="illustration-orbit orbit-one" /><div className="illustration-orbit orbit-two" /><div className="floating-note"><div className="note-top"><span className="note-icon"><AudioLines size={20} /></span><span>Meeting notes<small>A little clarity, captured.</small></span><span className="note-check"><CheckCheck size={16} /></span></div><div className="waveform">{[10,18,30,19,42,27,15,34,48,28,39,18,30,44,25,14,33,19,10].map((h,i) => <i key={i} style={{height:h}} />)}</div><div className="illustration-line wide" /><div className="illustration-line" /><div className="illustration-task"><span>✓</span><i /></div><div className="illustration-task"><span>✓</span><i /></div></div><div className="floating-chip"><span>✦</span>A conversation, made clear</div></div></section>
    <section className="stats-grid" aria-label="Meeting statistics"><Stat icon={CalendarDays} label="Total meetings" value={all.length} detail="All your conversations" /><Stat icon={Clock3} label="Time captured" value={minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`} detail="Space to stay present" /><Stat icon={CheckCheck} label="Action items" value={actions} detail="Next steps, all in one place" /></section>
    <section className="meeting-library"><div className="section-header"><div><h2>{search ? 'Search results' : 'Previous meetings'}<span className="count-tag">{items.length}</span></h2><p>{search ? 'Matching titles, transcripts, notes, and action items.' : 'Pick up right where the conversation left off.'}</p></div><label className="search-input"><Search size={17} /><input aria-label="Search meetings" placeholder="Search your meetings…" value={query} onChange={e => setQuery(e.target.value)} />{query && <button aria-label="Clear search" onClick={() => setQuery('')}><X size={15} /></button>}</label></div>
      <ErrorBox onRetry={source.refresh}>{source.error}</ErrorBox>
      {source.loading && !source.data ? <Loading /> : items.length ? <div className="meeting-grid">{items.map((meeting, index) => <a className="meeting-card" href={`#/meeting/${meeting.id}`} key={meeting.id}><div className="meeting-card-top"><span className={`meeting-icon tone-${index % 3}`}><FileText size={21} strokeWidth={1.6} /></span><Status status={meeting.status} /><ArrowUpRight className="card-arrow" size={17} /></div><h3>{meeting.title}</h3><div className="meeting-meta"><CalendarDays size={13} />{date(meeting.date)}<span>·</span><Clock3 size={13} />{Math.floor(meeting.duration / 60)} min</div><p className="meeting-excerpt">{search && meeting.snippet ? meeting.snippet : meeting.summary || meeting.description || 'Your meeting notes will appear here after recording and local processing.'}</p><div className="meeting-card-footer"><span><CheckCheck size={14} />{meeting.action_count} action items</span><span>{meeting.key_point_count} key points</span></div></a>)}</div> : !source.error && <EmptyState icon={search ? Search : AudioLines} title={search ? 'No meetings found' : 'Your next conversation starts here'} action={!search && <a className="text-link" href="#/new">Record your first meeting <ArrowRight size={16} /></a>}>{search ? 'Try a different word from a title, transcript, or action item.' : 'Start a meeting and let MeetNotes turn what was said into what comes next.'}</EmptyState>}
    </section><PrivacyNote />
  </>
}

function Stat({ icon: Icon, label, value, detail }) {
  return <div className="stat-card"><span className="stat-icon"><Icon size={19} strokeWidth={1.6} /></span><div><p>{label}</p><strong>{value}</strong><small>{detail}</small></div></div>
}
