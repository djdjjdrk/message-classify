import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'
import { ApiError, request, setUnauthorizedHandler } from '../src/api/request.js'
import { clearToken, getToken, saveToken } from '../src/utils/token.js'
import { login, register } from '../src/api/auth.js'
import { publishMessage, deleteMessage, getMyMessages, getPublicMessages } from '../src/api/messages.js'
import { annotateMessage, getClassificationMessages } from '../src/api/classification.js'
import { reviewMessage, getPendingReviews } from '../src/api/review.js'

const originalFetch = globalThis.fetch
let expired
let calls
beforeEach(() => {
  const storage = new Map()
  globalThis.sessionStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: (key) => storage.delete(key),
  }
  expired = 0
  calls = []
  setUnauthorizedHandler(() => { expired++ })
  globalThis.fetch = async (url, options) => {
    calls.push({ url, ...options })
    return Response.json({ code: 200, message: '成功', data: { id: 1 } })
  }
})
afterEach(() => { globalThis.fetch = originalFetch })

test('unwraps the API envelope and sends the token and query parameters', async () => {
  saveToken('test-token')
  assert.deepEqual(await getMyMessages({ page: 2, page_size: 10 }), { id: 1 })
  assert.equal(calls[0].url, '/api/v1/messages/mine?page=2&page_size=10')
  assert.equal(calls[0].headers.Authorization, 'Bearer test-token')
})

test('all page actions use the existing backend routes and bodies', async () => {
  await login({ username: 'student', password: 'password123' })
  await register({ username: 'new-user', password: 'password123', nickname: null })
  await publishMessage('测试正文')
  await deleteMessage(3)
  await getPublicMessages({ page: 1 })
  await getClassificationMessages({ category: 'unclassified' })
  await annotateMessage(3, { label: 'normal', reason: '日常讨论' })
  await getPendingReviews({ page: 1 })
  await reviewMessage(3, { decision: 'rejected', comment: '广告' })
  assert.deepEqual(calls.map(({ url, method }) => [url, method]), [
    ['/api/v1/auth/login', 'POST'], ['/api/v1/auth/register', 'POST'],
    ['/api/v1/messages', 'POST'], ['/api/v1/messages/3', 'DELETE'],
    ['/api/v1/messages/public?page=1', 'GET'],
    ['/api/v1/classification/messages?category=unclassified', 'GET'],
    ['/api/v1/classification/messages/3/annotations', 'POST'],
    ['/api/v1/reviews/pending?page=1', 'GET'], ['/api/v1/reviews/messages/3', 'POST'],
  ])
  assert.deepEqual(JSON.parse(calls[6].body), { label: 'normal', reason: '日常讨论' })
  assert.deepEqual(JSON.parse(calls[8].body), { decision: 'rejected', comment: '广告' })
})

for (const status of [200, 401]) {
  test(`authenticated expiry clears the session for HTTP ${status}`, async () => {
    saveToken('expired')
    globalThis.fetch = async () => Response.json({ code: 401, message: '已失效', data: null }, { status })
    await assert.rejects(request('/auth/me'), (error) => error.code === 401)
    assert.equal(getToken(), null)
    assert.equal(expired, 1)
  })
}

test('wrong login password stays on the login form without expiring another session', async () => {
  saveToken('existing')
  globalThis.fetch = async () => Response.json({ code: 401, message: '用户名或密码错误', data: null }, { status: 401 })
  await assert.rejects(login({ username: 'student', password: 'wrong' }), /用户名或密码错误/)
  assert.equal(getToken(), 'existing')
  assert.equal(expired, 0)
})

test('an old request cannot log out a newly signed-in user', async () => {
  saveToken('old-token')
  globalThis.fetch = async () => {
    saveToken('new-token')
    return Response.json({ code: 401, message: '旧凭证失效', data: null })
  }
  await assert.rejects(request('/messages/mine'), ApiError)
  assert.equal(getToken(), 'new-token')
  assert.equal(expired, 0)
})

test('business errors on HTTP 200 remain actionable', async () => {
  globalThis.fetch = async () => Response.json({ code: 400, message: '留言已被删除', data: null })
  await assert.rejects(request('/messages/1'), /留言已被删除/)
})

test('HTML gateway errors and malformed envelopes become readable errors', async () => {
  globalThis.fetch = async () => new Response('<html>private gateway details</html>', { status: 502 })
  await assert.rejects(request('/messages/mine'), /服务返回异常/)
  globalThis.fetch = async () => Response.json({ code: '200', message: '成功' })
  await assert.rejects(request('/messages/mine'), /服务返回异常/)
})

test('connection failures and timeouts produce retry messages', async () => {
  globalThis.fetch = async () => { throw new TypeError('private connection details') }
  await assert.rejects(request('/messages/mine'), /无法连接后端/)
  globalThis.fetch = async () => { throw new DOMException('timeout', 'TimeoutError') }
  await assert.rejects(request('/messages/mine'), /请求超时/)
})

test('clearing a token removes persistent credentials', () => {
  saveToken('token')
  clearToken()
  assert.equal(getToken(), null)
})
