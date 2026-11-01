import assert from 'node:assert/strict'
import { test } from 'node:test'
import { effectScope } from 'vue'
import { useStatistics } from '../src/composables/useStatistics.js'

const flush = () => new Promise(setImmediate)

test('statistics load on entry and retry after a refresh failure', async () => {
  const scope = effectScope()
  let fails = false
  let total = 0
  const state = scope.run(() => useStatistics(async () => {
    if (fails) throw new Error('统计暂不可用')
    return { total }
  }))
  await flush()
  assert.equal(state.statistics.value.total, 0)
  fails = true
  await state.reload()
  assert.equal(state.error.value, '统计暂不可用')
  assert.equal(state.loading.value, false)
  fails = false
  total = 12
  await state.reload()
  assert.equal(state.statistics.value.total, 12)
  assert.equal(state.error.value, '')
  scope.stop()
})

test('stale statistics responses and unmounted loads cannot replace the current data', async () => {
  const scope = effectScope()
  const pending = []
  const state = scope.run(() => useStatistics(() => new Promise((resolve) => pending.push(resolve))))
  const refresh = state.reload()
  pending[1]({ total: 2 })
  await refresh
  pending[0]({ total: 1 })
  await flush()
  assert.equal(state.statistics.value.total, 2)
  const last = state.reload()
  scope.stop()
  pending[2]({ total: 3 })
  await last
  assert.equal(state.statistics.value.total, 2)
})
