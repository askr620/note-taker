import { useEffect, useState } from 'react'
import { ArrowRight, FolderOpen, LayoutDashboard, Plus, Settings as SettingsIcon, ShieldCheck } from 'lucide-react'
import { Logo } from './components/Common'
import { useResource } from './hooks/useResource'
import Dashboard from './pages/Dashboard'
import Setup from './pages/Setup'
import Meeting from './pages/Meeting'
import Settings from './pages/Settings'

export default function App() {
  const [route, setRoute] = useState(location.hash.slice(1) || '/')
  const meetings = useResource('/meetings', 4000)
  useEffect(() => {
    const change = () => { setRoute(location.hash.slice(1) || '/'); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  const active = meetings.data?.find(m => ['recording', 'paused'].includes(m.status))
  const path = route.split('?')[0]
  return <div className="app-shell">
    <aside className="sidebar">
      <Logo />
      <div className="workspace-label">PERSONAL WORKSPACE</div>
      <nav aria-label="Main navigation">
        <a className={path === '/' || path.startsWith('/meeting/') ? 'nav-item selected' : 'nav-item'} href="#/"><LayoutDashboard size={18} />Your meetings<span className="nav-count">{meetings.data?.length ?? '—'}</span></a>
        <a className={path === '/settings' ? 'nav-item selected' : 'nav-item'} href="#/settings"><SettingsIcon size={18} />Settings</a>
      </nav>
      <div className="sidebar-bottom"><div className="local-card"><ShieldCheck size={22} /><strong>A little more private.</strong><p>Your conversations stay on this computer, from start to summary.</p><span><i />Local-first workspace</span></div><div className="profile"><span className="avatar">M</span><div><strong>My workspace</strong><small>Personal · Local storage</small></div><FolderOpen size={16} /></div></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb">Workspace <span>/</span> <strong>{path === '/settings' ? 'Settings' : path === '/new' ? 'New meeting' : path.startsWith('/meeting/') ? 'Meeting details' : 'Your meetings'}</strong></div><div className="topbar-actions"><span className="local-label"><i />Local workspace</span><a className="button primary small" href={active ? `#/meeting/${active.id}` : '#/new'}><Plus size={16} />{active ? 'Open recording' : 'Start Meeting'}</a></div></header>
      {active && path !== `/meeting/${active.id}` && <a className="recording-banner" href={`#/meeting/${active.id}`}><span className="recording-dot" />{active.status === 'paused' ? 'Paused' : 'Recording'}: {active.title}<span>Open controls <ArrowRight size={15} /></span></a>}
      <main>
        {path === '/' ? <Dashboard meetings={meetings} /> : path === '/new' ? <Setup key={route} existingId={new URLSearchParams(route.split('?')[1]).get('id')} onChange={meetings.refresh} /> : path === '/settings' ? <Settings /> : path.startsWith('/meeting/') ? <Meeting key={path} id={path.split('/')[2]} onChange={meetings.refresh} /> : <div className="panel"><h1>Page not found</h1><a href="#/">Back to meetings</a></div>}
      </main>
      <footer><span>MeetNotes <span className="footer-separator">/</span> Make room for the conversation.</span><span>Made for your peace of mind <ShieldCheck size={13} /></span></footer>
    </div>
  </div>
}
