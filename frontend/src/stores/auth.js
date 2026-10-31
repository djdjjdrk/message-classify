import { reactive } from 'vue'
import { getCurrentUser, login as loginRequest } from '../api/auth.js'
import { clearToken, getToken, saveToken } from '../utils/token.js'

export const auth = reactive({ user: null, checking: true, error: '' })
let initialization

export function initializeAuth() {
  if (!initialization) {
    initialization = (async () => {
      try {
        if (getToken()) auth.user = await getCurrentUser()
      } catch (error) {
        auth.error = error.message
      } finally {
        auth.checking = false
      }
    })()
  }
  return initialization
}

export async function signIn(username, password) {
  const result = await loginRequest({ username, password })
  saveToken(result.access_token)
  auth.user = result.user
  auth.error = ''
}

export function signOut(message = '') {
  clearToken()
  auth.user = null
  auth.error = message
}
