import { request } from './request.js'

export function getPendingReviews(params) {
  return request('/reviews/pending', { params })
}

export function reviewMessage(id, data) {
  return request(`/reviews/messages/${id}`, { method: 'POST', body: data })
}
