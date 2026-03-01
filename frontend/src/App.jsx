import { useState, useEffect, useRef } from 'react'
import './App.css'

const API = 'http://localhost:5001/api'

function parseSection(content, heading) {
  const regex = new RegExp(`### ${heading}\\n([\\s\\S]*?)(?=###|$)`)
  const match = content.match(regex)
  if (!match) return []
  return match[1]
    .split('\n')
    .map(l => l.replace(/^[-*\d.]\s*/, '').replace(/\*\*(.*?)\*\*/g, '$1').trim())
    .filter(Boolean)
}

function parseCodeSnippet(content) {
  const match = content.match(/```[\w]*\n([\s\S]*?)```/)
  return match ? match[1].trim() : null
}

function Section({ title, children }) {
  return (
    <div className="section">
      <p className="section-label">{title}</p>
      {children}
    </div>
  )
}

function SnapshotCard({ snapshot, index, isNew }) {
  const [open, setOpen] = useState(true)
  const concepts = parseSection(snapshot.content, 'Key Concepts')
  const definitions = parseSection(snapshot.content, 'Important Definitions')
  const summary = parseSection(snapshot.content, 'Summary')
  const questions = parseSection(snapshot.content, 'Study Questions')
  const code = parseCodeSnippet(snapshot.content)

  return (
    <div className={`card ${isNew ? 'card-new' : ''}`}>
      <button className="card-toggle" onClick={() => setOpen(!open)}>
        <div className="card-left">
          <span className="card-num">#{index + 1}</span>
          <span className="card-preview">{concepts[0] || 'Captured snapshot'}</span>
        </div>
        <span className="toggle-icon">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="card-body">
          {concepts.length > 0 && (
            <Section title="Key Concepts">
              <ul className="bullet-list">
                {concepts.map((c, i) => <li key={i}>{c}</li>)}
              </ul>
            </Section>
          )}
          {definitions.length > 0 && (
            <Section title="Definitions">
              {definitions.map((d, i) => {
                const idx = d.indexOf(':')
                const term = idx > -1 ? d.slice(0, idx).trim() : d
                const body = idx > -1 ? d.slice(idx + 1).trim() : ''
                return (
                  <div key={i} className="def-row">
                    <span className="def-term">{term}</span>
                    {body && <span className="def-body">{body}</span>}
                  </div>
                )
              })}
            </Section>
          )}
          {code && (
            <Section title="Code">
              <pre className="code-block"><code>{code}</code></pre>
            </Section>
          )}
          {summary.length > 0 && (
            <Section title="Summary">
              <p className="summary-text">{summary.join(' ')}</p>
            </Section>
          )}
          {questions.length > 0 && (
            <Section title="Study Questions">
              <ol className="numbered-list">
                {questions.map((q, i) => <li key={i}>{q}</li>)}
              </ol>
            </Section>
          )}
        </div>
      )}
    </div>
  )
}

function formatFilename(fname) {
  if (!fname) return ''
  const base = fname.replace('.md', '')
  // Expected format: TopicName_2026-02-28_20-05-38
  const dateMatch = base.match(/^(.+?)_(\d{4}-\d{2}-\d{2})/)
  if (dateMatch) {
    const topic = dateMatch[1].replace(/([A-Z])/g, ' $1').trim()
    const d = new Date(dateMatch[2])
    const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    return { topic, date: dateStr }
  }
  return { topic: base, date: '' }
}

export default function App() {
  const [snapshots, setSnapshots] = useState([])
  const [filename, setFilename] = useState(null)
  const [sessions, setSessions] = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [view, setView] = useState('live')
  const [isLive, setIsLive] = useState(false)
  const [newIndex, setNewIndex] = useState(null)
  const prevCountRef = useRef(0)
  const bottomRef = useRef()

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`${API}/latest`)
        if (!res.ok) { setIsLive(false); return }
        const data = await res.json()
        setFilename(data.filename)
        setIsLive(true)
        if (data.count > prevCountRef.current) {
          setNewIndex(data.count - 1)
          setTimeout(() => setNewIndex(null), 4000)
        }
        prevCountRef.current = data.count
        setSnapshots(data.snapshots || [])
      } catch { setIsLive(false) }
    }
    poll()
    const t = setInterval(poll, 8000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (newIndex !== null) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [newIndex])

  useEffect(() => {
    if (view !== 'sessions') return
    fetch(`${API}/sessions`).then(r => r.json()).then(setSessions).catch(() => {})
  }, [view])

  const loadSession = async (fname) => {
    const res = await fetch(`${API}/notes/${fname}`)
    const data = await res.json()
    setActiveSession(data)
  }

  const { topic, date } = filename ? formatFilename(filename) : { topic: '', date: '' }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <svg className="brand-eye" width="20" height="20" viewBox="0 0 20 20" fill="none">
            <ellipse cx="10" cy="10" rx="9" ry="5.5" stroke="currentColor" strokeWidth="1.5"/>
            <circle cx="10" cy="10" r="2.5" fill="currentColor"/>
          </svg>
          SightNotes
        </div>
        <nav className="nav">
          <button className={`nav-btn ${view === 'live' ? 'active' : ''}`} onClick={() => setView('live')}>Live</button>
          <button className={`nav-btn ${view === 'sessions' ? 'active' : ''}`} onClick={() => { setView('sessions'); setActiveSession(null) }}>Sessions</button>
        </nav>
        <div className="status">
          <span className={`dot ${isLive ? 'dot-live' : ''}`} />
          {isLive ? 'Live' : 'Idle'}
        </div>
      </header>

      <main className="main">

        {/* LIVE VIEW */}
        {view === 'live' && snapshots.length === 0 && (
          <div className="empty">
            <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
              <ellipse cx="22" cy="22" rx="20" ry="12" stroke="#64748b" strokeWidth="1.5"/>
              <circle cx="22" cy="22" r="5" stroke="#64748b" strokeWidth="1.5"/>
              <circle cx="22" cy="22" r="2" fill="#64748b"/>
            </svg>
            <h2>Waiting for lecture</h2>
            <p>Run <code>python main.py run</code>, join the call and share your screen.</p>
          </div>
        )}

        {view === 'live' && snapshots.length > 0 && (
          <div className="notes-container">
            <div className="notes-title-row">
              <div>
                <h1 className="notes-topic">{topic}</h1>
                {date && <p className="notes-date">{date}</p>}
              </div>
              <span className="count-badge">{snapshots.length} snapshots</span>
            </div>
            <div className="cards">
              {snapshots.map((snap, i) => (
                <SnapshotCard key={i} snapshot={snap} index={i} isNew={i === newIndex} />
              ))}
              <div ref={bottomRef} />
            </div>
          </div>
        )}

        {/* SESSIONS VIEW */}
        {view === 'sessions' && !activeSession && (
          <div className="notes-container">
            <h1 className="notes-topic" style={{ marginBottom: 20 }}>Past Sessions</h1>
            {sessions.length === 0 ? (
              <p className="empty-small">No sessions saved yet.</p>
            ) : (
              <div className="session-list">
                {sessions.map((s, i) => {
                  const { topic: t, date: d } = formatFilename(s.filename)
                  return (
                    <button key={i} className="session-row" onClick={() => loadSession(s.filename)}>
                      <div>
                        <div className="session-name">{t}</div>
                        <div className="session-meta">{d} · {(s.size / 1024).toFixed(1)} KB</div>
                      </div>
                      <span className="arrow">→</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {view === 'sessions' && activeSession && (
          <div className="notes-container">
            <div className="notes-title-row">
              <div>
                <button className="back-btn" onClick={() => setActiveSession(null)}>← Back</button>
                <h1 className="notes-topic">{formatFilename(activeSession.filename).topic}</h1>
                <p className="notes-date">{formatFilename(activeSession.filename).date}</p>
              </div>
              <span className="count-badge">{activeSession.count} snapshots</span>
            </div>
            <div className="cards">
              {activeSession.snapshots.map((snap, i) => (
                <SnapshotCard key={i} snapshot={snap} index={i} isNew={false} />
              ))}
            </div>
          </div>
        )}

      </main>
    </div>
  )
}