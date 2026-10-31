<script setup>
import { auth } from './stores/auth.js'
</script>

<template>
  <div v-if="auth.checking" class="loading-screen" role="status">正在加载校园留言…</div>
  <RouterView v-else />
</template>
