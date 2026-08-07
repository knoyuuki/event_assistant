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
        <router-link to="/persons" class="nav-link" active-class="nav-link--active">
          人员管理
        </router-link>
        <router-link to="/departments" class="nav-link" active-class="nav-link--active">
          部门管理
        </router-link>
        <router-link to="/meetings" class="nav-link" active-class="nav-link--active">
          会议排序
        </router-link>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
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
