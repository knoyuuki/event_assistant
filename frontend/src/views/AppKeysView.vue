<template>
  <div class="keys-page">
    <div class="page-head">
      <h2>🔑 外部应用密钥管理</h2>
      <button class="btn btn-primary" @click="openCreate">+ 新建应用密钥</button>
    </div>

    <p v-if="!keys.length" class="empty-tip">暂无应用密钥，点击右上角创建。</p>

    <table v-else class="keys-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>应用名称</th>
          <th>App ID</th>
          <th>状态</th>
          <th>过期时间</th>
          <th>最近调用</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="k in keys" :key="k.id">
          <td>{{ k.id }}</td>
          <td>
            {{ k.app_name }}
            <div v-if="k.description" class="desc">{{ k.description }}</div>
          </td>
          <td><code class="app-id">{{ k.app_id }}</code></td>
          <td>
            <span :class="k.status === 1 ? 'badge badge-on' : 'badge badge-off'">
              {{ k.status === 1 ? '启用' : '禁用' }}
            </span>
          </td>
          <td>{{ k.expires_at || '永久' }}</td>
          <td>{{ k.last_called_at || '—' }}</td>
          <td>{{ k.created_at }}</td>
          <td class="ops">
            <button class="btn btn-sm" @click="toggleStatus(k)">
              {{ k.status === 1 ? '禁用' : '启用' }}
            </button>
            <button class="btn btn-sm" @click="doRotate(k)">轮换</button>
            <button class="btn btn-sm" @click="openLogs(k)">日志</button>
            <button class="btn btn-sm btn-danger" @click="doDelete(k)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 新建弹窗 -->
    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="modal">
        <h3>新建应用密钥</h3>
        <label>应用名称 *</label>
        <input v-model="form.app_name" placeholder="如：智能体会务助手" />
        <label>备注</label>
        <input v-model="form.description" placeholder="用途说明（可选）" />
        <label>过期时间（可选）</label>
        <input v-model="form.expires_at" type="date" />
        <div class="modal-ops">
          <button class="btn" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" :disabled="creating" @click="doCreate">
            {{ creating ? '创建中...' : '创建' }}
          </button>
        </div>
        <p v-if="formError" class="err">{{ formError }}</p>
      </div>
    </div>

    <!-- 密钥展示弹窗（仅一次） -->
    <div v-if="secretResult" class="modal-mask" @click.self="secretResult = null">
      <div class="modal">
        <h3>{{ secretResult.title }}</h3>
        <p class="secret-warn">⚠️ 密钥仅展示一次，请立即复制并妥善保存！</p>
        <p v-if="secretResult.app_id" class="kv">App ID：<code>{{ secretResult.app_id }}</code></p>
        <p class="kv">App Secret：</p>
        <div class="secret-box">
          <code>{{ secretResult.secret }}</code>
          <button class="btn btn-sm" @click="copySecret">复制</button>
        </div>
        <div class="modal-ops">
          <button class="btn btn-primary" @click="secretResult = null">我已保存</button>
        </div>
      </div>
    </div>

    <!-- 调用日志弹窗 -->
    <div v-if="logsKey" class="modal-mask" @click.self="logsKey = null">
      <div class="modal modal-wide">
        <h3>调用日志：{{ logsKey.app_name }}（近 7 天，共 {{ logsTotal }} 条）</h3>
        <table v-if="logs.length" class="keys-table logs-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>方法</th>
              <th>路径</th>
              <th>状态</th>
              <th>IP</th>
              <th>耗时</th>
              <th>请求参数</th>
              <th>返回结果</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="l in logs" :key="l.id">
              <td class="nowrap">{{ l.created_at }}</td>
              <td>{{ l.method }}</td>
              <td class="nowrap">{{ l.path }}</td>
              <td :class="l.status_code >= 400 ? 'err' : ''">{{ l.status_code }}</td>
              <td>{{ l.caller_ip }}</td>
              <td>{{ l.duration_ms }}ms</td>
              <td class="truncate" :title="l.request_params">{{ l.request_params }}</td>
              <td class="truncate" :title="l.response_result">{{ l.response_result }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty-tip">近 7 天暂无调用记录。</p>
        <div class="modal-ops">
          <button class="btn btn-primary" @click="logsKey = null">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  fetchAppKeys, createAppKey, updateAppKey, rotateAppKey, deleteAppKey,
  fetchAppKeyLogs, type AppKeyItem, type AppKeyLog,
} from '../api'

const keys = ref<AppKeyItem[]>([])
const showCreate = ref(false)
const creating = ref(false)
const formError = ref('')
const form = ref({ app_name: '', description: '', expires_at: '' })
const secretResult = ref<{ title: string; app_id?: string; secret: string } | null>(null)
const logsKey = ref<AppKeyItem | null>(null)
const logs = ref<AppKeyLog[]>([])
const logsTotal = ref(0)

onMounted(load)

async function load() {
  try {
    const res = await fetchAppKeys()
    keys.value = res.data.data || []
  } catch (e: any) {
    alert(e.response?.data?.detail || '加载失败')
  }
}

function openCreate() {
  form.value = { app_name: '', description: '', expires_at: '' }
  formError.value = ''
  showCreate.value = true
}

async function doCreate() {
  if (!form.value.app_name.trim()) {
    formError.value = '应用名称不能为空'
    return
  }
  creating.value = true
  try {
    const res = await createAppKey({
      app_name: form.value.app_name.trim(),
      description: form.value.description.trim() || undefined,
      expires_at: form.value.expires_at ? `${form.value.expires_at}T00:00:00` : undefined,
    })
    showCreate.value = false
    secretResult.value = { title: '创建成功', app_id: res.data.app_id, secret: res.data.app_secret }
    await load()
  } catch (e: any) {
    formError.value = e.response?.data?.detail || '创建失败'
  } finally {
    creating.value = false
  }
}

async function toggleStatus(k: AppKeyItem) {
  const target = k.status === 1 ? 0 : 1
  await updateAppKey(k.id, { status: target })
  await load()
}

async function doRotate(k: AppKeyItem) {
  if (!confirm(`确定轮换「${k.app_name}」的密钥？旧密钥将立即失效。`)) return
  const res = await rotateAppKey(k.id)
  secretResult.value = { title: '轮换成功', app_id: k.app_id, secret: res.data.app_secret }
  await load()
}

async function doDelete(k: AppKeyItem) {
  if (!confirm(`确定删除「${k.app_name}」？其调用日志将一并删除。`)) return
  await deleteAppKey(k.id)
  await load()
}

async function openLogs(k: AppKeyItem) {
  logsKey.value = k
  logs.value = []
  logsTotal.value = 0
  const res = await fetchAppKeyLogs(k.id)
  logs.value = res.data.data.logs || []
  logsTotal.value = res.data.data.total || 0
}

async function copySecret() {
  try {
    await navigator.clipboard.writeText(secretResult.value!.secret)
    alert('已复制到剪贴板')
  } catch {
    alert('复制失败，请手动选择复制')
  }
}
</script>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.btn {
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 8px;
  padding: 6px 14px;
  cursor: pointer;
  font-size: 13px;
}
.btn-primary {
  background: #1a1a2e;
  color: #fff;
  border-color: #1a1a2e;
}
.btn-danger {
  color: #e74c3c;
  border-color: #e74c3c;
}
.btn-sm {
  padding: 3px 10px;
  font-size: 12px;
  margin-right: 4px;
}
.keys-table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  font-size: 13px;
}
.keys-table th,
.keys-table td {
  border-bottom: 1px solid #f0f0f0;
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
}
.keys-table th {
  background: #fafafa;
  color: #666;
  font-weight: 600;
  white-space: nowrap;
}
.desc {
  color: #999;
  font-size: 12px;
}
.app-id {
  font-size: 12px;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 4px;
}
.badge {
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
}
.badge-on {
  background: #e8f7ee;
  color: #1a9c54;
}
.badge-off {
  background: #fdecea;
  color: #d63031;
}
.ops {
  white-space: nowrap;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  width: 420px;
  max-height: 85vh;
  overflow: auto;
}
.modal-wide {
  width: 860px;
}
.modal label {
  display: block;
  font-size: 13px;
  color: #555;
  margin: 12px 0 6px;
}
.modal input {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  box-sizing: border-box;
}
.modal-ops {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
.secret-warn {
  color: #e67e22;
  font-size: 13px;
  margin: 8px 0;
}
.kv {
  font-size: 13px;
  margin: 6px 0;
}
.secret-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #1a1a2e;
  color: #7bed9f;
  padding: 10px 12px;
  border-radius: 8px;
  word-break: break-all;
}
.secret-box button {
  flex-shrink: 0;
}
.err {
  color: #e74c3c;
  font-size: 13px;
  margin-top: 10px;
}
.empty-tip {
  color: #999;
  padding: 24px 0;
  text-align: center;
}
.logs-table .nowrap {
  white-space: nowrap;
}
.logs-table .truncate {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.logs-table .err {
  color: #e74c3c;
  font-weight: 600;
}
</style>
