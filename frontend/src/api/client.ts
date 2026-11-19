// A thin wrapper around fetch: base URL, JSON, access token, error parsing,
// and one automatic refresh of the access token on 401.

const API_PREFIX = '/api/v1'

// The access token lives only in memory (not localStorage): after a page reload
// it is restored from the httpOnly refresh cookie (see refreshAccessToken).
let accessToken: string | null = null

// AuthProvider subscribes here to know when the session is gone (refresh failed).
let onSessionExpired: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler
}

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

type QueryValue = string | number | boolean | null | undefined

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  // JSON body; for files pass `formData` instead.
  body?: unknown
  formData?: FormData
  // Empty values (undefined, null, '') are skipped.
  query?: Record<string, QueryValue>
}

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') {
      params.set(key, String(value))
    }
  }
  const search = params.toString()
  return `${API_PREFIX}${path}${search ? `?${search}` : ''}`
}

// FastAPI errors: {"detail": "text"} or, for 422, {"detail": [{"msg": ...}, ...]}.
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') {
      return data.detail
    }
    if (Array.isArray(data.detail)) {
      return data.detail
        .map((item: { msg?: string }) => item.msg?.replace(/^Value error, /, ''))
        .filter(Boolean)
        .join(' ')
    }
  } catch {
    // Not JSON (e.g. a proxy error page) - fall through to the generic text.
  }
  return `Помилка сервера (${response.status}).`
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {}
  let body: BodyInit | undefined
  if (options.formData) {
    body = options.formData // the browser sets multipart Content-Type itself
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`
  }
  return fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers,
    body,
  })
}

// Several requests may get 401 at the same time: they share one refresh call.
let refreshPromise: Promise<string | null> | null = null

export function refreshAccessToken(): Promise<string | null> {
  refreshPromise ??= fetch(`${API_PREFIX}/accounts/refresh`, { method: 'POST' })
    .then(async (response) => {
      if (!response.ok) {
        return null
      }
      const data = (await response.json()) as { access_token: string }
      return data.access_token
    })
    .catch(() => null)
    .then((token) => {
      setAccessToken(token)
      refreshPromise = null
      return token
    })
  return refreshPromise
}

export async function api<T = void>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options)

  // Access token expired (15 min): get a new one and repeat the request once.
  if (response.status === 401 && accessToken) {
    const token = await refreshAccessToken()
    if (token) {
      response = await send(path, options)
    } else {
      onSessionExpired?.()
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
