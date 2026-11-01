import { request } from './request.js'

export function getStatistics() {
  return request('/statistics')
}
