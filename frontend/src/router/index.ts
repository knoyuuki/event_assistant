import { createRouter, createWebHistory } from 'vue-router'
import BrowseView from '../views/BrowseView.vue'
import TestView from '../views/TestView.vue'
import PersonManageView from '../views/PersonManageView.vue'
import DeptManageView from '../views/DeptManageView.vue'
import MeetingView from '../views/MeetingView.vue'
import LoginView from '../views/LoginView.vue'
import { getToken, getStoredUser } from '../api'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { public: true },
    },
    {
      path: '/',
      redirect: '/browse',
    },
    {
      path: '/browse',
      name: 'browse',
      component: BrowseView,
    },
    {
      path: '/test',
      name: 'test',
      component: TestView,
    },
    {
      path: '/persons',
      name: 'persons',
      component: PersonManageView,
      meta: { adminOnly: true },
    },
    {
      path: '/departments',
      name: 'departments',
      component: DeptManageView,
      meta: { adminOnly: true },
    },
    {
      path: '/meetings',
      name: 'meetings',
      component: MeetingView,
    },
  ],
})

// 登录守卫：未登录只能访问 /login；管理页仅限 admin
router.beforeEach((to) => {
  if (to.meta.public) return true
  if (!getToken()) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.meta.adminOnly && getStoredUser()?.role !== 'admin') {
    return { path: '/browse' }
  }
  return true
})

export default router
