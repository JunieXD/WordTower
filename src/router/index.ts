const DefaultLayout = () => import('@/layouts/DefaultLayout.vue')
const HomeView = () => import('@/views/HomeView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const LibraryView = () => import('@/views/LibraryView.vue')
const LibraryEditView = () => import('@/views/LibraryEditView.vue')
const ProfileView = () => import('@/views/ProfileView.vue')
const NotFoundView = () => import('@/views/NotFoundView.vue')
const UpgradeView = () => import('@/views/UpgradeView.vue')
const LeaderboardView = () => import('@/views/LeaderboardView.vue')
const CombatView = () => import('@/views/CombatView.vue')
const CheckoutView = () => import('@/views/CheckoutView.vue')
const CombatLayout = () => import('@/layouts/CombatLayout.vue')
import { createRouter, createWebHistory } from 'vue-router'
import { useUserProfileStore } from '@/stores/userProfile'
import { useNotificationStore } from '@/stores/notification'
import { useLibraryStore } from '@/stores/library'

const routes = [
  {
    path: '/',
    component: DefaultLayout,
    meta: { requiresAuth: true }, // 父路由设置，所有子路由继承
    children: [
      { path: '', redirect: { name: 'home' } },
      { path: 'home', name: 'home', component: HomeView },
      {
        path: 'library',
        name: 'library',
        component: LibraryView,
      },
      { path: 'library/edit/:id', name: 'library-edit', component: LibraryEditView },
      { path: 'upgrade', name: 'upgrade', component: UpgradeView },
      { path: 'leaderboard', name: 'leaderboard', component: LeaderboardView },
      { path: 'profile', name: 'profile', component: ProfileView },
    ],
  },
  {
    path: '/combat',
    component: CombatLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'combat', component: CombatView },
      { path: 'checkout', name: 'checkout', component: CheckoutView },
    ],
  },
  { path: '/login', name: 'login', component: LoginView },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFoundView,
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async (to) => {
  if (to.meta.requiresAuth) {
    const userProfileStore = useUserProfileStore()
    if (!userProfileStore.profile) {
      const profile = await userProfileStore.getProfile(true)
      if (!profile) {
        const notificationStore = useNotificationStore()
        notificationStore.addNotification({
          title: '登录已过期',
          description: '登录已过期，请重新登录',
          variant: 'destructive',
          duration: 4000,
        })
        return { name: 'login', query: { redirect: to.fullPath } }
      }
    }
  }

  // Combat 页面路由守卫：检查选中的单词数量
  if (to.name === 'combat') {
    const libraryStore = useLibraryStore()
    const notificationStore = useNotificationStore()

    const count = await libraryStore.getSelectedWordsCount()
    if (count < 10) {
      notificationStore.addNotification({
        title: '无法进入闯塔',
        description: `您选择的单词数量不足（当前 ${count} 个，至少需要 10 个），请先在词库中选择更多单词`,
        variant: 'destructive',
        duration: 5000,
      })
      return { name: 'library' }
    }
  }
})

export default router
