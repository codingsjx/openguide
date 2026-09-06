// Thin fetch wrapper for the backend. Vite dev proxy sends /api to :8000.
// Point VITE_API_BASE at the backend root when not using the proxy.
const BASE = import.meta.env.VITE_API_BASE ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `请求失败 (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch {
      /* keep default */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export interface SearchHit {
  text: string
  perspective: string
  score: number
  meta: Record<string, unknown>
}

export interface SearchResult {
  url: string
  query: string
  kind: string
  perspective: string
  hits: SearchHit[]
}

export const api = {
  postProfile: (url: string) =>
    request<import('../types/profile').Profile>('/api/profile', {
      method: 'POST',
      body: JSON.stringify({ url }),
    }),
  postSearch: (url: string, query: string, kind?: string) =>
    request<SearchResult>('/api/search', {
      method: 'POST',
      body: JSON.stringify({ url, query, kind: kind ?? null }),
    }),
  postGuide: (url: string, useLlm = true) =>
    request<import('../types/guide').Guide>('/api/guide', {
      method: 'POST',
      body: JSON.stringify({ url, use_llm: useLlm }),
    }),
  getLlmConfig: () => request<{ configured: boolean }>('/api/llm-config'),
  setLlmConfig: (cfg: { api_key: string; base_url: string; model: string }) =>
    request<{ configured: boolean }>('/api/llm-config', {
      method: 'POST',
      body: JSON.stringify(cfg),
    }),
}
