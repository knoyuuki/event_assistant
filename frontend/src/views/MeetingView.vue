<template>
  <div class="meeting-manage">
    <div class="page-header">
      <h2 class="page-title">会议名单排序</h2>
      <div class="header-actions">
        <button class="btn btn-primary" @click="openCreate">+ 新建会议</button>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <div class="filter-item">
        <label class="filter-label">名称</label>
        <input v-model="filterSearch" class="filter-input" placeholder="搜索会议名称..." @keyup.enter="onFilterChange" />
      </div>
      <div class="filter-item">
        <label class="filter-label">日期从</label>
        <input v-model="filterDateFrom" type="date" class="filter-input filter-input--date" @change="onFilterChange" />
      </div>
      <div class="filter-item">
        <label class="filter-label">日期至</label>
        <input v-model="filterDateTo" type="date" class="filter-input filter-input--date" @change="onFilterChange" />
      </div>
      <div class="filter-item">
        <label class="filter-label">参会部门</label>
        <input v-model="filterDepartment" class="filter-input" placeholder="搜索部门..." @keyup.enter="onFilterChange" />
      </div>
      <div class="filter-item">
        <label class="filter-label">参会人员</label>
        <input v-model="filterPerson" class="filter-input" placeholder="搜索人员..." @keyup.enter="onFilterChange" />
      </div>
      <button class="btn btn-outline btn-sm" @click="onFilterChange">搜索</button>
      <button class="btn btn-outline btn-sm" @click="clearFilters">清除</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div class="meeting-list" v-if="meetings.length">
        <div v-for="m in meetings" :key="m.id" class="meeting-card" :class="{ 'meeting-card--expanded': expandedId === m.id }">
          <!-- Card header -->
          <div class="card-header" @click="toggleExpand(m.id)">
            <div class="card-title-row">
              <span class="card-toggle">{{ expandedId === m.id ? '▼' : '▶' }}</span>
              <span class="card-name">{{ m.name }}</span>
              <span class="card-meta">
                {{ formatDate(m.created_at) }}
                <template v-if="m.sorted_departments">
                  · {{ parsedDeptCount(m.sorted_departments) }}个部门
                </template>
                <template v-if="m.sorted_persons">
                  · {{ parsedPersonCount(m.sorted_persons) }}人
                </template>
                <span class="card-meta-basis" :title="sortBasisDetail(m)">· {{ sortBasisLabel(m) }}</span>
              </span>
            </div>
            <div class="card-actions" @click.stop>
              <button class="btn btn-sm btn-outline" @click="openDetail(m)">查看详情</button>
              <button class="btn btn-sm btn-outline" @click="openEdit(m)">编辑</button>
              <button class="btn btn-sm btn-outline" @click="handleResort(m.id)" :disabled="resortingId === m.id">
                {{ resortingId === m.id ? '排序中...' : '重新排序' }}
              </button>
              <button class="btn btn-sm btn-danger" @click="confirmDelete(m)">删除</button>
            </div>
          </div>

          <!-- Expanded preview -->
          <div class="card-body" v-if="expandedId === m.id">
            <div class="card-section" v-if="m.sorted_departments">
              <div class="card-section-title">📋 参会部门排序</div>
              <ol class="card-list">
                <li v-for="(dept, idx) in parseJson(m.sorted_departments)" :key="'d'+idx">
                  {{ typeof dept === 'string' ? dept : dept.name }}
                </li>
              </ol>
            </div>
            <div class="card-section" v-if="m.sorted_persons">
              <div class="card-section-title">👤 参会人员排序</div>
              <ol class="card-list">
                <li v-for="(p, idx) in parseJson(m.sorted_persons)" :key="'p'+idx">
                  <span>{{ p.name }}</span>
                  <span v-if="p.department" class="card-list-dept">{{ p.department }}</span>
                  <span v-if="p.position_title" class="card-list-level">{{ p.position_title }}</span>
                </li>
              </ol>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty">
        <p>暂无会议记录</p>
        <p class="empty-hint">点击"新建会议"按钮创建第一个会议名单</p>
      </div>
    </template>

    <!-- Create Meeting Modal -->
    <div class="modal-overlay" v-if="showCreateModal" @click.self="closeCreateModal">
      <div class="modal-panel">
        <h3 class="modal-title">{{ isEditing ? '编辑会议' : '新建会议' }}</h3>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">会议名称 <span class="required">*</span></label>
            <input v-model="createForm.name" class="form-input" placeholder="请输入会议名称，如：2025年1月月度例会" />
          </div>
          <div class="form-group">
            <label class="form-label">参会部门名单 <span class="form-label--optional">（可选）</span></label>
            <textarea
              v-model="createForm.input_departments"
              class="form-textarea"
              placeholder="请输入参会部门，支持顿号、中文逗号、英文逗号分隔&#10;如：财务部，人力部，办公室&#10;如仅填写人员名单，此处可留空，系统将自动识别"
              rows="4"
            ></textarea>
            <span class="form-hint">支持顿号（、）、中文逗号（，）、英文逗号（,）分隔；与人员名单至少填写一项</span>
          </div>
          <div class="form-group">
            <label class="form-label">参会人员名单 <span class="form-label--optional">（可选）</span></label>
            <textarea
              v-model="createForm.input_persons"
              class="form-textarea"
              placeholder="请输入参会人员姓名，支持顿号、中文逗号、英文逗号分隔&#10;如：张三，李四，王五"
              rows="3"
            ></textarea>
            <span class="form-hint">支持顿号（、）、中文逗号（，）、英文逗号（,）分隔；与部门名单至少填写一项，系统自动匹配排序</span>
          </div>
          <div class="form-group">
            <label class="form-label">排序依据</label>
            <div class="sort-basis-row">
              <label class="sort-basis-option">
                <input type="radio" value="current" v-model="sortBasis" />
                <span>当前部门排序</span>
              </label>
              <label class="sort-basis-option">
                <input type="radio" value="snapshot" v-model="sortBasis" />
                <span>保存的排序记录</span>
              </label>
            </div>
            <template v-if="sortBasis === 'snapshot'">
              <select v-if="snapshots.length" v-model="selectedSnapshotId" class="form-select">
                <option :value="null" disabled>-- 请选择排序存档 --</option>
                <option v-for="s in snapshots" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
              <span v-else class="form-hint">暂无排序存档，请先在「部门管理」中保存一份部门排序</span>
            </template>
            <span v-else class="form-hint">按部门管理中当前分类与部门的排列顺序进行排序</span>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeCreateModal">取消</button>
          <button class="btn btn-primary" @click="saveMeeting" :disabled="saving">
            {{ saving ? '保存中...' : (isEditing ? '保存修改' : '保存并排序') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Detail Popup Modal -->
    <div class="modal-overlay" v-if="detailMeeting" @click.self="closeDetail">
      <div class="modal-panel modal-panel--lg">
        <div class="detail-header">
          <h3 class="modal-title">{{ detailMeeting.name }}</h3>
          <span class="detail-date">{{ formatDate(detailMeeting.created_at) }}</span>
          <span class="detail-date">· 排序依据：{{ sortBasisLabel(detailMeeting) }}</span>
        </div>
        <div class="modal-body">
          <div class="detail-section" v-if="sortedDepts.length">
            <h4 class="detail-section-title">📋 参会部门排序（{{ sortedDepts.length }}个）</h4>
            <ol class="detail-list">
              <li v-for="(dept, idx) in sortedDepts" :key="'dd'+idx">
                <span class="detail-name">{{ typeof dept === 'string' ? dept : dept.name }}</span>
              </li>
            </ol>
          </div>
          <div class="detail-section" v-if="sortedPersons.length">
            <h4 class="detail-section-title">👤 参会人员排序（{{ sortedPersons.length }}人）</h4>
            <ol class="detail-list">
              <li v-for="(p, idx) in sortedPersons" :key="'dp'+idx">
                <span class="detail-name">{{ p.name }}</span>
                <span v-if="p.department" class="detail-badge detail-badge--dept">{{ p.department }}</span>
                <span v-if="p.position_title" class="detail-badge detail-badge--level">{{ p.position_title }}</span>
              </li>
            </ol>
          </div>
          <div class="detail-section" v-if="!sortedDepts.length && !sortedPersons.length">
            <p class="detail-empty">暂无排序数据</p>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="copyDetail('depts')">📋 复制部门排序</button>
          <button class="btn btn-outline" @click="copyDetail('persons')">👤 复制人员排序</button>
          <button class="btn btn-outline" @click="copyDetail('all')">📄 复制全部</button>
          <button class="btn btn-outline" @click="handleResort(detailMeeting.id); closeDetail();" :disabled="resortingId === detailMeeting.id">
            🔄 重新排序
          </button>
          <button class="btn btn-outline" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>

    <!-- Delete confirm modal -->
    <div class="modal-overlay" v-if="showDeleteConfirm" @click.self="showDeleteConfirm = false">
      <div class="modal-panel modal-panel--sm">
        <h3 class="modal-title">确认删除</h3>
        <p class="delete-text">确定要删除会议「{{ deleteTarget?.name }}」吗？此操作不可撤销。</p>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger" @click="doDelete" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import {
  fetchMeetings,
  createMeeting,
  updateMeeting,
  deleteMeeting,
  resortMeeting,
  fetchDeptSnapshots,
  type Meeting,
  type DeptSnapshot,
} from '../api'

// ─── Data ──────────────────────────────────────────────────────
const meetings = ref<Meeting[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const resortingId = ref<number | null>(null)
const expandedId = ref<number | null>(null)

// Filters
const filterSearch = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')
const filterDepartment = ref('')
const filterPerson = ref('')

// Create/Edit modal
const showCreateModal = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const createForm = reactive({
  name: '',
  input_departments: '',
  input_persons: '' as string | null,
})

// Sorting basis: 'current' dept order or a saved snapshot
const sortBasis = ref<'current' | 'snapshot'>('current')
const selectedSnapshotId = ref<number | null>(null)
const snapshots = ref<DeptSnapshot[]>([])

// Detail modal
const detailMeeting = ref<Meeting | null>(null)

// Delete
const showDeleteConfirm = ref(false)
const deleteTarget = ref<Meeting | null>(null)

// ─── Computed ──────────────────────────────────────────────────

const sortedDepts = computed(() => {
  if (!detailMeeting.value?.sorted_departments) return []
  return parseJson(detailMeeting.value.sorted_departments)
})

const sortedPersons = computed(() => {
  if (!detailMeeting.value?.sorted_persons) return []
  return parseJson(detailMeeting.value.sorted_persons)
})

// ─── Methods ───────────────────────────────────────────────────

function parseJson(raw: string): any[] {
  try {
    return JSON.parse(raw)
  } catch {
    return []
  }
}

function parsedDeptCount(raw: string): number {
  return parseJson(raw).length
}

function parsedPersonCount(raw: string): number {
  return parseJson(raw).length
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadSnapshots() {
  try {
    const res = await fetchDeptSnapshots()
    snapshots.value = res.data
  } catch (e) {
    console.error('Failed to load snapshots:', e)
  }
}

function snapshotById(id?: number | null): DeptSnapshot | undefined {
  if (!id) return undefined
  return snapshots.value.find(s => s.id === id)
}

function sortBasisLabel(m: Meeting): string {
  if (m.sort_snapshot_id) {
    const s = snapshotById(m.sort_snapshot_id)
    return s ? `存档：${s.name}` : `存档#${m.sort_snapshot_id}`
  }
  return '当前部门排序'
}

function sortBasisDetail(m: Meeting): string {
  if (m.sort_snapshot_id) {
    const s = snapshotById(m.sort_snapshot_id)
    return s?.note ? `存档备注：${s.note}` : `排序依据：${sortBasisLabel(m)}`
  }
  return '排序依据：当前部门排序'
}

async function loadMeetings() {
  loading.value = true
  try {
    const res = await fetchMeetings({
      search: filterSearch.value || undefined,
      date_from: filterDateFrom.value || undefined,
      date_to: filterDateTo.value || undefined,
      department: filterDepartment.value || undefined,
      person: filterPerson.value || undefined,
    })
    meetings.value = res.data
  } catch (e) {
    console.error('Failed to load meetings:', e)
  } finally {
    loading.value = false
  }
}

function onFilterChange() {
  loadMeetings()
}

function clearFilters() {
  filterSearch.value = ''
  filterDateFrom.value = ''
  filterDateTo.value = ''
  filterDepartment.value = ''
  filterPerson.value = ''
  loadMeetings()
}

function toggleExpand(id: number) {
  expandedId.value = expandedId.value === id ? null : id
}

// ─── Create ────────────────────────────────────────────────────

function openCreate() {
  isEditing.value = false
  editingId.value = null
  createForm.name = ''
  createForm.input_departments = ''
  createForm.input_persons = null
  sortBasis.value = 'current'
  selectedSnapshotId.value = null
  showCreateModal.value = true
}

function openEdit(m: Meeting) {
  isEditing.value = true
  editingId.value = m.id
  createForm.name = m.name
  createForm.input_departments = m.input_departments || ''
  createForm.input_persons = m.input_persons || null
  // Restore sorting basis: prefer snapshot mode only if the snapshot still exists
  const snap = snapshotById(m.sort_snapshot_id)
  if (m.sort_snapshot_id && snap) {
    sortBasis.value = 'snapshot'
    selectedSnapshotId.value = m.sort_snapshot_id
  } else {
    sortBasis.value = 'current'
    selectedSnapshotId.value = null
  }
  showCreateModal.value = true
}

function closeCreateModal() {
  showCreateModal.value = false
  isEditing.value = false
  editingId.value = null
}

async function saveMeeting() {
  if (!createForm.name.trim()) {
    alert('请输入会议名称')
    return
  }
  if (!createForm.input_departments.trim() && !(createForm.input_persons?.trim())) {
    alert('请至少填写参会部门名单或参会人员名单中的一项')
    return
  }
  // Validate sorting basis
  let sortSnapshotId: number | null = null
  if (sortBasis.value === 'snapshot') {
    if (!selectedSnapshotId.value || !snapshotById(selectedSnapshotId.value)) {
      alert('请选择一份有效的排序存档，或改用「当前部门排序」')
      return
    }
    sortSnapshotId = selectedSnapshotId.value
  }

  saving.value = true
  try {
    if (isEditing.value && editingId.value) {
      await updateMeeting(editingId.value, {
        name: createForm.name.trim(),
        input_persons: createForm.input_persons?.trim() || null,
        input_departments: createForm.input_departments.trim() || null,
        sort_snapshot_id: sortSnapshotId,
      })
    } else {
      await createMeeting({
        name: createForm.name.trim(),
        input_persons: createForm.input_persons?.trim() || null,
        input_departments: createForm.input_departments.trim() || null,
        sort_snapshot_id: sortSnapshotId,
      })
    }
    showCreateModal.value = false
    isEditing.value = false
    editingId.value = null
    await loadMeetings()
  } catch (e: any) {
    console.error('Save meeting failed:', e)
    alert(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

// ─── Detail ────────────────────────────────────────────────────

function openDetail(meeting: Meeting) {
  detailMeeting.value = meeting
}

function closeDetail() {
  detailMeeting.value = null
}

/**
 * 复制会议名单。
 * mode: 'all' 复制部门排序+人员排序；'depts' 仅部门；'persons' 仅人员。
 */
async function copyDetail(mode: 'all' | 'depts' | 'persons' = 'all') {
  if (!detailMeeting.value) return
  const lines: string[] = []

  if (mode === 'all') {
    lines.push(`【${detailMeeting.value.name}】会议名单`)
    lines.push('')
  }

  const depts = sortedDepts.value
  if (mode !== 'persons' && depts.length) {
    lines.push('📋 参会部门排序：')
    depts.forEach((d: any, i: number) => {
      lines.push(`  ${i + 1}. ${typeof d === 'string' ? d : d.name}`)
    })
    lines.push('')
  }

  const persons = sortedPersons.value
  if (mode !== 'depts' && persons.length) {
    lines.push('👤 参会人员排序：')
    persons.forEach((p: any, i: number) => {
      let line = `  ${i + 1}. ${p.name}`
      if (p.department) line += `  [${p.department}]`
      if (p.position_title) line += `  ${p.position_title}`
      lines.push(line)
    })
    lines.push('')
  }

  if (!lines.length) {
    alert('没有可复制的内容')
    return
  }

  await copyToClipboard(lines.join('\n'))
}

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    alert('已复制到剪贴板')
  } catch {
    // Fallback: use textarea
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    alert('已复制到剪贴板')
  }
}

// ─── Resort ────────────────────────────────────────────────────

async function handleResort(id: number) {
  resortingId.value = id
  try {
    const res = await resortMeeting(id)
    // Update the meeting in the list
    const idx = meetings.value.findIndex(m => m.id === id)
    if (idx >= 0) {
      meetings.value[idx] = res.data
    }
    // If detail is open for this meeting, refresh it
    if (detailMeeting.value?.id === id) {
      detailMeeting.value = res.data
    }
  } catch (e: any) {
    console.error('Resort failed:', e)
    alert(e?.response?.data?.detail || '重新排序失败')
  } finally {
    resortingId.value = null
  }
}

// ─── Delete ────────────────────────────────────────────────────

function confirmDelete(meeting: Meeting) {
  deleteTarget.value = meeting
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteMeeting(deleteTarget.value.id)
    showDeleteConfirm.value = false
    if (expandedId.value === deleteTarget.value.id) {
      expandedId.value = null
    }
    if (detailMeeting.value?.id === deleteTarget.value.id) {
      detailMeeting.value = null
    }
    deleteTarget.value = null
    await loadMeetings()
  } catch (e: any) {
    console.error('Delete failed:', e)
    alert(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

// ─── Lifecycle ─────────────────────────────────────────────────

onMounted(() => {
  loadMeetings()
  loadSnapshots()
})
</script>

<style scoped>
.meeting-manage {
  /* container */
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
}

.header-actions {
  display: flex;
  gap: 10px;
}

/* ─── Filter bar ────────────────────────── */
.filter-bar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 16px;
  padding: 14px 18px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filter-label {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

.filter-input {
  padding: 6px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  flex: 1;
  min-width: 100px;
}

.filter-input:focus {
  border-color: #1677ff;
}

.filter-input--date {
  min-width: 130px;
}

.loading,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
  font-size: 16px;
}

.empty-hint {
  font-size: 13px;
  color: #bbb;
  margin-top: 8px;
}

/* ─── Meeting Cards ────────────────────────── */
.meeting-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.meeting-card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.meeting-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  transition: background 0.15s;
  flex-wrap: wrap;
  gap: 10px;
}

.card-header:hover {
  background: #fafbff;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.card-toggle {
  font-size: 10px;
  color: #999;
  flex-shrink: 0;
}

.card-name {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-meta {
  font-size: 12px;
  color: #aaa;
  white-space: nowrap;
}

.card-meta-basis {
  color: #1677ff;
  background: #f0f5ff;
  padding: 0 6px;
  border-radius: 3px;
}

.card-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.card-body {
  padding: 0 18px 16px;
  border-top: 1px solid #f0f0f0;
}

.card-section {
  margin-top: 12px;
}

.card-section-title {
  font-size: 14px;
  font-weight: 600;
  color: #555;
  margin-bottom: 6px;
}

.card-list {
  padding-left: 24px;
  font-size: 13px;
  color: #333;
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 200px;
  overflow-y: auto;
}

.card-list li {
  line-height: 1.7;
}

.card-list-dept {
  display: inline-block;
  margin-left: 8px;
  padding: 0 6px;
  font-size: 11px;
  color: #888;
  background: #f5f5f5;
  border-radius: 3px;
}

.card-list-level {
  display: inline-block;
  margin-left: 4px;
  padding: 0 6px;
  font-size: 11px;
  color: #1677ff;
  background: #f0f5ff;
  border-radius: 3px;
}

/* ─── Detail Modal ─────────────────────────── */
.modal-panel--lg {
  width: 640px;
}

.detail-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 20px;
}

.detail-header .modal-title {
  margin-bottom: 0;
}

.detail-date {
  font-size: 13px;
  color: #999;
}

.detail-section {
  margin-bottom: 16px;
}

.detail-section-title {
  font-size: 15px;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.detail-list {
  padding-left: 24px;
  font-size: 14px;
  color: #333;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 360px;
  overflow-y: auto;
}

.detail-list li {
  line-height: 1.8;
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-name {
  font-weight: 500;
}

.detail-badge {
  padding: 1px 8px;
  font-size: 12px;
  border-radius: 4px;
}

.detail-badge--dept {
  color: #666;
  background: #f5f5f5;
}

.detail-badge--level {
  color: #1677ff;
  background: #f0f5ff;
}

.detail-empty {
  text-align: center;
  color: #bbb;
  font-size: 14px;
  padding: 20px;
}

/* ─── Buttons ────────────────────────────── */
.btn {
  padding: 8px 20px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
}

.btn-primary {
  background: #1677ff;
  color: #fff;
  border-color: #1677ff;
}
.btn-primary:hover { background: #4096ff; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-outline {
  background: #fff;
  color: #555;
  border-color: #d9d9d9;
}
.btn-outline:hover { border-color: #1677ff; color: #1677ff; }
.btn-outline:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-danger {
  background: #fff;
  color: #ff4d4f;
  border-color: #ff4d4f;
}
.btn-danger:hover { background: #ff4d4f; color: #fff; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm {
  padding: 4px 12px;
  font-size: 13px;
}

/* ─── Modal ──────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-panel {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
  width: 580px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.15);
}

.modal-panel--sm {
  width: 400px;
}

.modal-title {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 20px;
}

.modal-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  flex-wrap: wrap;
}

.delete-text {
  font-size: 15px;
  color: #555;
  margin-bottom: 8px;
}

/* ─── Form ───────────────────────────────── */
.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 14px;
  font-weight: 500;
  color: #333;
}

.form-label--optional {
  font-weight: 400;
  color: #999;
  font-size: 13px;
}

.required {
  color: #ff4d4f;
}

.form-input {
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: #1677ff;
}

.form-textarea {
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  resize: vertical;
  font-family: inherit;
}

.form-textarea:focus {
  border-color: #1677ff;
}

.form-hint {
  font-size: 12px;
  color: #aaa;
  margin-top: 2px;
}

.sort-basis-row {
  display: flex;
  gap: 18px;
}

.sort-basis-option {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
}
</style>
