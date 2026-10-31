<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { auth, signIn } from '../stores/auth.js'

const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const saving = ref(false)

async function submit() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  auth.error = ''
  try {
    await signIn(username.value.trim(), password.value)
    await router.replace('/messages')
  } catch (failure) {
    error.value = failure.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-intro">
      <span class="brand-mark">言</span>
      <p class="eyebrow">CAMPUS MESSAGES</p>
      <h1>校园里的声音，<br />在这里相遇。</h1>
      <p class="muted">分享日常、提出问题，让每一条留言被认真看见。</p>
    </section>
    <section class="auth-card">
      <h2>登录</h2><p class="muted">欢迎回到校园留言</p>
      <p v-if="route.query.registered" class="notice success" role="status">注册成功，请使用新账号登录</p>
      <p v-if="error || auth.error" class="notice error" role="alert">{{ error || auth.error }}</p>
      <form @submit.prevent="submit">
        <label>用户名<input v-model="username" name="username" autocomplete="username" required minlength="3" maxlength="20" /></label>
        <label>密码<input v-model="password" name="password" type="password" autocomplete="current-password" required minlength="8" maxlength="32" /></label>
        <button class="primary full-width" :disabled="saving">{{ saving ? '正在登录…' : '登录' }}</button>
      </form>
      <p class="auth-link">还没有账号？<RouterLink to="/register">注册账号</RouterLink></p>
    </section>
  </main>
</template>
