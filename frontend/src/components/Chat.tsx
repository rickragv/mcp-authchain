import { useState } from 'react'
import { User } from 'firebase/auth'
import { sendChat, parseResponse, ParsedResponse } from '../api'
import WeatherCard from './WeatherCard'

interface ChatProps {
  user: User
}

export default function Chat({ user }: ChatProps) {
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ParsedResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!prompt.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const idToken = await user.getIdToken(true)  // force refresh on every request
      const res = await sendChat(prompt, idToken)
      setResult(parseResponse(res.response))
    } catch (err: any) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <form onSubmit={handleSubmit} style={formStyle}>
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Try 'weather in Tokyo' or 'weather in London and Paris'"
          style={inputStyle}
          disabled={loading}
        />
        <button type="submit" disabled={loading} style={submitStyle}>
          {loading ? (
            <span style={spinnerStyle} />
          ) : (
            '\u2192'
          )}
        </button>
      </form>

      {error && (
        <div style={errorStyle}>{error}</div>
      )}

      {result?.weather && (
        <div style={resultSection}>
          <div style={cardsContainer}>
            {result.weather.map((w, i) => (
              <WeatherCard key={`${w.city}-${i}`} data={w} />
            ))}
          </div>
          {result.text && (
            <div style={summaryStyle}>
              {result.text}
            </div>
          )}
        </div>
      )}

      {!result?.weather && result?.text && (
        <div style={textResultStyle}>
          {result.text}
        </div>
      )}
    </div>
  )
}

const formStyle: React.CSSProperties = {
  display: 'flex',
  gap: '8px',
  marginBottom: '32px',
}

const inputStyle: React.CSSProperties = {
  flex: 1,
  padding: '14px 20px',
  fontSize: '16px',
  border: '2px solid #e0e0e0',
  borderRadius: '28px',
  outline: 'none',
  transition: 'border-color 0.2s',
}

const submitStyle: React.CSSProperties = {
  width: '52px',
  height: '52px',
  fontSize: '20px',
  background: '#4285f4',
  color: '#fff',
  border: 'none',
  borderRadius: '50%',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}

const spinnerStyle: React.CSSProperties = {
  width: '18px',
  height: '18px',
  border: '2px solid rgba(255,255,255,0.3)',
  borderTop: '2px solid #fff',
  borderRadius: '50%',
  animation: 'spin 0.8s linear infinite',
}

const cardsContainer: React.CSSProperties = {
  display: 'flex',
  gap: '16px',
  flexWrap: 'wrap',
  justifyContent: 'center',
}

const errorStyle: React.CSSProperties = {
  padding: '12px 16px',
  background: '#fff0f0',
  border: '1px solid #fcc',
  borderRadius: '12px',
  color: '#c00',
  fontSize: '14px',
}

const resultSection: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
  alignItems: 'center',
}

const summaryStyle: React.CSSProperties = {
  padding: '14px 20px',
  background: '#f0f4ff',
  borderRadius: '12px',
  border: '1px solid #d0d9f0',
  lineHeight: '1.6',
  fontSize: '15px',
  color: '#333',
  maxWidth: '500px',
  textAlign: 'center',
}

const textResultStyle: React.CSSProperties = {
  padding: '16px 20px',
  background: '#f8f9fa',
  borderRadius: '12px',
  border: '1px solid #e0e0e0',
  lineHeight: '1.6',
  whiteSpace: 'pre-wrap',
}
