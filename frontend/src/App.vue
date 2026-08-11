<template>
  <div id="app-container">
    <header class="app-header">
      <h1 class="app-title">📋 会务助手</h1>
      <nav class="app-nav">
        <router-link to="/browse" class="nav-link" active-class="nav-link--active">
          浏览模式
        </router-link>
        <router-link to="/test" class="nav-link" active-class="nav-link--active">
          认人测试
        </router-link>
        <router-link v-if="isAdmin" to="/persons" class="nav-link" active-class="nav-link--active">
          人员管理
        </router-link>
        <router-link v-if="isAdmin" to="/departments" class="nav-link" active-class="nav-link--active">
          部门管理
        </router-link>
        <router-link to="/meetings" class="nav-link" active-class="nav-link--active">
          会议排序
        </router-link>
      </nav>
      <div v-if="user" class="app-user">
        <span class="user-name">{{ user.display_name || user.username }}</span>
        <span class="user-role" :class="'role-' + user.role">{{ user.role === 'admin' ? '管理员' : '游客' }}</span>
        <button class="logout-btn" @click="doLogout">退出</button>
      </div>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchMe, logout, clearToken, getToken, getStoredUser, type UserInfo } from './api'

const router = useRouter()
const user = ref<UserInfo | null>(getStoredUser())
const isAdmin = computed(() => user.value?.role === 'admin')

onMounted(async () => {
  if (!getToken()) return
  try {
    const res = await fetchMe()
    user.value = res.data.data
  } catch {
    /* 401 由拦截器统一处理 */
  }
})

async function doLogout() {
  try {
    await logout()
  } catch {
    /* 忽略 */
  }
  clearToken()
  user.value = null
  router.push('/login')
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei',
    sans-serif;
  background: #f0f2f5;
  color: #333;
  min-height: 100vh;
}

#app-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 0 16px 40px;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 0;
  border-bottom: 1px solid #e0e0e0;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.app-title {
  font-size: 24px;
  font-weight: 700;
  color: #1a1a2e;
}

.app-nav {
  display: flex;
  gap: 8px;
}

.nav-link {
  text-decoration: none;
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  color: #555;
  background: #fff;
  border: 1px solid #d9d9d9;
  transition: all 0.2s;
}

.nav-link:hover {
  color: #1677ff;
  border-color: #1677ff;
}

.nav-link--active {
  color: #fff;
  background: #1677ff;
  border-color: #1677ff;
}

.app-main {
  min-height: 400px;
}
</style>

<style scoped>
.app-user {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}
.user-name {
  color: #1a1a2e;
  font-weight: 600;
}
.user-role {
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
}
.role-admin {
  background: #1a1a2e;
  color: #fff;
}
.role-user {
  background: #e8e8e8;
  color: #555;
}
.logout-btn {
  border: 1px solid #d9d9d9;
  background: #fff;
  color: #555;
  border-radius: 8px;
  padding: 4px 12px;
  cursor: pointer;
  font-size: 13px;
}
.logout-btn:hover {
  border-color: #e74c3c;
  color: #e74c3c;
}
</style>
