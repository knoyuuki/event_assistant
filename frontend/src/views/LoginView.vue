<template>
  <div class="login-page">
    <div class="login-card">
      <h2 class="login-title">📋 会务助手</h2>
      <p class="login-sub">请登录后使用</p>
      <form @submit.prevent="submit">
        <div class="form-item">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            placeholder="请输入用户名"
            required
          />
        </div>
        <div class="form-item">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入密码"
            required
          />
        </div>
        <p v-if="error" class="login-error">{{ error }}</p>
        <button type="submit" class="login-btn" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login, setToken, setStoredUser } from '../api'

const route = useRoute()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = await login(username.value.trim(), password.value)
    const { token, user } = res.data.data
    setToken(token)
    setStoredUser(user)
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (e: any) {
    error.value = e.response?.data?.detail || '登录失败，请稍后再试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}
.login-card {
  width: 360px;
  background: #fff;
  border-radius: 12px;
  padding: 36px 32px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
}
.login-title {
  text-align: center;
  color: #1a1a2e;
  margin-bottom: 4px;
}
.login-sub {
  text-align: center;
  color: #888;
  font-size: 13px;
  margin-bottom: 24px;
}
.form-item {
  margin-bottom: 16px;
}
.form-item label {
  display: block;
  font-size: 13px;
  color: #555;
  margin-bottom: 6px;
}
.form-item input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}
.form-item input:focus {
  border-color: #1a1a2e;
}
.login-error {
  color: #e74c3c;
  font-size: 13px;
  margin-bottom: 12px;
}
.login-btn {
  width: 100%;
  padding: 11px;
  background: #1a1a2e;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  margin-top: 4px;
}
.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
