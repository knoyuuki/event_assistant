import { createRouter, createWebHistory } from 'vue-router'
import BrowseView from '../views/BrowseView.vue'
import TestView from '../views/TestView.vue'
import PersonManageView from '../views/PersonManageView.vue'
import DeptManageView from '../views/DeptManageView.vue'
import MeetingView from '../views/MeetingView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
    },
    {
      path: '/departments',
      name: 'departments',
      component: DeptManageView,
    },
    {
      path: '/meetings',
      name: 'meetings',
      component: MeetingView,
    },
  ],
})

export default router
