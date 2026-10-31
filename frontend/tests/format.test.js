import assert from 'node:assert/strict'
import { test } from 'node:test'
import { formatTime } from '../src/utils/format.js'

test('naive UTC timestamps and explicit zones display the same Beijing time', () => {
  const expected = formatTime('2026-10-31T08:00:00Z')
  assert.equal(formatTime('2026-10-31T08:00:00'), expected)
  assert.equal(formatTime('2026-10-31T16:00:00+08:00'), expected)
  assert.match(expected, /16:00/)
  assert.equal(formatTime(null), '')
})
