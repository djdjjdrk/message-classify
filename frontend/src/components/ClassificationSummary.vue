<script setup>
import { labels } from '../utils/format.js'

defineProps({ message: Object })
</script>

<template>
  <div class="classification-summary">
    <strong>分类：{{ labels[message.effective_label] || '未分类' }}</strong>
  </div>
</template>
