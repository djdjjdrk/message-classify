<script setup>
import { useRouter } from 'vue-router'
import { auth, signOut } from '../stores/auth.js'

const router = useRouter()
function logout() {
  signOut()
  router.replace('/login')
}
</script>

<template>
  <header class="app-header">
    <RouterLink class="brand" to="/messages"><span class="brand-mark">言</span>校园留言</RouterLink>
    <nav aria-label="主导航">
      <RouterLink to="/messages">留言管理</RouterLink>
      <template v-if="auth.user?.role === 'admin'">
        <RouterLink to="/classification">分类标注</RouterLink>
        <RouterLink to="/review">留言审核</RouterLink>
      </template>
    </nav>
    <div class="account">
      <span>{{ auth.user?.nickname }}<small>{{ auth.user?.username }}</small></span>
      <button class="quiet" @click="logout">退出</button>
    </div>
  </header>
  <main class="workspace"><RouterView /></main>
  <footer>校园留言分类与垃圾信息识别系统</footer>
</template>
