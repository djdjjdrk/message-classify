import { clearToken, getToken } from '../utils/token.js'

const baseURL = '/api/v1'
let onUnauthorized = () => {}

export class ApiError extends Error {
  constructor(message, status = 0, code = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

export async function request(path, { method = 'GET', body, params, auth = true } = {}) {
  const headers = { Accept: 'application/json' }
  const token = auth ? getToken() : null
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let url = `${baseURL}${path}`
  if (params) url += `?${new URLSearchParams(params)}`
  let response
  try {
    response = await fetch(url, {
      method, headers, body: JSON.stringify(body), signal: AbortSignal.timeout(10000),
    })
  } catch (error) {
    if (error.name === 'TimeoutError' || error.name === 'AbortError') {
      throw new ApiError('请求超时，请重试')
    }
    throw new ApiError('无法连接后端服务，请稍后重试')
  }
  const payload = await response.json().catch(() => null)
  if (auth && (response.status === 401 || payload?.code === 401)) {
    // 已退出或换账号后，旧请求的响应不能清除新账号的凭证。
    if (token === getToken()) {
      clearToken()
      onUnauthorized()
    }
    throw new ApiError('登录已失效，请重新登录', response.status, 401)
  }
  if (!payload || !Number.isInteger(payload.code) || typeof payload.message !== 'string'
      || !Object.hasOwn(payload, 'data')) {
    throw new ApiError('服务返回异常，请稍后重试', response.status)
  }
  if (!response.ok || payload.code !== 200) {
    throw new ApiError(payload.message || '请求失败，请重试', response.status, payload.code)
  }
  return payload.data
}
