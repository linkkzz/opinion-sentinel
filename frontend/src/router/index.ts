import { createRouter, createWebHistory } from 'vue-router'
import EntryView from '../views/EntryView.vue'
import AdminTasksView from '../views/admin/AdminTasksView.vue'
import AdminTaskDetailView from '../views/admin/AdminTaskDetailView.vue'
import AccountsView from '../views/admin/AccountsView.vue'
import DashboardView from '../views/dashboard/DashboardView.vue'
import TaskScreenView from '../views/dashboard/TaskScreenView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: EntryView },
    { path: '/admin', component: AdminTasksView },
    { path: '/admin/tasks/:id', component: AdminTaskDetailView },
    { path: '/admin/accounts', component: AccountsView },
    { path: '/dashboard', component: DashboardView },
    { path: '/dashboard/tasks/:id', component: TaskScreenView },
  ],
})

