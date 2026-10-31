<script setup>
import { labels, predictionStatuses } from '../utils/format.js'
defineProps({ message: Object })
</script>

<template>
  <div class="classification-summary">
    <strong>当前分类：{{ labels[message.effective_label] || '未分类' }}</strong>
    <span class="muted">模型：{{ message.prediction_status === 'success'
      ? labels[message.predicted_label] || '未分类' : predictionStatuses[message.prediction_status] }}
      · 人工：{{ labels[message.manual_label] || '未标注' }}</span>
  </div>
</template>
