import { request } from './request.js'

export function getClassificationMessages(params) {
  return request('/classification/messages', { params })
}

export function annotateMessage(id, data) {
  return request(`/classification/messages/${id}/annotations`, { method: 'POST', body: data })
}
