<script setup>
import { computed } from 'vue'
import { labels, predictionStatuses } from '../utils/format.js'

const props = defineProps({ message: Object })

// 成功预测才展示概率和模型名；其余状态只说明原因，交给人工标注。
const prediction = computed(() => {
  if (props.message.prediction_status !== 'success') return null
  return {
    label: labels[props.message.predicted_label] || '未知',
    percent: props.message.predicted_probability == null
      ? ''
      : `垃圾概率 ${(props.message.predicted_probability * 100).toFixed(1)}%`,
    model: props.message.model_name || '未知模型',
  }
})

// 后端已按贡献绝对值降序给出最多 5 个词，这里只展示词、词频和方向，不重算贡献。
const contributions = computed(() => {
  // 只有预测成功时的解释才可信；其余状态即使残留旧 JSON 也不展示。
  if (props.message.prediction_status !== 'success') return []
  const list = props.message.prediction_explanation
  if (!Array.isArray(list)) return []
  return list
    .filter(item => item?.word)
    .slice(0, 5)
    .map(item => ({ word: item.word, count: item.count ?? 0, direction: item.direction === 'spam' ? '垃圾' : '正常' }))
})
</script>

<template>
  <div class="classification-summary">
    <strong>分类：{{ labels[message.effective_label] || '未分类' }}</strong>
    <span v-if="prediction" class="muted">
      模型预测：{{ prediction.label }}<template v-if="prediction.percent">，{{ prediction.percent }}</template> · {{ prediction.model }}
    </span>
    <span v-else class="muted">{{ predictionStatuses[message.prediction_status] || '待预测' }}</span>
    <span v-if="contributions.length" class="muted">
      主要依据：<template v-for="(item, index) in contributions" :key="item.word">{{ index ? '、' : '' }}{{ item.word }}（{{ item.count }}次，支持{{ item.direction }}）</template>
    </span>
  </div>
</template>
