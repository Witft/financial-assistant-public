import { createRouter, createWebHistory } from 'vue-router'
import UploadPage from '@/views/UploadPage.vue'
import DashboardPage from '@/views/DashboardPage.vue'
import ReviewPage from '@/views/ReviewPage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'upload',
      component: UploadPage
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardPage
    },
    {
      path: '/review',
      name: 'review',
      component: ReviewPage
    }
  ]
})

export default router
