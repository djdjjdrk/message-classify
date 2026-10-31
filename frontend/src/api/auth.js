import { request } from './request.js'

export function login(data) {
  return request('/auth/login', { method: 'POST', body: data, auth: false })
}

export function register(data) {
  return request('/auth/register', { method: 'POST', body: data, auth: false })
}

export function getCurrentUser() {
  return request('/auth/me')
}
