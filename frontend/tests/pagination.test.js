import assert from 'node:assert/strict'
import { test } from 'node:test'
import { computed, effectScope, nextTick, ref } from 'vue'
import { usePagedList } from '../src/composables/usePagedList.js'

const flush = async () => { await new Promise(setImmediate); await nextTick() }

test('filter changes reset pagination and shrinking results clamp the last page', async () => {
  const scope = effectScope()
  const category = ref('all')
  let total = 11
  const calls = []
  const endpoint = computed(() => async (params) => {
    calls.push(params)
    return { total, list: [{ id: params.page }] }
  })
  const list = scope.run(() => usePagedList(endpoint, computed(() => ({ category: category.value }))))
  await flush()
  list.page.value = 2
  await flush()
  assert.equal(list.items.value[0].id, 2)
  total = 10
  await list.reload()
  await flush()
  assert.equal(list.page.value, 1)
  assert.equal(list.items.value[0].id, 1)
  total = 11
  await list.reload()
  list.page.value = 2
  await flush()
  category.value = 'spam'
  await flush()
  assert.equal(list.page.value, 1)
  assert.equal(calls.at(-1).category, 'spam')
  assert.equal(calls.at(-1).page_size, 10)
  scope.stop()
})

test('older responses do not overwrite newer filters', async () => {
  const scope = effectScope()
  const filters = ref({ category: 'all' })
  const pending = []
  const endpoint = computed(() => () => new Promise((resolve) => pending.push(resolve)))
  const list = scope.run(() => usePagedList(endpoint, filters))
  filters.value = { category: 'spam' }
  await nextTick()
  pending[1]({ total: 1, list: [{ id: 2 }] })
  await flush()
  pending[0]({ total: 1, list: [{ id: 1 }] })
  await flush()
  assert.deepEqual(list.items.value, [{ id: 2 }])
  scope.stop()
})

test('failed loads can be retried without changing the current page', async () => {
  const scope = effectScope()
  let fails = true
  const endpoint = computed(() => async () => {
    if (fails) throw new Error('服务暂不可用')
    return { total: 0, list: [] }
  })
  const list = scope.run(() => usePagedList(endpoint))
  await flush()
  assert.equal(list.error.value, '服务暂不可用')
  assert.equal(list.loading.value, false)
  fails = false
  await list.reload()
  assert.equal(list.error.value, '')
  assert.equal(list.page.value, 1)
  scope.stop()
})

test('message search carries keywords through pages and scopes and clears to page one', async () => {
  const scope = effectScope()
  const keyword = ref('图书馆')
  const board = ref('mine')
  const calls = []
  const endpoints = Object.fromEntries(['mine', 'public'].map((name) => [name, async (params) => {
    calls.push({ scope: name, ...params })
    return { total: 21, list: [] }
  }]))
  const endpoint = computed(() => endpoints[board.value])
  const list = scope.run(() => usePagedList(endpoint, computed(() => ({ keyword: keyword.value }))))
  await flush()
  list.page.value = 2
  await flush()
  assert.deepEqual(calls.at(-1), { scope: 'mine', page: 2, page_size: 10, keyword: '图书馆' })
  board.value = 'public'
  await flush()
  assert.deepEqual(calls.at(-1), { scope: 'public', page: 1, page_size: 10, keyword: '图书馆' })
  list.page.value = 2
  await flush()
  keyword.value = ''
  await flush()
  assert.deepEqual(calls.at(-1), { scope: 'public', page: 1, page_size: 10, keyword: '' })
  scope.stop()
})
