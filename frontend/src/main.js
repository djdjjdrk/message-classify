import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.js'
import { setUnauthorizedHandler } from './api/request.js'
import { signOut } from './stores/auth.js'
import './assets/main.css'

setUnauthorizedHandler(() => {
  signOut('登录已失效，请重新登录')
  router.replace('/login')
})
createApp(App).use(router).mount('#app')
