<template>
  <el-container class="app-container">
    <el-aside v-if="route.path !== '/login'" width="200px" class="sidebar">
      <div class="logo">
        <h2>IE造价审报平台</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><Monitor /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/templates">
          <el-icon><Document /></el-icon>
          <span>模板管理</span>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/reports">
          <el-icon><Files /></el-icon>
          <span>报告管理</span>
        </el-menu-item>
        <el-sub-menu v-if="isAdmin" index="system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/settings">
            <el-icon><Tools /></el-icon>
            <span>系统设置</span>
          </el-menu-item>
          <el-menu-item index="/logs">
            <el-icon><List /></el-icon>
            <span>操作日志</span>
          </el-menu-item>
          <el-menu-item index="/dictionary">
            <el-icon><Collection /></el-icon>
            <span>数据字典</span>
          </el-menu-item>
          <el-menu-item index="/backup">
            <el-icon><FolderOpened /></el-icon>
            <span>数据备份</span>
          </el-menu-item>
          <el-menu-item index="/users">
            <el-icon><UserFilled /></el-icon>
            <span>账号管理</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header v-if="route.path !== '/login'" class="header">
        <div class="header-content">
          <span>工程造价审报自动生成平台</span>
        </div>
        <div v-if="currentUser" class="header-user">
          <span class="user-name">{{ currentUser.display_name || currentUser.username }}</span>
          <el-tag size="small" :type="currentUser.role === 'admin' ? 'danger' : 'info'">
            {{ currentUser.role === 'admin' ? '管理员' : '员工' }}
          </el-tag>
          <el-button type="danger" size="small" link @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>

      <el-main class="main-content" :class="{ 'login-main': route.path === '/login' }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <!-- 服务停止遮罩 -->
  <div v-if="serviceDown" class="service-down-overlay">
    <div class="service-down-modal">
      <el-icon class="down-icon"><WarningFilled /></el-icon>
      <h2>服务已停止</h2>
      <p>检测到后端服务已关闭。</p>
      <p class="hint">请关闭此页面，或联系管理员重启服务。</p>
      <el-button type="primary" @click="tryClosePage">关闭页面</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Monitor, Document, Files, Setting, Tools, List, Collection, FolderOpened, UserFilled, WarningFilled
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const isAdmin = ref(false)
const currentUser = ref<any>(null)

// 服务健康检测：fetch 轮询 /api/health，连续 2 次失败显示遮罩
// 用原生 fetch 绕过 axios 响应拦截器，避免每次失败弹 ElMessage 错误
const serviceDown = ref(false)
let healthTimer: number | null = null
let failCount = 0

const checkHealth = async () => {
  try {
    const res = await fetch('/api/health', { signal: AbortSignal.timeout(5000) })
    if (res.ok) {
      failCount = 0
      serviceDown.value = false
    } else {
      throw new Error('not ok')
    }
  } catch {
    failCount++
    if (failCount >= 2) serviceDown.value = true
  }
}

const tryClosePage = () => {
  window.close()
  // 浏览器安全限制：JS 无法关闭用户手动打开的标签页，提示手动关闭
  setTimeout(() => {
    ElMessage.warning('浏览器限制了自动关闭，请手动关闭此标签页（Ctrl+W）')
  }, 300)
}

const startHealthCheck = () => {
  if (!healthTimer) healthTimer = window.setInterval(checkHealth, 3000)
}
const stopHealthCheck = () => {
  if (healthTimer) { clearInterval(healthTimer); healthTimer = null }
  failCount = 0
  serviceDown.value = false
}

// 子路由（如 /projects/123）高亮父菜单
const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/projects')) return '/projects'
  return path
})

const checkAdmin = () => {
  try {
    const userStr = localStorage.getItem('user')
    if (userStr) {
      const user = JSON.parse(userStr)
      isAdmin.value = user.role === 'admin'
      currentUser.value = user
    } else {
      isAdmin.value = false
      currentUser.value = null
    }
  } catch {
    isAdmin.value = false
    currentUser.value = null
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  currentUser.value = null
  isAdmin.value = false
  ElMessage.success('已退出登录')
  router.push('/login')
}

onMounted(() => {
  checkAdmin()
  // 登录页不轮询，避免未登录时无意义请求
  if (route.path !== '/login') startHealthCheck()
})

onUnmounted(() => {
  stopHealthCheck()
})

watch(() => route.path, (newPath) => {
  checkAdmin()
  if (newPath === '/login') {
    stopHealthCheck()
  } else {
    startHealthCheck()
  }
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Microsoft YaHei', Arial, sans-serif;
}

.app-container {
  height: 100vh;
}

.sidebar {
  background: #304156;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #2b3a4a;
}

.logo h2 {
  font-size: 18px;
  color: #fff;
}

.sidebar-menu {
  border-right: none;
  background: #304156;
}

.sidebar-menu .el-menu-item {
  color: #bfcbd9;
}

.sidebar-menu .el-menu-item:hover {
  background: #263445;
  color: #fff;
}

.sidebar-menu .el-menu-item.is-active {
  background: #409eff;
  color: #fff;
}

.header {
  background: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content {
  font-size: 18px;
  font-weight: bold;
  color: #333;
}

.header-user {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-user .user-name {
  font-size: 14px;
  color: #333;
}

.main-content {
  background: #f0f2f5;
  padding: 20px;
}

.login-main {
  background: #fff;
  padding: 0;
}

.service-down-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.service-down-modal {
  background: #fff;
  padding: 40px 50px;
  border-radius: 8px;
  text-align: center;
  max-width: 420px;
}

.service-down-modal .down-icon {
  font-size: 56px;
  color: #f56c6c;
  margin-bottom: 16px;
}

.service-down-modal h2 {
  color: #f56c6c;
  margin-bottom: 12px;
}

.service-down-modal p {
  color: #606266;
  margin-bottom: 8px;
}

.service-down-modal .hint {
  color: #909399;
  font-size: 13px;
  margin-bottom: 24px;
}
</style>
