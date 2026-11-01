<script setup>
import { useStatistics } from '../composables/useStatistics.js'

const { statistics, loading, error, reload } = useStatistics()
const classificationLabels = { normal: '普通', spam: '垃圾', unclassified: '未分类' }
const reviewLabels = { pending: '待审核', approved: '已通过', rejected: '已驳回' }
</script>

<template>
  <div class="page-heading">
    <div><p class="eyebrow">STATISTICS</p><h1>留言统计</h1><p class="muted">统计全部未删除留言，分类与审核情况分别汇总。</p></div>
    <button :disabled="loading" @click="reload">刷新统计</button>
  </div>
  <section :aria-busy="loading" aria-label="留言统计数据">
    <div v-if="error" class="notice error" role="alert">{{ error }} <button @click="reload">重试</button></div>
    <p v-else-if="loading" class="empty-state" role="status">正在加载统计…</p>
    <template v-else-if="statistics">
      <section class="panel statistics-total" aria-labelledby="total-heading">
        <div><h2 id="total-heading">留言总数</h2><p class="muted">不包含已删除留言</p></div>
        <p class="stat-number">{{ statistics.total.toLocaleString('zh-CN') }} <span class="muted">条</span></p>
      </section>
      <div class="statistics-grid">
        <section class="panel" aria-labelledby="classification-heading">
          <h2 id="classification-heading">分类分布</h2>
          <p class="muted">人工标签优先，其次采用成功的模型预测。</p>
          <dl class="stat-list">
            <div v-for="(label, key) in classificationLabels" :key="key"><dt>{{ label }}</dt><dd>{{ statistics.classification[key].toLocaleString('zh-CN') }} <span class="muted">条</span></dd></div>
          </dl>
        </section>
        <section class="panel" aria-labelledby="review-heading">
          <h2 id="review-heading">审核情况</h2>
          <p class="muted">按留言当前审核状态统计。</p>
          <dl class="stat-list">
            <div v-for="(label, key) in reviewLabels" :key="key"><dt>{{ label }}</dt><dd>{{ statistics.review[key].toLocaleString('zh-CN') }} <span class="muted">条</span></dd></div>
          </dl>
        </section>
      </div>
    </template>
  </section>
</template>
