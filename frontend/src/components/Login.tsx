import { useState } from 'react'
import {
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut,
  User,
} from 'firebase/auth'
import { auth, googleProvider } from '../firebase'

interface LoginProps {
  user: User | null
}

export default function Login({ user }: LoginProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (user) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <span style={{ fontSize: '14px' }}>{user.email}</span>
        <button onClick={() => signOut(auth)} style={btnOutline}>
          Sign Out
        </button>
      </div>
    )
  }

  const handleEmail = async (isSignUp: boolean) => {
    if (!email || !password) {
      setError('Email and password required')
      return
    }
    setLoading(true)
    setError(null)
    try {
      if (isSignUp) {
        await createUserWithEmailAndPassword(auth, email, password)
      } else {
        await signInWithEmailAndPassword(auth, email, password)
      }
    } catch (err: any) {
      setError(err.message?.replace('Firebase: ', '') || 'Auth failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogle = async () => {
    setError(null)
    try {
      await signInWithPopup(auth, googleProvider)
    } catch (err: any) {
      setError(err.message?.replace('Firebase: ', '') || 'Google sign-in failed')
    }
  }

  return (
    <div style={containerStyle}>
      <h2 style={{ margin: '0 0 20px', fontSize: '18px', textAlign: 'center' }}>Sign In</h2>

      <input
        type="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        style={inputStyle}
        disabled={loading}
      />
      <input
        type="password"
        placeholder="Password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        style={inputStyle}
        disabled={loading}
        onKeyDown={(e) => e.key === 'Enter' && handleEmail(false)}
      />

      <div style={{ display: 'flex', gap: '8px' }}>
        <button onClick={() => handleEmail(false)} disabled={loading} style={btnPrimary}>
          {loading ? '...' : 'Sign In'}
        </button>
        <button onClick={() => handleEmail(true)} disabled={loading} style={btnOutline}>
          Sign Up
        </button>
      </div>

      <div style={dividerStyle}>
        <span style={{ background: '#fff', padding: '0 8px', color: '#999', fontSize: '12px' }}>
          or
        </span>
      </div>

      <button onClick={handleGoogle} style={btnGoogle}>
        Sign in with Google
      </button>

      {error && <div style={errorStyle}>{error}</div>}
    </div>
  )
}

const containerStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '10px',
  maxWidth: '320px',
  margin: '60px auto',
  padding: '24px',
  border: '1px solid #e0e0e0',
  borderRadius: '8px',
}

const inputStyle: React.CSSProperties = {
  padding: '10px 12px',
  fontSize: '14px',
  border: '1px solid #ddd',
  borderRadius: '4px',
  outline: 'none',
}

const btnPrimary: React.CSSProperties = {
  flex: 1,
  padding: '10px',
  fontSize: '14px',
  background: '#4285f4',
  color: '#fff',
  border: 'none',
  borderRadius: '4px',
  cursor: 'pointer',
}

const btnOutline: React.CSSProperties = {
  flex: 1,
  padding: '10px',
  fontSize: '14px',
  background: '#fff',
  color: '#333',
  border: '1px solid #ccc',
  borderRadius: '4px',
  cursor: 'pointer',
}

const btnGoogle: React.CSSProperties = {
  padding: '10px',
  fontSize: '14px',
  background: '#fff',
  color: '#333',
  border: '1px solid #ccc',
  borderRadius: '4px',
  cursor: 'pointer',
}

const dividerStyle: React.CSSProperties = {
  textAlign: 'center',
  borderBottom: '1px solid #e0e0e0',
  lineHeight: '0.1em',
  margin: '8px 0',
}

const errorStyle: React.CSSProperties = {
  padding: '8px',
  background: '#fee',
  border: '1px solid #fcc',
  borderRadius: '4px',
  fontSize: '13px',
  color: '#c00',
}
