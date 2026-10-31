<script setup>
import { ref } from 'vue'
import { deleteMessage } from '../api/messages.js'

const props = defineProps({ id: Number })
const emit = defineEmits(['deleted'])
const saving = ref(false)
const error = ref('')
const confirmation = ref(null)
async function remove() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    await deleteMessage(props.id)
    confirmation.value.open = false
    emit('deleted')
  } catch (failure) {
    error.value = failure.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <details ref="confirmation" class="delete-confirm">
    <summary>删除留言</summary>
    <div class="confirmation">
      <span>确认删除这条留言？</span>
      <button class="danger" :disabled="saving" @click="remove">{{ saving ? '正在删除…' : '确认删除' }}</button>
      <button :disabled="saving" @click="confirmation.open = false">取消</button>
    </div>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
  </details>
</template>
