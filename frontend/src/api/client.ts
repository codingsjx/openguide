// Thin fetch wrapper for the backend. Vite dev proxy sends /api to :8000.
// Point VITE_API_BASE at the backend root when not using the proxy.
const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit, timeoutMs = 60_000): Promise<T> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
      signal: controller.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error(`请求超时（${Math.round(timeoutMs / 1000)} 秒），请检查网络或改用本地规则`)
    }
    throw new Error(error instanceof Error ? `网络请求失败：${error.message}` : '网络请求失败')
  } finally {
    window.clearTimeout(timeout)
  }
  if (!res.ok) {
    let detail = `请求失败 (${res.status})`
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') {
        detail = body.detail
      } else if (Array.isArray(body?.detail)) {
        detail = body.detail.map((item: { msg?: string }) => item.msg ?? '参数错误').join('；')
      }
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, detail)
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
    }, 180_000),
  getLlmConfig: () => request<{ configured: boolean }>('/api/llm-config'),
  setLlmConfig: (cfg: { api_key: string; base_url: string; model: string }) =>
    request<{ configured: boolean }>('/api/llm-config', {
      method: 'POST',
      body: JSON.stringify(cfg),
    }),
  postFollowup: (payload: {
    url: string
    intent: 'granular' | 'explain' | 'diagnose'
    step: Record<string, unknown>
    query?: string
    log_text?: string
  }) =>
    request<{ intent: string; text: string; sub_steps: unknown[]; sources: string[] }>(
      '/api/followup',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),
}
