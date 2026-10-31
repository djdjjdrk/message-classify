<script setup>
defineProps({ loading: Boolean, error: String, empty: Boolean })
defineEmits(['retry'])
</script>

<template>
  <div v-if="error" class="notice error" role="alert">{{ error }} <button @click="$emit('retry')">重试</button></div>
  <p v-else-if="loading" class="empty-state" role="status">正在加载…</p>
  <p v-else-if="empty" class="empty-state">暂无留言。</p>
</template>
