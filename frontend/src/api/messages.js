import { request } from './request.js'

export function getMyMessages(params) {
  return request('/messages/mine', { params })
}

export function getPublicMessages(params) {
  return request('/messages/public', { params })
}

export function publishMessage(content) {
  return request('/messages', { method: 'POST', body: { content } })
}

export function deleteMessage(id) {
  return request(`/messages/${id}`, { method: 'DELETE' })
}
