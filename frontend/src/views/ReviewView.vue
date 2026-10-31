<script setup>
import { computed, ref } from 'vue'
import { getPendingReviews } from '../api/review.js'
import { usePagedList } from '../composables/usePagedList.js'
import ClassificationSummary from '../components/ClassificationSummary.vue'
import ListStatus from '../components/ListStatus.vue'
import MessageCard from '../components/MessageCard.vue'
import PaginationBar from '../components/PaginationBar.vue'
import ReviewForm from '../components/ReviewForm.vue'

const endpoint = computed(() => getPendingReviews)
const { items, page, total, pages, loading, error, reload } = usePagedList(endpoint)
const notice = ref('')
function saved(message) {
  notice.value = message
  reload()
}
</script>

<template>
  <div class="page-heading"><div><p class="eyebrow">MODERATION</p><h1>留言审核</h1><p class="muted">决定待审核留言是否公开。通过后公开，驳回时需要填写原因。</p></div><button :disabled="loading" @click="reload">刷新列表</button></div>
  <p v-if="notice" class="notice success" role="status">{{ notice }}</p>
  <section class="list-section" :aria-busy="loading">
    <ListStatus :loading="loading" :error="error" :empty="!items.length" @retry="reload" />
    <div v-if="!loading && !error" class="message-list">
      <MessageCard v-for="message in items" :key="message.id" :message="message">
        <ClassificationSummary :message="message" />
        <ReviewForm :id="message.id" @saved="saved" />
      </MessageCard>
    </div>
    <PaginationBar v-model:page="page" :pages="pages" :total="total" :loading="loading" />
  </section>
</template>
