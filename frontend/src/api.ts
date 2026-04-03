const API_URL = import.meta.env.VITE_API_URL || ''

export interface WeatherData {
  type: 'weather'
  city: string
  country: string
  temperature: number
  wind_speed: number
  condition: string
  weather_code: number
}

export interface ChatResponse {
  response: string
  user_uid: string
  tools_used: string[]
}

export interface ParsedResponse {
  weather: WeatherData[] | null
  text: string | null
}

export function parseResponse(response: string): ParsedResponse {
  // Strip qwen thinking tags if present
  let cleaned = response.replace(/<think>[\s\S]*?<\/think>/g, '').trim()

  // Try format: JSON --- summary
  const separatorIdx = cleaned.indexOf('\n---')
  if (separatorIdx > 0) {
    const jsonPart = cleaned.substring(0, separatorIdx).trim()
    const textPart = cleaned.substring(separatorIdx + 4).trim()

    try {
      const parsed = JSON.parse(jsonPart)
      const weatherArr = Array.isArray(parsed) ? parsed : [parsed]
      if (weatherArr[0]?.type === 'weather') {
        return { weather: weatherArr, text: textPart || null }
      }
    } catch {
      // fall through
    }
  }

  // Try parsing entire response as JSON (no summary)
  try {
    // Find first { or [ in the string (skip any leaked thinking text)
    const jsonStart = cleaned.search(/[\[{]/)
    if (jsonStart >= 0) {
      const jsonStr = cleaned.substring(jsonStart)
      const parsed = JSON.parse(jsonStr)

      if (parsed.type === 'weather') {
        return { weather: [parsed], text: jsonStart > 0 ? null : null }
      }
      if (Array.isArray(parsed) && parsed.length > 0 && parsed[0].type === 'weather') {
        return { weather: parsed, text: null }
      }
    }
  } catch {
    // Not JSON
  }

  return { weather: null, text: cleaned }
}

export async function sendChat(prompt: string, idToken: string): Promise<ChatResponse> {
  const res = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${idToken}`,
    },
    body: JSON.stringify({ prompt }),
  })

  if (res.status === 401) {
    throw new Error('Unauthorized -- please sign in again')
  }

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`API error ${res.status}: ${text}`)
  }

  return res.json()
}
