<script setup>
defineProps({ page: Number, pages: Number, total: Number, loading: Boolean })
defineEmits(['update:page'])
</script>

<template>
  <div class="pagination">
    <span class="muted">共 {{ total }} 条 · 第 {{ page }} / {{ pages }} 页</span>
    <div class="actions">
      <button :disabled="loading || page <= 1" @click="$emit('update:page', page - 1)">上一页</button>
      <button :disabled="loading || page >= pages" @click="$emit('update:page', page + 1)">下一页</button>
    </div>
  </div>
</template>
