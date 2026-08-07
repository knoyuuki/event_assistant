<template>
  <div class="person-manage">
    <div class="page-header">
      <h2 class="page-title">人员管理</h2>
      <div class="header-actions">
        <button class="btn btn-outline" @click="openReorder">↕ 排序调整</button>
        <button class="btn btn-outline" @click="handleImport">📥 导入通讯录</button>
        <button class="btn btn-primary" @click="openAdd">+ 新增人员</button>
      </div>
    </div>

    <!-- Filter bar -->
    <div class="filter-bar">
      <div class="filter-item">
        <label class="filter-label">部门</label>
        <DeptTreeSelect
          v-model="filterDepartment"
          :tree-data="departmentTreeData"
          :show-all="true"
          placeholder="全部部门"
          style="min-width: 160px"
          @update:model-value="onFilterChange"
        />
      </div>
      <div class="filter-item">
        <label class="filter-label">类型</label>
        <select v-model="filterPersonType" class="filter-select" @change="onFilterChange">
          <option value="">全部</option>
          <option v-for="t in personTypes" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>
      <div class="filter-item">
        <label class="filter-label">等级</label>
        <select v-model.number="filterPositionLevel" class="filter-select" @change="onFilterChange">
          <option :value="0">全部</option>
          <option v-for="(label, level) in availableLevels" :key="level" :value="level">
            {{ label }}（{{ level }}）
          </option>
        </select>
      </div>
      <div class="filter-item filter-item--search">
        <label class="filter-label">姓名</label>
        <input
          v-model="filterSearch"
          class="filter-input"
          placeholder="输入姓名模糊搜索..."
          @keyup.enter="onFilterChange"
        />
        <button class="btn btn-outline btn-sm" @click="onFilterChange">搜索</button>
      </div>
      <div class="filter-item filter-item--page-size">
        <label class="filter-label">每页</label>
        <select v-model.number="pageSize" class="filter-select filter-select--sm" @change="onPageSizeChange">
          <option :value="10">10</option>
          <option :value="20">20</option>
          <option :value="50">50</option>
          <option :value="100">100</option>
        </select>
        <span class="filter-label">条</span>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div class="table-wrapper" v-if="persons.length">
        <table class="data-table">
          <thead>
            <tr>
              <th class="col-photo">照片</th>
              <th class="col-id">ID</th>
              <th class="col-name">姓名</th>
              <th class="col-dept">部门</th>
              <th class="col-type">类型</th>
              <th class="col-pos">职位（照片）</th>
              <th class="col-title">人员职位</th>
              <th class="col-level">等级</th>
              <th class="col-phone">手机号</th>
              <th class="col-mdept">分管部门</th>
              <th class="col-notes">备注</th>
              <th class="col-actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in persons" :key="p.id">
              <td class="cell-photo">
                <img
                  :src="getPhotoUrl(p.filename)"
                  :alt="p.name"
                  class="photo-thumb"
                  @click="openPreview(p)"
                  @error="onImgError($event)"
                  title="点击查看大图"
                />
              </td>
              <td>{{ p.id }}</td>
              <td class="cell-name">{{ p.name }}</td>
              <td>{{ p.department }}</td>
              <td>{{ p.person_type || '-' }}</td>
              <td>{{ p.position }}</td>
              <td>{{ p.position_title || '-' }}</td>
              <td>{{ p.position_level ?? '-' }}</td>
              <td>{{ p.phone || '-' }}</td>
              <td>{{ p.managed_departments || '-' }}</td>
              <td class="cell-notes">{{ p.notes || '-' }}</td>
              <td class="cell-actions">
                <button class="btn btn-sm btn-outline" @click="openEdit(p)">编辑</button>
                <button class="btn btn-sm btn-danger" @click="confirmDelete(p)">删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="empty">
        <p>暂无人员数据</p>
        <p class="empty-hint">请先在浏览页面扫描照片，或使用"导入通讯录"按钮</p>
      </div>

      <!-- Pagination -->
      <div class="pagination" v-if="totalPages > 1">
        <div class="pagination-info">
          共 {{ total }} 条，第 {{ currentPage }} / {{ totalPages }} 页
        </div>
        <div class="pagination-controls">
          <button class="btn btn-sm btn-outline" :disabled="currentPage <= 1" @click="goToPage(1)">首页</button>
          <button class="btn btn-sm btn-outline" :disabled="currentPage <= 1" @click="goToPage(currentPage - 1)">上一页</button>
          <template v-for="p in visiblePages" :key="p">
            <span v-if="p === '...'" class="pagination-ellipsis">...</span>
            <button
              v-else
              class="btn btn-sm"
              :class="p === currentPage ? 'btn-primary' : 'btn-outline'"
              @click="goToPage(p)"
            >{{ p }}</button>
          </template>
          <button class="btn btn-sm btn-outline" :disabled="currentPage >= totalPages" @click="goToPage(currentPage + 1)">下一页</button>
          <button class="btn btn-sm btn-outline" :disabled="currentPage >= totalPages" @click="goToPage(totalPages)">末页</button>
        </div>
      </div>
    </template>

    <!-- Photo preview modal -->
    <div class="preview-overlay" v-if="previewPerson" @click.self="closePreview">
      <button class="preview-close" @click="closePreview" title="关闭">&times;</button>
      <div class="preview-container">
        <img
          :src="getPhotoUrl(previewPerson.filename)"
          :alt="previewPerson.name"
          class="preview-image"
          @error="onPreviewError($event)"
        />
        <div class="preview-info">
          <span class="preview-name">{{ previewPerson.name }}</span>
          <span class="preview-dept">{{ previewPerson.department }}</span>
          <span class="preview-pos">{{ previewPerson.position }}</span>
          <span v-if="previewPerson.person_type" class="preview-type">{{ previewPerson.person_type }}</span>
          <span v-if="previewPerson.position_title" class="preview-title">{{ previewPerson.position_title }}</span>
        </div>
      </div>
      <button class="preview-nav preview-nav--prev" @click="previewPrev" :disabled="previewIndex <= 0" title="上一张">&lsaquo;</button>
      <button class="preview-nav preview-nav--next" @click="previewNext" :disabled="previewIndex >= persons.length - 1" title="下一张">&rsaquo;</button>
    </div>

    <!-- Add/Edit Modal -->
    <div class="modal-overlay" v-if="showModal" @click.self="closeModal">
      <div class="modal-panel">
        <h3 class="modal-title">{{ isEditing ? '编辑人员' : '新增人员' }}</h3>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">姓名 <span class="required">*</span></label>
            <input v-model="form.name" class="form-input" placeholder="请输入姓名" />
          </div>
          <div class="form-group">
            <label class="form-label">部门 <span class="required">*</span></label>
            <DeptTreeSelect
              v-model="form.department"
              :tree-data="departmentTreeData"
              placeholder="请选择部门"
            />
          </div>
          <div class="form-group">
            <label class="form-label">人员类型</label>
            <select v-model="form.person_type" class="form-select">
              <option value="">-- 请选择 --</option>
              <option v-for="t in personTypes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">职位（照片文件名） <span class="required">*</span></label>
            <input v-model="form.position" class="form-input" placeholder="请输入职位" />
          </div>
          <div class="form-group">
            <label class="form-label">文件名 <span class="required">*</span></label>
            <input v-model="form.filename" class="form-input" placeholder="请输入照片文件名" :disabled="isEditing" />
          </div>
          <div class="form-group">
            <label class="form-label">人员职位</label>
            <select v-model="form.position_title" class="form-select" @change="onPositionTitleChange">
              <option value="">-- 请选择 --</option>
              <option v-for="(level, title) in positionMap" :key="title" :value="title">
                {{ title }}（等级 {{ level }}）
              </option>
              <option value="__custom__">其他（自定义）</option>
            </select>
            <input
              v-if="showCustomTitle"
              v-model="customTitle"
              class="form-input form-input--inline"
              placeholder="请输入自定义职位名称"
              @input="onCustomTitleInput"
            />
          </div>
          <div class="form-group">
            <label class="form-label">职位等级</label>
            <input v-model.number="form.position_level" type="number" step="0.1" min="1" max="5" class="form-input form-input--short" placeholder="自动计算" />
            <span class="form-hint">1-5，留空则自动根据职位计算</span>
          </div>
          <div class="form-group">
            <label class="form-label">手机号</label>
            <input v-model="form.phone" class="form-input" placeholder="请输入手机号" />
          </div>
          <div class="form-group">
            <label class="form-label">邮箱</label>
            <input v-model="form.email" class="form-input" placeholder="请输入邮箱" />
          </div>
          <div class="form-group">
            <label class="form-label">分管部门</label>
            <input v-model="form.managed_departments" class="form-input" placeholder="多个用逗号分隔，如：财务部,人力资源部" />
          </div>
          <div class="form-group">
            <label class="form-label">分管业务</label>
            <input v-model="form.managed_businesses" class="form-input" placeholder="多个用逗号分隔" />
          </div>
          <div class="form-group">
            <label class="form-label">备注</label>
            <textarea v-model="form.notes" class="form-textarea" placeholder="请输入备注信息" rows="3"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeModal">取消</button>
          <button class="btn btn-primary" @click="savePerson" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete confirm modal -->
    <div class="modal-overlay" v-if="showDeleteConfirm" @click.self="showDeleteConfirm = false">
      <div class="modal-panel modal-panel--sm">
        <h3 class="modal-title">确认删除</h3>
        <p class="delete-text">确定要删除人员「{{ deleteTarget?.name }}」吗？此操作不可撤销。</p>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showDeleteConfirm = false">取消</button>
          <button class="btn btn-danger" @click="doDelete" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Reorder Modal -->
    <div class="modal-overlay" v-if="showReorderModal" @click.self="showReorderModal = false">
      <div class="modal-panel modal-panel--lg">
        <h3 class="modal-title">排序调整</h3>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">选择部门</label>
            <DeptTreeSelect
              v-model="reorderDept"
              :tree-data="departmentTreeData"
              placeholder="请选择要排序的部门"
            />
          </div>
          <div v-if="reorderDept && reorderGroups.length" class="reorder-groups">
            <div v-for="group in reorderGroups" :key="group.type" class="reorder-group">
              <div class="reorder-group-header">{{ group.type }}（{{ group.persons.length }}人）</div>
              <div v-for="(p, idx) in group.persons" :key="p.id" class="reorder-row">
                <span class="reorder-name">{{ p.name }}</span>
                <span class="reorder-level">{{ p.position_title || p.position || '-' }}</span>
                <div class="reorder-actions">
                  <button class="btn btn-sm btn-outline" @click="moveReorderUp(group.type, idx)" :disabled="idx === 0" title="上移">▲</button>
                  <button class="btn btn-sm btn-outline" @click="moveReorderDown(group.type, idx)" :disabled="idx === group.persons.length - 1" title="下移">▼</button>
                </div>
              </div>
            </div>
          </div>
          <div v-if="reorderDept && !reorderGroups.length" class="reorder-empty">
            该部门暂无人员
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showReorderModal = false">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import {
  fetchPersons,
  fetchDepartmentsTree,
  fetchPositionLevels,
  fetchPersonTypes,
  createPerson,
  updatePerson,
  deletePerson,
  reorderPersons,
  importExcel,
  importLeaders,
  getPhotoUrl,
  type Person,
  type PersonForm,
  type DepartmentTreeNode,
} from '../api'
import DeptTreeSelect from '../components/DeptTreeSelect.vue'

// ─── Data ──────────────────────────────────────────────────────
const persons = ref<Person[]>([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

// Filters
const filterDepartment = ref('')
const filterPersonType = ref('')
const filterPositionLevel = ref(0)
const filterSearch = ref('')
const departmentTreeData = ref<DepartmentTreeNode[]>([])
const personTypes = ref<string[]>([])

// Modals
const showModal = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const positionMap = ref<Record<string, number>>({})
const showCustomTitle = ref(false)
const customTitle = ref('')

// Delete
const showDeleteConfirm = ref(false)
const deleteTarget = ref<Person | null>(null)
const deleting = ref(false)

// Photo preview
const previewPerson = ref<Person | null>(null)
const previewIndex = ref(0)

// Reorder
const showReorderModal = ref(false)
const reorderDept = ref('')
const reorderData = ref<Record<string, Person[]>>({})

const form = reactive<PersonForm>({
  name: '',
  department: '',
  position: '',
  filename: '',
  person_type: null,
  sort_order: null,
  position_title: null,
  position_level: null,
  managed_departments: null,
  managed_businesses: null,
  notes: null,
  phone: null,
  email: null,
})

// ─── Computed ──────────────────────────────────────────────────
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const visiblePages = computed(() => {
  const pages: (number | string)[] = []
  const tp = totalPages.value
  const cp = currentPage.value

  if (tp <= 7) {
    for (let i = 1; i <= tp; i++) pages.push(i)
  } else {
    pages.push(1)
    if (cp > 3) pages.push('...')
    for (let i = Math.max(2, cp - 1); i <= Math.min(tp - 1, cp + 1); i++) {
      pages.push(i)
    }
    if (cp < tp - 2) pages.push('...')
    pages.push(tp)
  }
  return pages
})

const reorderGroups = computed(() => {
  if (!reorderDept.value || !reorderData.value) return []
  const data = reorderData.value
  const typeOrder = ['部门领导', '员工', 'P1', 'P2']
  return typeOrder
    .filter(t => data[t] && data[t].length > 0)
    .map(t => ({ type: t, persons: data[t] }))
})

// Build available position levels with labels from the position map
const availableLevels = computed(() => {
  const levels: Record<number, string> = {}
  // Collect unique levels with their canonical titles
  const seen = new Map<number, string>()
  for (const [title, level] of Object.entries(positionMap.value)) {
    const existing = seen.get(level)
    if (!existing) {
      seen.set(level, title)
    } else {
      // Use the shorter/cleaner title
      if (title.length < existing.length) {
        seen.set(level, title)
      }
    }
  }
  // Sort by level ascending
  const sorted = [...seen.entries()].sort((a, b) => a[0] - b[0])
  const result: Record<number, string> = {}
  for (const [level, title] of sorted) {
    result[level] = title
  }
  return result
})

// ─── Methods ───────────────────────────────────────────────────

function resetForm() {
  form.name = ''
  form.department = ''
  form.position = ''
  form.filename = ''
  form.person_type = null
  form.sort_order = null
  form.position_title = null
  form.position_level = null
  form.managed_departments = null
  form.managed_businesses = null
  form.notes = null
  form.phone = null
  form.email = null
  showCustomTitle.value = false
  customTitle.value = ''
}

async function loadPersons() {
  loading.value = true
  try {
    const res = await fetchPersons({
      department: filterDepartment.value || undefined,
      person_type: filterPersonType.value || undefined,
      position_level: filterPositionLevel.value || undefined,
      search: filterSearch.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    persons.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error('Failed to load persons:', e)
  } finally {
    loading.value = false
  }
}

async function loadDepartmentTree() {
  try {
    const res = await fetchDepartmentsTree()
    departmentTreeData.value = res.data
  } catch (e) {
    console.error('Failed to load departments:', e)
  }
}

async function loadPositionMap() {
  try {
    const res = await fetchPositionLevels()
    positionMap.value = res.data.mapping
  } catch (e) {
    console.error('Failed to load position levels:', e)
  }
}

async function loadPersonTypes() {
  try {
    const res = await fetchPersonTypes()
    personTypes.value = res.data.types
  } catch (e) {
    console.error('Failed to load person types:', e)
  }
}

function onFilterChange() {
  currentPage.value = 1
  loadPersons()
}

function onPageSizeChange() {
  currentPage.value = 1
  loadPersons()
}

function goToPage(page: number | string) {
  const p = typeof page === 'string' ? parseInt(page, 10) : page
  if (isNaN(p) || p < 1 || p > totalPages.value) return
  currentPage.value = p
  loadPersons()
}

// ─── Photo preview ─────────────────────────────────────────────

function openPreview(person: Person) {
  previewIndex.value = persons.value.findIndex(p => p.id === person.id)
  previewPerson.value = person
  document.addEventListener('keydown', onPreviewKeydown)
}

function closePreview() {
  previewPerson.value = null
  document.removeEventListener('keydown', onPreviewKeydown)
}

function previewPrev() {
  if (previewIndex.value > 0) {
    previewIndex.value--
    previewPerson.value = persons.value[previewIndex.value]
  }
}

function previewNext() {
  if (previewIndex.value < persons.value.length - 1) {
    previewIndex.value++
    previewPerson.value = persons.value[previewIndex.value]
  }
}

function onPreviewKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') closePreview()
  if (e.key === 'ArrowLeft') previewPrev()
  if (e.key === 'ArrowRight') previewNext()
}

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

function onPreviewError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}

// ─── CRUD ──────────────────────────────────────────────────────

function openAdd() {
  isEditing.value = false
  editingId.value = null
  resetForm()
  showModal.value = true
}

function openEdit(person: Person) {
  isEditing.value = true
  editingId.value = person.id
  form.name = person.name
  form.department = person.department
  form.position = person.position
  form.filename = person.filename
  form.person_type = person.person_type ?? null
  form.sort_order = person.sort_order ?? null
  form.position_title = person.position_title ?? null
  form.position_level = person.position_level ?? null
  form.managed_departments = person.managed_departments ?? null
  form.managed_businesses = person.managed_businesses ?? null
  form.notes = person.notes ?? null
  form.phone = person.phone ?? null
  form.email = person.email ?? null
  showCustomTitle.value = false
  customTitle.value = ''

  if (person.position_title && !(person.position_title in positionMap.value)) {
    showCustomTitle.value = true
    customTitle.value = person.position_title
  }

  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

function onPositionTitleChange() {
  if (form.position_title === '__custom__') {
    showCustomTitle.value = true
    customTitle.value = ''
    form.position_title = null
    form.position_level = null
  } else if (form.position_title) {
    showCustomTitle.value = false
    const level = positionMap.value[form.position_title]
    if (level !== undefined) {
      form.position_level = level
    }
  }
}

function onCustomTitleInput() {
  form.position_title = customTitle.value || null
  if (customTitle.value && !(customTitle.value in positionMap.value)) {
    form.position_level = 4.0
  }
}

async function savePerson() {
  if (!form.name || !form.department || !form.position || !form.filename) {
    alert('请填写姓名、部门、职位和文件名')
    return
  }

  saving.value = true
  try {
    if (isEditing.value && editingId.value) {
      await updatePerson(editingId.value, { ...form })
    } else {
      await createPerson({ ...form })
    }
    showModal.value = false
    await loadPersons()
  } catch (e: any) {
    console.error('Save failed:', e)
    alert(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function confirmDelete(person: Person) {
  deleteTarget.value = person
  showDeleteConfirm.value = true
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deletePerson(deleteTarget.value.id)
    showDeleteConfirm.value = false
    deleteTarget.value = null
    if (persons.value.length === 1 && currentPage.value > 1) {
      currentPage.value--
    }
    await loadPersons()
  } catch (e: any) {
    console.error('Delete failed:', e)
    alert(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

// ─── Reorder ───────────────────────────────────────────────────

function openReorder() {
  reorderDept.value = filterDepartment.value || ''
  reorderData.value = {}
  showReorderModal.value = true
}

async function loadReorderData() {
  if (!reorderDept.value) return
  try {
    const res = await fetchPersons({
      department: reorderDept.value,
      page_size: 200,
    })
    const allPersons = res.data.items
    const grouped: Record<string, Person[]> = {}
    for (const p of allPersons) {
      const pt = p.person_type || '未分类'
      grouped.setdefault ? null : null
      if (!grouped[pt]) grouped[pt] = []
      grouped[pt].push(p)
    }
    reorderData.value = grouped
  } catch (e) {
    console.error('Failed to load reorder data:', e)
  }
}

watch(reorderDept, () => {
  if (reorderDept.value) loadReorderData()
})

async function moveReorderUp(type: string, idx: number) {
  const group = reorderData.value[type]
  if (!group || idx <= 0) return
  const items = group.map((p, i) => ({ id: p.id, sort_order: i }))
  const a = items[idx - 1]
  const b = items[idx]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  try {
    await reorderPersons(items)
    await loadReorderData()
    await loadPersons()
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

async function moveReorderDown(type: string, idx: number) {
  const group = reorderData.value[type]
  if (!group || idx >= group.length - 1) return
  const items = group.map((p, i) => ({ id: p.id, sort_order: i }))
  const a = items[idx]
  const b = items[idx + 1]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  try {
    await reorderPersons(items)
    await loadReorderData()
    await loadPersons()
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

// ─── Import ────────────────────────────────────────────────────

async function handleImport() {
  if (!confirm('将导入通讯录数据（企业通讯录人员名单.xlsx）到数据库。\n\n先导入公司领导（来自Markdown），再导入Excel人员数据。\n\n是否继续？')) return

  try {
    // Step 1: Import company leaders
    const leadersRes = await importLeaders()
    alert(`公司领导导入完成：新增 ${leadersRes.data.inserted} 条，更新 ${leadersRes.data.updated} 条`)

    // Step 2: Import Excel data (dry run first)
    const dryRes = await importExcel(true)
    const dryData = dryRes.data
    if (!confirm(`预览结果：共 ${dryData.total} 条，分 ${dryData.groups} 组。\n\n确认导入？`)) return

    const importRes = await importExcel(false)
    alert(`导入完成：新增 ${importRes.data.inserted} 条，更新 ${importRes.data.updated} 条，共 ${importRes.data.total} 条`)
    await loadPersons()
  } catch (e: any) {
    console.error('Import failed:', e)
    alert(e?.response?.data?.detail || '导入失败')
  }
}

// ─── Lifecycle ─────────────────────────────────────────────────

onMounted(() => {
  loadDepartmentTree()
  loadPositionMap()
  loadPersonTypes()
  loadPersons()
})
</script>

<style scoped>
.person-manage {
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
  gap: 16px;
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

.filter-item--search {
  flex: 1;
  min-width: 240px;
}

.filter-label {
  font-size: 13px;
  color: #666;
  white-space: nowrap;
}

.filter-select {
  padding: 6px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  background: #fff;
  cursor: pointer;
  min-width: 120px;
}

.filter-select:focus {
  border-color: #1677ff;
}

.filter-select--sm {
  min-width: 64px;
}

.filter-input {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 13px;
  outline: none;
}

.filter-input:focus {
  border-color: #1677ff;
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

/* ─── Table ─────────────────────────────── */
.table-wrapper {
  background: #fff;
  border-radius: 10px;
  overflow-x: auto;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 1200px;
}

.data-table th,
.data-table td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid #f0f0f0;
  white-space: nowrap;
  vertical-align: middle;
}

.data-table th {
  background: #fafafa;
  font-weight: 600;
  color: #555;
  position: sticky;
  top: 0;
  z-index: 1;
}

.data-table tbody tr {
  height: 64px;
}

.data-table tbody tr:hover {
  background: #fafbff;
}

/* Column widths */
.col-photo { width: 64px; text-align: center; }
.col-id { width: 48px; }
.col-name { width: 70px; }
.col-dept { width: 110px; }
.col-type { width: 70px; }
.col-pos { width: 100px; }
.col-title { width: 110px; }
.col-level { width: 56px; }
.col-phone { width: 100px; }
.col-mdept { width: 120px; }
.col-notes { min-width: 100px; }
.col-actions { width: 130px; }

/* Photo thumbnail */
.cell-photo {
  text-align: center;
  padding: 4px 6px !important;
}

.photo-thumb {
  width: 48px;
  height: 56px;
  object-fit: cover;
  border-radius: 4px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  vertical-align: middle;
}

.photo-thumb:hover {
  transform: scale(1.08);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.cell-name {
  font-weight: 500;
  color: #1a1a2e;
}

.cell-notes {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cell-actions {
  display: flex;
  gap: 6px;
}

/* ─── Pagination ────────────────────────── */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding: 12px 0;
  flex-wrap: wrap;
  gap: 12px;
}

.pagination-info {
  font-size: 13px;
  color: #888;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 4px;
}

.pagination-ellipsis {
  padding: 0 4px;
  color: #999;
  user-select: none;
}

/* ─── Photo preview ─────────────────────── */
.preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.88);
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-close {
  position: absolute;
  top: 16px;
  right: 24px;
  background: none;
  border: none;
  color: #fff;
  font-size: 36px;
  cursor: pointer;
  line-height: 1;
  opacity: 0.7;
  transition: opacity 0.2s;
  z-index: 2;
}

.preview-close:hover {
  opacity: 1;
}

.preview-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  max-width: 90vw;
  max-height: 90vh;
}

.preview-image {
  max-width: 90vw;
  max-height: 75vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
}

.preview-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  color: #fff;
  font-size: 15px;
}

.preview-name {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}

.preview-dept,
.preview-pos,
.preview-type {
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 4px;
  font-size: 13px;
}

.preview-title {
  padding: 2px 8px;
  background: rgba(22, 119, 255, 0.3);
  border-radius: 4px;
  font-size: 13px;
  color: #91caff;
}

/* Preview nav arrows */
.preview-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255, 255, 255, 0.12);
  border: none;
  color: #fff;
  font-size: 48px;
  width: 56px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s;
  border-radius: 8px;
  user-select: none;
}

.preview-nav:hover {
  background: rgba(255, 255, 255, 0.25);
}

.preview-nav:disabled {
  opacity: 0.25;
  cursor: default;
}

.preview-nav--prev {
  left: 16px;
}

.preview-nav--next {
  right: 16px;
}

/* ─── Reorder Modal ────────────────────── */
.modal-panel--lg {
  width: 680px;
}

.reorder-groups {
  margin-top: 16px;
}

.reorder-group {
  margin-bottom: 12px;
}

.reorder-group-header {
  font-size: 14px;
  font-weight: 600;
  color: #555;
  background: #f7f8fa;
  padding: 8px 12px;
  border-radius: 6px 6px 0 0;
}

.reorder-row {
  display: flex;
  align-items: center;
  padding: 6px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.reorder-row:hover {
  background: #fafbff;
}

.reorder-name {
  font-weight: 500;
  flex: 1;
  color: #1a1a2e;
}

.reorder-level {
  color: #888;
  font-size: 13px;
  margin-right: 12px;
}

.reorder-actions {
  display: flex;
  gap: 4px;
}

.reorder-empty {
  text-align: center;
  padding: 30px;
  color: #999;
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

.form-input:disabled {
  background: #f5f5f5;
  color: #999;
}

.form-input--short {
  max-width: 120px;
}

.form-input--inline {
  margin-top: 6px;
}

.form-select {
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  outline: none;
  background: #fff;
  cursor: pointer;
}

.form-select:focus {
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
</style>
