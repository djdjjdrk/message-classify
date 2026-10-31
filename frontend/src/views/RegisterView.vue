<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { register } from '../api/auth.js'

const router = useRouter()
const form = reactive({ username: '', nickname: '', password: '', confirm: '' })
const error = ref('')
const saving = ref(false)
async function submit() {
  if (saving.value) return
  error.value = ''
  if (form.password !== form.confirm) {
    error.value = '两次输入的密码不一致'
    return
  }
  saving.value = true
  try {
    await register({ username: form.username.trim(), nickname: form.nickname.trim() || null, password: form.password })
    await router.replace({ path: '/login', query: { registered: '1' } })
  } catch (failure) {
    error.value = failure.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <main class="auth-page register-page">
    <section class="auth-card">
      <RouterLink class="back-link" to="/login">← 返回登录</RouterLink>
      <h1>加入校园留言</h1><p class="muted">创建一个普通用户账号</p>
      <p v-if="error" class="notice error" role="alert">{{ error }}</p>
      <form @submit.prevent="submit">
        <label>用户名<input v-model="form.username" name="username" autocomplete="username" required minlength="3" maxlength="20" /></label>
        <label>昵称 <span class="muted">选填</span><input v-model="form.nickname" name="nickname" autocomplete="nickname" maxlength="20" /></label>
        <label>密码<input v-model="form.password" name="password" type="password" autocomplete="new-password" required minlength="8" maxlength="32" /></label>
        <label>确认密码<input v-model="form.confirm" name="confirm" type="password" autocomplete="new-password" required minlength="8" maxlength="32" /></label>
        <button class="primary full-width" :disabled="saving">{{ saving ? '正在注册…' : '注册' }}</button>
      </form>
    </section>
  </main>
</template>
