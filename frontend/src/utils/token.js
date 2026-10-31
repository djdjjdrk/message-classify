const tokenKey = 'campus_access_token'

export function getToken() {
  return sessionStorage.getItem(tokenKey)
}

export function saveToken(token) {
  sessionStorage.setItem(tokenKey, token)
}

export function clearToken() {
  sessionStorage.removeItem(tokenKey)
}
