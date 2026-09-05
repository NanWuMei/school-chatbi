const BASE = '/api/v1'

export interface UserInfo {
  user_id: string
  name: string
  role: number
  role_name: string
  class_id?: string | null
  grade?: string | null
}

export interface Message {
  id: number
  role: 'user' | 'assistant'
  text: string
  answer_type?: string | null
  chart_config?: any
  data_rows?: any[]
  generated_sql?: string | null
  suggestions?: any[]
  can_feedback?: boolean
  created_at: string
}

function token(): string {
  return localStorage.getItem('chatbi_token') || ''
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> | undefined),
  }
  if (token()) headers.Authorization = `Bearer ${token()}`
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  async login(user_id: string, password: string): Promise<{ access_token: string; user: UserInfo }> {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ user_id, password }),
    })
  },
  async me(): Promise<UserInfo> {
    return request('/auth/me')
  },
  async createSession(): Promise<{ session_id: string }> {
    return request('/sessions', { method: 'POST' })
  },
  async listMessages(sessionId: string): Promise<Message[]> {
    return request(`/sessions/${sessionId}/messages`)
  },
  async chat(sessionId: string, query: string): Promise<any> {
    return request('/chat', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, query }),
    })
  },
  async runSkill(
    skill: 'overall_distribution' | 'risk_warning' | 'class_compare' | 'course_deep' | 'trend_compare' | 'group_diff',
    filters: any = {},
  ): Promise<any> {
    return request('/skills/run', {
      method: 'POST',
      body: JSON.stringify({ skill, ...filters }),
    })
  },
  async attribution(payload: any = {}): Promise<any> {
    return request('/attribution', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  async feedback(payload: { message_id: number; feedback: -1 | 0 | 1; feedback_reason?: string | null }): Promise<any> {
    return request('/feedback', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  async getFeedback(): Promise<any[]> {
    return request('/feedback')
  },
  async metaIndicators(): Promise<{ indicators: any[]; courses: any[] }> {
    return request('/meta/indicators')
  },
}
