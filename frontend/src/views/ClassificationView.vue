<script setup>
import { computed, ref } from 'vue'
import { getClassificationMessages } from '../api/classification.js'
import { usePagedList } from '../composables/usePagedList.js'
import AnnotationForm from '../components/AnnotationForm.vue'
import ClassificationSummary from '../components/ClassificationSummary.vue'
import ListStatus from '../components/ListStatus.vue'
import MessageCard from '../components/MessageCard.vue'
import PaginationBar from '../components/PaginationBar.vue'

const category = ref('all')
const endpoint = computed(() => getClassificationMessages)
const filters = computed(() => ({ category: category.value }))
const { items, page, total, pages, loading, error, reload } = usePagedList(endpoint, filters)
const notice = ref('')
function saved(message) {
  notice.value = message
  reload()
}
</script>

<template>
  <div class="page-heading"><div><p class="eyebrow">CLASSIFICATION</p><h1>分类标注</h1><p class="muted">查看分类结果并进行人工标注。</p></div></div>
  <p v-if="notice" class="notice success" role="status">{{ notice }}</p>
  <section class="list-section" :aria-busy="loading">
    <div class="list-toolbar">
      <label class="filter-label">分类<select v-model="category" @change="notice = ''"><option value="all">全部</option><option value="unclassified">未分类</option><option value="normal">普通</option><option value="spam">垃圾</option></select></label>
      <button :disabled="loading" @click="reload">刷新列表</button>
    </div>
    <ListStatus :loading="loading" :error="error" :empty="!items.length" @retry="reload" />
    <div v-if="!loading && !error" class="message-list">
      <MessageCard v-for="message in items" :key="message.id" :message="message">
        <ClassificationSummary :message="message" />
        <AnnotationForm :id="message.id" @saved="saved" />
      </MessageCard>
    </div>
    <PaginationBar v-model:page="page" :pages="pages" :total="total" :loading="loading" />
  </section>
</template>
