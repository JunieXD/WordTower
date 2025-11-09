const DefaultLayout = () => import('@/layouts/DefaultLayout.vue')
const HomeView = () => import('@/views/HomeView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const LibraryView = () => import('@/views/LibraryView.vue')
const ProfileView = () => import('@/views/ProfileView.vue')
const NotFoundView = () => import('@/views/NotFoundView.vue')
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    component: DefaultLayout,
    meta: { requiresAuth: true }, // 父路由设置，所有子路由继承
    children: [
      { path: '', redirect: { name: 'home' } },
      { path: 'home', name: 'home', component: HomeView },
      { path: 'library', name: 'library', component: LibraryView },
      { path: 'profile', name: 'profile', component: ProfileView },
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
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    authStore.initToken()
  }
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
})

export default router
