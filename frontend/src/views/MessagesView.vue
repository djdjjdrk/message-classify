<script setup>
import { computed, ref } from 'vue'
import { getMyMessages, getPublicMessages, publishMessage } from '../api/messages.js'
import { usePagedList } from '../composables/usePagedList.js'
import DeleteButton from '../components/DeleteButton.vue'
import ListStatus from '../components/ListStatus.vue'
import MessageCard from '../components/MessageCard.vue'
import PaginationBar from '../components/PaginationBar.vue'

const scope = ref('mine')
const endpoint = computed(() => scope.value === 'mine' ? getMyMessages : getPublicMessages)
const { items, page, total, pages, loading, error, reload } = usePagedList(endpoint)
const content = ref('')
const saving = ref(false)
const publishError = ref('')
const notice = ref('')
async function publish() {
  if (saving.value) return
  publishError.value = ''
  notice.value = ''
  if (!content.value.trim()) {
    publishError.value = '留言内容不能为空'
    return
  }
  saving.value = true
  try {
    await publishMessage(content.value.trim())
    content.value = ''
    notice.value = '留言发布成功，审核通过后将公开展示。'
    if (scope.value !== 'mine' || page.value !== 1) {
      scope.value = 'mine'
      page.value = 1
    } else {
      await reload()
    }
  } catch (failure) {
    publishError.value = failure.message
  } finally {
    saving.value = false
  }
}
function deleted() {
  notice.value = '留言已删除'
  reload()
}
</script>

<template>
  <div class="page-heading"><div><p class="eyebrow">MESSAGE BOARD</p><h1>留言管理</h1></div></div>
  <section class="panel compose-panel">
    <h2>发布留言</h2><p class="muted">分享校园生活、提问或建议。审核通过后公开展示。</p>
    <form @submit.prevent="publish">
      <label class="sr-only" for="message-content">留言内容</label>
      <textarea id="message-content" v-model="content" rows="4" required maxlength="2000" placeholder="有什么想和大家分享的？" />
      <div class="compose-footer"><span class="muted">{{ content.length }} / 2000</span><button class="primary" :disabled="saving">{{ saving ? '正在发布…' : '发布留言' }}</button></div>
    </form>
    <p v-if="publishError" class="notice error" role="alert">{{ publishError }}</p>
  </section>
  <p v-if="notice" class="notice success" role="status">{{ notice }}</p>
  <section class="list-section" aria-label="留言列表" :aria-busy="loading">
    <div class="list-toolbar">
      <div class="switcher" role="group" aria-label="留言范围">
        <button :class="{ selected: scope === 'mine' }" :aria-pressed="scope === 'mine'" @click="scope = 'mine'; notice = ''">我的留言</button>
        <button :class="{ selected: scope === 'public' }" :aria-pressed="scope === 'public'" @click="scope = 'public'; notice = ''">公共留言</button>
      </div>
      <button :disabled="loading" @click="reload">刷新列表</button>
    </div>
    <ListStatus :loading="loading" :error="error" :empty="!items.length" @retry="reload" />
    <div v-if="!loading && !error" class="message-list">
      <MessageCard v-for="message in items" :key="`${scope}-${message.id}`" :message="message">
        <DeleteButton v-if="scope === 'mine' || message.can_delete" :id="message.id" @deleted="deleted" />
      </MessageCard>
    </div>
    <PaginationBar v-model:page="page" :pages="pages" :total="total" :loading="loading" />
  </section>
</template>
