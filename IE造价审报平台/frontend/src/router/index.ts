import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Workbench',
    component: () => import('../views/Workbench.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/projects',
    name: 'Projects',
    component: () => import('../views/Projects.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/projects/:id',
    name: 'ProjectDetail',
    component: () => import('../views/ProjectDetail.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/templates',
    name: 'Templates',
    component: () => import('../views/Templates.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/reports',
    name: 'Reports',
    component: () => import('../views/Reports.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/backup',
    name: 'Backup',
    component: () => import('../views/system/Backup.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/dictionary',
    name: 'Dictionary',
    component: () => import('../views/system/Dictionary.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/system/Settings.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/logs',
    name: 'OperationLogs',
    component: () => import('../views/system/OperationLogs.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/users',
    name: 'AccountManagement',
    component: () => import('../views/system/AccountManagement.vue'),
    meta: { requiresAuth: true, requiresAdmin: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('token')

  // 检查是否需要登录
  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
    return
  }

  // 如果已登录且访问登录页，重定向到首页
  if (to.path === '/login' && token) {
    next('/')
    return
  }

  // 管理员权限校验
  if (to.meta.requiresAdmin) {
    const userStr = localStorage.getItem('user')
    if (!userStr) {
      // token 存在但 user 信息丢失，拒绝放行，避免绕过前端校验
      next('/')
      return
    }
    try {
      const user = JSON.parse(userStr)
      if (user.role !== 'admin') {
        next('/')
        return
      }
    } catch {
      // 用户信息解析失败，拒绝放行
      next('/')
      return
    }
  }

  next()
})

export default router
