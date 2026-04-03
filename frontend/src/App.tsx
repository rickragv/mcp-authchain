import { useEffect, useState } from 'react'
import { onAuthStateChanged, User } from 'firebase/auth'
import { auth } from './firebase'
import Login from './components/Login'
import Chat from './components/Chat'

export default function App() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const unsub = onAuthStateChanged(auth, (u) => {
      setUser(u)
      setLoading(false)
    })
    return unsub
  }, [])

  if (loading) {
    return <div style={containerStyle}>Loading...</div>
  }

  return (
    <div style={containerStyle}>
      <header style={headerStyle}>
        <h1 style={{ margin: 0, fontSize: '20px' }}>MCP Auth Demo</h1>
        {user && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '14px' }}>{user.email}</span>
            <button onClick={() => auth.signOut()} style={signOutBtn}>Sign Out</button>
          </div>
        )}
      </header>

      <main style={{ padding: '20px' }}>
        {user ? (
          <Chat user={user} />
        ) : (
          <>
            <div style={{ textAlign: 'center', color: '#666', marginTop: '20px' }}>
              <p style={{ fontSize: '13px' }}>
                Firebase token flows: Frontend → Agent API → MCP Server
              </p>
            </div>
            <Login user={user} />
          </>
        )}
      </main>
    </div>
  )
}

const containerStyle: React.CSSProperties = {
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  minHeight: '100vh',
  background: '#fff',
}

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '12px 24px',
  borderBottom: '1px solid #e0e0e0',
}

const signOutBtn: React.CSSProperties = {
  padding: '6px 12px',
  fontSize: '13px',
  background: '#fff',
  color: '#333',
  border: '1px solid #ccc',
  borderRadius: '4px',
  cursor: 'pointer',
}
