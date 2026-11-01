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
const render = async message => {
  const html = await renderToString(createSSRApp({ render: () => h(Summary, { message }) }))
  // SSR 会在 v-for/v-if 之间插入 <!--[--> 之类的分片注释，断言前先去掉。
  return html.replaceAll(/<!--.*?-->/g, '')
}

test('classification shows model prediction with probability, model name and contribution words', async () => {
  const html = await render(prediction)
  assert.match(html, /分类：垃圾/)
  assert.match(html, /模型预测：垃圾/)
  assert.match(html, /垃圾概率 91\.0%/)
  assert.match(html, /baseline_v1/)
  assert.match(html, /主要依据：免费（2次，支持垃圾）/)
})

test('manual correction keeps the original model prediction visible', async () => {
  const html = await render({ ...prediction, effective_label: 'normal', manual_label: 'normal' })
  assert.match(html, /分类：普通/)
  assert.match(html, /模型预测：垃圾/)
  assert.match(html, /垃圾概率 91\.0%/)
})

test('contribution words are capped at five', async () => {
  const words = ['甲', '乙', '丙', '丁', '戊', '己']
  const html = await render({
    ...prediction,
    prediction_explanation: words.map((word, index) => ({ word, count: 1, contribution: 1 - index * 0.1, direction: 'spam' })),
  })
  assert.match(html, /主要依据：甲（1次，支持垃圾）/)
  assert.match(html, /、乙（1次，支持垃圾）、丙/)
  assert.match(html, /、戊（1次，支持垃圾）/)
  assert.doesNotMatch(html, /己/)
})

test('no features shows the manual hint and no probability', async () => {
  const html = await render({ ...prediction, prediction_status: 'no_features', effective_label: null })
  assert.match(html, /分类：未分类/)
  assert.match(html, /无已知特征，请人工标注/)
  assert.doesNotMatch(html, /垃圾概率|baseline_v1|主要依据/)
})
