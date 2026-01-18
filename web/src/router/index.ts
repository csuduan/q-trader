import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '总览' }
  },
  {
    path: '/account',
    name: 'Account',
    component: () => import('@/views/Account.vue'),
    meta: { title: '账户' }
  },
  {
    path: '/rotation',
    name: 'Rotation',
    component: () => import('@/views/Rotation.vue'),
    meta: { title: '换仓' }
  },
  {
    path: '/system',
    name: 'System',
    component: () => import('@/views/System.vue'),
    meta: { title: '系统' }
  },
  {
    path: '/logs',
    name: 'Logs',
    component: () => import('@/views/LogViewer.vue'),
    meta: { title: '日志' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  // 设置页面标题
  document.title = `${to.meta.title || 'Q-Trader'} - 交易管理系统`
  next()
})

export default router
