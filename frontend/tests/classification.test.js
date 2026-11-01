import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import { compileScript, parse } from '@vue/compiler-sfc'
import { createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'

const source = await readFile(new URL('../src/components/ClassificationSummary.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const compiled = compileScript(descriptor, { id: 'classification-test', inlineTemplate: true })
const moduleCode = compiled.content
  .replaceAll(/from (['"])vue\1/g, `from '${import.meta.resolve('vue')}'`)
  .replaceAll('../utils/format.js', new URL('../src/utils/format.js', import.meta.url).href)
const { default: Summary } = await import(`data:text/javascript;base64,${Buffer.from(moduleCode).toString('base64')}`)

const prediction = {
  effective_label: 'spam', predicted_label: 'spam', prediction_status: 'success',
  predicted_probability: 0.91, model_name: 'baseline_v1', manual_label: null,
  prediction_explanation: [{ word: '免费', count: 2, contribution: 1.23456, direction: 'spam' }],
}
const render = message => renderToString(createSSRApp({ render: () => h(Summary, { message }) }))

test('classification shows only the effective manual label after correction', async () => {
  const html = await render({ ...prediction, effective_label: 'normal', manual_label: 'normal' })
  assert.match(html, /分类：普通/)
  assert.doesNotMatch(html, /原始模型|人工：|概率|baseline_v1|免费|词频|贡献|支持/)
})

test('spam classification hides model details and contribution words', async () => {
  const html = await render(prediction)
  assert.match(html, /分类：垃圾/)
  assert.doesNotMatch(html, /概率|模型名|baseline_v1|免费|词频|贡献|<li>/)
})

test('no features remains unclassified', async () => {
  const html = await render({ ...prediction, prediction_status: 'no_features', effective_label: null })
  assert.match(html, /分类：未分类/)
  assert.doesNotMatch(html, /概率|词频|贡献/)
})
