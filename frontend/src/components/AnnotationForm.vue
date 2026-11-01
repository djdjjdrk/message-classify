<script setup>
import { ref } from 'vue'
import { annotateMessage } from '../api/classification.js'

const props = defineProps({ id: Number })
const emit = defineEmits(['saved'])
const label = ref('')
const reason = ref('')
const saving = ref(false)
const error = ref('')
async function submit() {
  if (saving.value) return
  error.value = ''
  if (!label.value) { error.value = '请先选择人工标签'; return }
  saving.value = true
  try {
    const result = await annotateMessage(props.id, { label: label.value, reason: reason.value })
    label.value = ''
    reason.value = ''
    emit('saved', result.changed ? '人工标注已保存，审核状态未改变。' : '人工标签未变化，无需重复保存。')
  } catch (failure) {
    error.value = failure.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="inline-form" @submit.prevent="submit">
    <label>人工标签<select v-model="label" required :disabled="saving"><option disabled value="">请选择</option><option value="normal">普通</option><option value="spam">垃圾</option></select></label>
    <label class="flex-grow">标注原因（选填）<input v-model="reason" maxlength="500" :disabled="saving" /></label>
    <button :disabled="saving">{{ saving ? '正在保存…' : '保存标注' }}</button>
    <p v-if="error" class="notice error form-error" role="alert">{{ error }}</p>
  </form>
</template>
