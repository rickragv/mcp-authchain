import { WeatherData } from '../api'

interface WeatherCardProps {
  data: WeatherData
}

const weatherIcons: Record<number, string> = {
  0: '\u2600\uFE0F',     // Clear
  1: '\uD83C\uDF24\uFE0F', // Mostly Clear
  2: '\u26C5',           // Partly Cloudy
  3: '\u2601\uFE0F',     // Overcast
  45: '\uD83C\uDF2B\uFE0F', // Fog
  48: '\uD83C\uDF2B\uFE0F', // Fog
  51: '\uD83C\uDF26\uFE0F', // Drizzle
  53: '\uD83C\uDF26\uFE0F',
  55: '\uD83C\uDF26\uFE0F',
  61: '\uD83C\uDF27\uFE0F', // Rain
  63: '\uD83C\uDF27\uFE0F',
  65: '\uD83C\uDF27\uFE0F',
  71: '\u2744\uFE0F',     // Snow
  73: '\u2744\uFE0F',
  75: '\u2744\uFE0F',
  80: '\uD83C\uDF26\uFE0F', // Showers
  81: '\uD83C\uDF27\uFE0F',
  82: '\uD83C\uDF27\uFE0F',
  95: '\u26C8\uFE0F',     // Thunderstorm
  96: '\u26C8\uFE0F',
  99: '\u26C8\uFE0F',
}

function getGradient(code: number): string {
  if (code === 0 || code === 1) return 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)'
  if (code === 2) return 'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)'
  if (code === 3) return 'linear-gradient(135deg, #a8c0ff 0%, #8f94fb 100%)'
  if (code >= 45 && code <= 48) return 'linear-gradient(135deg, #d7d2cc 0%, #304352 100%)'
  if (code >= 51 && code <= 67) return 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)'
  if (code >= 71 && code <= 77) return 'linear-gradient(135deg, #e6e9f0 0%, #eef1f5 100%)'
  if (code >= 80 && code <= 82) return 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
  if (code >= 95) return 'linear-gradient(135deg, #434343 0%, #000000 100%)'
  return 'linear-gradient(135deg, #89f7fe 0%, #66a6ff 100%)'
}

function getTextColor(code: number): string {
  if (code >= 95) return '#fff'
  if (code >= 45 && code <= 48) return '#fff'
  if (code >= 71 && code <= 77) return '#333'
  return '#fff'
}

export default function WeatherCard({ data }: WeatherCardProps) {
  const icon = weatherIcons[data.weather_code] || '\uD83C\uDF21\uFE0F'
  const gradient = getGradient(data.weather_code)
  const textColor = getTextColor(data.weather_code)

  return (
    <div style={{ ...cardStyle, background: gradient, color: textColor }}>
      <div style={topRow}>
        <div>
          <div style={{ fontSize: '18px', fontWeight: 600 }}>{data.city}</div>
          <div style={{ fontSize: '13px', opacity: 0.85 }}>{data.country}</div>
        </div>
        <div style={{ fontSize: '48px', lineHeight: 1 }}>{icon}</div>
      </div>

      <div style={{ fontSize: '48px', fontWeight: 300, margin: '12px 0 4px' }}>
        {Math.round(data.temperature)}°
      </div>

      <div style={{ fontSize: '14px', opacity: 0.9, marginBottom: '16px' }}>
        {data.condition}
      </div>

      <div style={statsRow}>
        <div style={statItem}>
          <div style={{ fontSize: '11px', opacity: 0.7, textTransform: 'uppercase' }}>Wind</div>
          <div style={{ fontSize: '16px', fontWeight: 500 }}>{data.wind_speed} km/h</div>
        </div>
        <div style={{ ...statItem, borderLeft: `1px solid ${textColor}33` }}>
          <div style={{ fontSize: '11px', opacity: 0.7, textTransform: 'uppercase' }}>Feels Like</div>
          <div style={{ fontSize: '16px', fontWeight: 500 }}>{Math.round(data.temperature)}°C</div>
        </div>
      </div>
    </div>
  )
}

const cardStyle: React.CSSProperties = {
  borderRadius: '16px',
  padding: '24px',
  minWidth: '280px',
  maxWidth: '340px',
  boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
}

const topRow: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'flex-start',
}

const statsRow: React.CSSProperties = {
  display: 'flex',
  borderTop: '1px solid rgba(255,255,255,0.2)',
  paddingTop: '12px',
}

const statItem: React.CSSProperties = {
  flex: 1,
  textAlign: 'center',
}
