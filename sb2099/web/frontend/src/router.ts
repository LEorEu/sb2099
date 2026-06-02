import { createRouter, createWebHistory } from 'vue-router'
import { useAdminStore } from '@/stores/admin'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/barrage', name: 'barrage', component: () => import('@/views/BarrageView.vue') },
    { path: '/live', name: 'live', component: () => import('@/views/LiveView.vue') },

    {
      path: '/admin/login', name: 'admin-login',
      component: () => import('@/views/admin/AdminLogin.vue'),
      meta: { admin: true, public: true },
    },
    {
      path: '/admin', component: () => import('@/views/admin/AdminLayout.vue'),
      meta: { admin: true },
      children: [
        { path: '', redirect: '/admin/settings' },
        { path: 'settings', name: 'admin-settings', component: () => import('@/views/admin/AdminSettings.vue') },
        { path: 'tags', name: 'admin-tags', component: () => import('@/views/admin/AdminTags.vue') },
        { path: 'pending', name: 'admin-pending', component: () => import('@/views/admin/AdminPending.vue') },
        { path: 'reports', name: 'admin-reports', component: () => import('@/views/admin/AdminReports.vue') },
        { path: 'trash', name: 'admin-trash', component: () => import('@/views/admin/AdminTrash.vue') },
        { path: 'live-hot', name: 'admin-live-hot', component: () => import('@/views/admin/AdminLiveHot.vue') },
        { path: 'live-hot/:id', name: 'admin-live-hot-detail', component: () => import('@/views/admin/AdminLiveHotDetail.vue') },
        { path: 'stats', name: 'admin-stats', component: () => import('@/views/admin/AdminStats.vue') },
      ],
    },

    { path: '/:pathMatch(.*)*', name: 'notfound', component: () => import('@/views/NotFoundView.vue') },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

// 后台守卫：受保护的 admin 路由需登录态；未登录跳 /admin/login，已登录访问登录页跳设置页。
router.beforeEach(async (to) => {
  if (!to.meta.admin) return true
  const store = useAdminStore()
  const authed = store.checked ? store.authed : await store.check()
  if (to.meta.public) {
    return authed ? { name: 'admin-settings' } : true
  }
  return authed ? true : { name: 'admin-login', query: { next: to.fullPath } }
})
