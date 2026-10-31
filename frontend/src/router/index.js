import { createRouter, createWebHashHistory } from 'vue-router'
import { auth, initializeAuth } from '../stores/auth.js'
import MainLayout from '../layouts/MainLayout.vue'
import LoginView from '../views/LoginView.vue'
import RegisterView from '../views/RegisterView.vue'
import MessagesView from '../views/MessagesView.vue'
import ClassificationView from '../views/ClassificationView.vue'
import ReviewView from '../views/ReviewView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { title: '登录', public: true } },
    { path: '/register', component: RegisterView, meta: { title: '注册', public: true } },
    {
      path: '/', component: MainLayout, redirect: '/messages', children: [
        { path: 'messages', component: MessagesView, meta: { title: '留言管理' } },
        { path: 'classification', component: ClassificationView, meta: { title: '分类标注', admin: true } },
        { path: 'review', component: ReviewView, meta: { title: '留言审核', admin: true } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/messages' },
  ],
})

router.beforeEach(async (to) => {
  await initializeAuth()
  if (!to.meta.public && !auth.user) return '/login'
  if (to.meta.public && auth.user) return '/messages'
  if (to.meta.admin && auth.user?.role !== 'admin') return '/messages'
  document.title = `${to.meta.title || '校园留言'} · 校园留言`
})

export default router
