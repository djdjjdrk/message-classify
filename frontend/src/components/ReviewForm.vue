<script setup>
import { ref } from 'vue'
import { reviewMessage } from '../api/review.js'

const props = defineProps({ id: Number })
const emit = defineEmits(['saved'])
const comment = ref('')
const saving = ref(false)
const error = ref('')
async function submit(decision) {
  if (saving.value) return
  error.value = ''
  if (decision === 'rejected' && !comment.value.trim()) {
    error.value = '驳回时请填写原因'
    return
  }
  saving.value = true
  try {
    await reviewMessage(props.id, { decision, comment: comment.value })
    emit('saved', decision === 'approved' ? '留言已通过审核并公开。' : '留言已驳回。')
  } catch (failure) {
    error.value = failure.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="review-form" @submit.prevent="submit($event.submitter?.value || 'approved')">
    <label>审核说明（驳回时必填）<textarea v-model="comment" rows="2" maxlength="500" :disabled="saving" /></label>
    <div class="actions"><button class="primary" value="approved" :disabled="saving">{{ saving ? '正在保存…' : '通过并公开' }}</button><button value="rejected" :disabled="saving">驳回</button></div>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
  </form>
</template>
