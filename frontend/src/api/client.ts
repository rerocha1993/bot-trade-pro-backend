/** Cliente HTTP mínimo. Em dev o Vite faz proxy; em produção o FastAPI serve o painel na mesma origem. */
export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

type Params = Record<string, string | number | boolean | null | undefined>

function url(path: string, params?: Params): string {
  if (!params) return path
  const q = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join('&')
  return q ? `${path}?${q}` : path
}

async function call<T>(method: string, path: string, params?: Params, body?: unknown): Promise<T> {
  const res = await fetch(url(path, params), {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  let data: unknown = text
  try { data = text ? JSON.parse(text) : null } catch { /* texto puro */ }
  if (!res.ok) {
    const detail = (data && typeof data === 'object' && 'detail' in data) ? (data as { detail: unknown }).detail : data
    throw new ApiError(res.status, detail)
  }
  return data as T
}

export const api = {
  get: <T>(path: string, params?: Params) => call<T>('GET', path, params),
  post: <T>(path: string, params?: Params, body?: unknown) => call<T>('POST', path, params, body),
  put: <T>(path: string, params?: Params, body?: unknown) => call<T>('PUT', path, params, body),
  patch: <T>(path: string, params?: Params, body?: unknown) => call<T>('PATCH', path, params, body),
  del: <T>(path: string, params?: Params) => call<T>('DELETE', path, params),
}

export function erroTexto(e: unknown): string {
  if (e instanceof ApiError) return `${e.status}: ${e.message}`
  if (e instanceof Error) return e.message
  return String(e)
}
