<template>
  <div class="dept-manage">
    <div class="page-header">
      <h2 class="page-title">部门管理</h2>
      <div class="header-actions">
        <button class="btn btn-outline" @click="handleSeedTree">🔄 重置分类树</button>
        <button class="btn btn-outline" @click="initFromPhotos">📷 从照片初始化</button>
        <button class="btn btn-outline" @click="openAddCategory">+ 新增分类</button>
        <button class="btn btn-primary" @click="openSaveSnapshot">💾 保存当前排序</button>
      </div>
    </div>

    <p class="tree-hint">💡 支持拖拽行来调整分类与部门的排序，也可使用右侧 ▲▼ 按钮</p>

    <div v-if="loading" class="loading">加载中...</div>

    <template v-else>
      <div class="tree-toolbar" v-if="treeData.length">
        <button class="btn btn-sm btn-outline" @click="expandAllCategories" :disabled="allExpanded">📂 展开全部</button>
        <button class="btn btn-sm btn-outline" @click="collapseAllCategories" :disabled="allCollapsed">📁 收起全部</button>
      </div>
      <div class="tree-container" v-if="treeData.length">
        <div v-for="(cat, catIdx) in treeData" :key="cat.id ?? 'uncategorized'" class="tree-group">
          <!-- Category row -->
          <div
            class="tree-row tree-row--category"
            :class="{
              'tree-row--uncategorized': cat.id === null,
              'tree-row--dragging': draggingCatIdx === catIdx,
              'tree-row--drag-over': dragOverCatIdx === catIdx,
            }"
            :draggable="cat.id !== null"
            :ref="el => setCatRowRef(cat, el)"
            title="拖拽调整分类顺序"
            @dragstart="onCatDragStart(catIdx, $event)"
            @dragover="onCatDragOver(catIdx, $event)"
            @drop="onCatDrop(catIdx, $event)"
            @dragend="onCatDragEnd"
          >
            <button class="toggle-btn" @click="toggleCategory(cat)">
              <span :class="['toggle-icon', { 'toggle-icon--expanded': isCatExpanded(cat) }]">▶</span>
            </button>
            <span class="category-name">{{ cat.name }}</span>
            <span class="category-count">{{ cat.departments.length }}个部门</span>
            <div class="row-actions" v-if="cat.id !== null">
              <button class="btn btn-sm btn-outline" @click="openAddDeptToCategory(cat)" title="添加部门">+</button>
              <button class="btn btn-sm btn-outline" @click="moveCategoryUp(catIdx)" :disabled="sortableCatIdx(catIdx) === 0" title="上移">▲</button>
              <button class="btn btn-sm btn-outline" @click="moveCategoryDown(catIdx)" :disabled="sortableCatIdx(catIdx) >= sortableCatCount() - 1" title="下移">▼</button>
              <button class="btn btn-sm btn-outline" @click="openEditCategory(cat)" title="编辑分类">编辑</button>
              <button class="btn btn-sm btn-danger" @click="confirmDeleteCategory(cat)" title="删除分类">删除</button>
            </div>
          </div>

          <!-- Department rows -->
          <template v-if="isCatExpanded(cat)">
            <div
              v-for="(dept, deptIdx) in cat.departments"
              :key="dept.id"
              class="tree-row tree-row--dept"
              :class="{
                'tree-row--dragging': isDeptDragging(catIdx, deptIdx),
                'tree-row--drag-over': isDeptDragOver(catIdx, deptIdx),
              }"
              draggable="true"
              title="拖拽调整部门顺序"
              @dragstart="onDeptDragStart(catIdx, deptIdx, $event)"
              @dragover="onDeptDragOver(catIdx, deptIdx, $event)"
              @drop="onDeptDrop(catIdx, deptIdx, $event)"
              @dragend="onDeptDragEnd"
            >
              <span class="dept-name">{{ dept.name }}</span>
              <div class="row-actions">
                <button class="btn btn-sm btn-outline" @click="moveDeptUp(catIdx, deptIdx)" :disabled="deptIdx === 0" title="上移">▲</button>
                <button class="btn btn-sm btn-outline" @click="moveDeptDown(catIdx, deptIdx)" :disabled="deptIdx === cat.departments.length - 1" title="下移">▼</button>
                <button class="btn btn-sm btn-outline" @click="openEditDept(dept)" title="编辑部门">编辑</button>
                <button class="btn btn-sm btn-danger" @click="confirmDeleteDept(dept)" title="删除部门">删除</button>
              </div>
            </div>
            <div v-if="!cat.departments.length" class="tree-row tree-row--empty">
              暂无部门，点击 + 添加
            </div>
          </template>
        </div>
      </div>

      <div v-else class="empty">
        <p>暂无部门数据</p>
        <p class="empty-hint">点击"重置分类树"初始化预定义分类，或扫描照片目录导入</p>
      </div>

      <!-- Sort snapshots (排序存档) -->
      <div class="snapshot-section">
        <div class="snapshot-header">
          <h3 class="snapshot-title">📦 部门排序存档</h3>
        </div>
        <p class="snapshot-hint">
          将当前分类与部门的排列顺序保存为存档，可命名并添加备注；在会议排序中可选择按某份存档排序。
        </p>
        <div v-if="snapshots.length" class="snapshot-list">
          <div v-for="s in snapshots" :key="s.id" class="snapshot-row">
            <div class="snapshot-info">
              <span class="snapshot-name">{{ s.name }}</span>
              <span v-if="s.note" class="snapshot-note">{{ s.note }}</span>
              <span class="snapshot-meta">{{ formatDate(s.created_at) }}</span>
            </div>
            <div class="row-actions">
              <button class="btn btn-sm btn-outline" @click="handleApplySnapshot(s)" title="将当前部门排序恢复为该存档顺序">读取</button>
              <button class="btn btn-sm btn-outline" @click="openEditSnapshot(s)" title="编辑名称/备注">编辑</button>
              <button class="btn btn-sm btn-danger" @click="confirmDeleteSnapshot(s)" title="删除存档">删除</button>
            </div>
          </div>
        </div>
        <div v-else class="snapshot-empty">
          暂无存档，点击右上角"💾 保存当前排序"创建第一份存档
        </div>
      </div>
    </template>

    <!-- Category Add/Edit Modal -->
    <div class="modal-overlay" v-if="showCategoryModal" @click.self="closeCategoryModal">
      <div class="modal-panel modal-panel--sm">
        <h3 class="modal-title">{{ isEditingCategory ? '编辑分类' : '新增分类' }}</h3>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">分类名称 <span class="required">*</span></label>
            <input v-model="categoryForm.name" class="form-input" placeholder="请输入分类名称" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeCategoryModal">取消</button>
          <button class="btn btn-primary" @click="saveCategory" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Department Add/Edit Modal -->
    <div class="modal-overlay" v-if="showDeptModal" @click.self="closeDeptModal">
      <div class="modal-panel">
        <h3 class="modal-title">{{ isEditingDept ? '编辑部门' : '新增部门' }}</h3>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">部门名称 <span class="required">*</span></label>
            <input v-model="deptForm.name" class="form-input" placeholder="请输入部门名称" />
          </div>
          <div class="form-group">
            <label class="form-label">所属分类 <span class="required">*</span></label>
            <select v-model="deptForm.category_id" class="form-select">
              <option :value="null">-- 请选择分类 --</option>
              <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">描述</label>
            <textarea v-model="deptForm.description" class="form-textarea" placeholder="请输入部门描述（可选）" rows="3"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeDeptModal">取消</button>
          <button class="btn btn-primary" @click="saveDept" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Category confirm modal -->
    <div class="modal-overlay" v-if="showDeleteCategoryConfirm" @click.self="showDeleteCategoryConfirm = false">
      <div class="modal-panel modal-panel--sm">
        <h3 class="modal-title">确认删除</h3>
        <p class="delete-text">确定要删除分类「{{ deleteCategoryTarget?.name }}」吗？<br>该分类下必须没有部门才能删除。</p>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showDeleteCategoryConfirm = false">取消</button>
          <button class="btn btn-danger" @click="doDeleteCategory" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Department confirm modal -->
    <div class="modal-overlay" v-if="showDeleteDeptConfirm" @click.self="showDeleteDeptConfirm = false">
      <div class="modal-panel modal-panel--sm">
        <h3 class="modal-title">确认删除</h3>
        <p class="delete-text">确定要删除部门「{{ deleteDeptTarget?.name }}」吗？此操作不可撤销。</p>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showDeleteDeptConfirm = false">取消</button>
          <button class="btn btn-danger" @click="doDeleteDept" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Save/Edit Snapshot modal -->
    <div class="modal-overlay" v-if="showSnapshotModal" @click.self="closeSnapshotModal">
      <div class="modal-panel modal-panel--sm">
        <h3 class="modal-title">{{ snapshotModalMode === 'edit' ? '编辑排序存档' : '保存当前部门排序' }}</h3>
        <div class="modal-body">
          <div class="form-group" v-if="snapshotModalMode === 'save'">
            <label class="form-label">保存方式</label>
            <select v-model="snapshotForm.overwrite_id" class="form-select" @change="onOverwriteChange">
              <option :value="null">-- 新增为新存档 --</option>
              <option v-for="s in snapshots" :key="s.id" :value="s.id">覆盖已保存的「{{ s.name }}」</option>
            </select>
            <span class="form-hint">选择已有存档将用当前排序覆盖它，否则新增一份存档</span>
          </div>
          <div class="form-group">
            <label class="form-label">存档名称 <span class="required">*</span></label>
            <input v-model="snapshotForm.name" class="form-input" placeholder="如：默认排序" />
          </div>
          <div class="form-group">
            <label class="form-label">备注</label>
            <textarea v-model="snapshotForm.note" class="form-textarea" placeholder="可选，如：XX会议使用 / 按公司最新架构" rows="3"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="closeSnapshotModal">取消</button>
          <button class="btn btn-primary" @click="doSaveSnapshot" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Delete Snapshot confirm modal -->
    <div class="modal-overlay" v-if="showDeleteSnapshotConfirm" @click.self="showDeleteSnapshotConfirm = false">
      <div class="modal-panel modal-panel--sm">
        <h3 class="modal-title">确认删除</h3>
        <p class="delete-text">确定要删除存档「{{ deleteSnapshotTarget?.name }}」吗？此操作不可撤销。</p>
        <div class="modal-footer">
          <button class="btn btn-outline" @click="showDeleteSnapshotConfirm = false">取消</button>
          <button class="btn btn-danger" @click="doDeleteSnapshot" :disabled="deleting">
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import {
  fetchDepartmentsTree,
  fetchDeptCategories,
  createDeptCategory,
  updateDeptCategory,
  deleteDeptCategory,
  reorderDeptCategories,
  createDepartment,
  updateDepartment,
  deleteDepartment,
  reorderDepartments,
  seedDeptTree,
  rescan,
  fetchDeptSnapshots,
  createDeptSnapshot,
  updateDeptSnapshot,
  deleteDeptSnapshot,
  applyDeptSnapshot,
  type DepartmentTreeNode,
  type DeptCategory,
  type Department,
  type DeptSnapshot,
} from '../api'

// ─── Data ──────────────────────────────────────────────────────
const treeData = ref<DepartmentTreeNode[]>([])
const categories = ref<DeptCategory[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
// 展开/折叠状态按分类 ID 存储，排序后重新加载也能保持（不随索引变化丢失）
const expandedCategories = ref<Record<string, boolean>>({})
// 分类行 DOM 元素引用，用于排序后定位到当前调整的分类
const catRowEls = ref<Record<string, HTMLElement>>({})

/** 分类展开状态的稳定 key（未归类分类 id 为 null） */
function catKey(cat: { id: number | null }): string {
  return cat.id === null ? 'uncategorized' : String(cat.id)
}

function isCatExpanded(cat: DepartmentTreeNode): boolean {
  return !!expandedCategories.value[catKey(cat)]
}

function setCatRowRef(cat: DepartmentTreeNode, el: unknown) {
  const key = catKey(cat)
  if (el) {
    catRowEls.value[key] = el as HTMLElement
  } else {
    delete catRowEls.value[key]
  }
}

// Drag & drop reorder state
const draggingCatIdx = ref<number | null>(null)
const dragOverCatIdx = ref<number | null>(null)
const draggingDept = ref<{ catIdx: number; deptIdx: number } | null>(null)
const dragOverDept = ref<{ catIdx: number; deptIdx: number } | null>(null)

// ─── Category Modal ────────────────────────────────────────────
const showCategoryModal = ref(false)
const isEditingCategory = ref(false)
const editingCategoryId = ref<number | null>(null)
const categoryForm = reactive({ name: '' })

// ─── Dept Modal ────────────────────────────────────────────────
const showDeptModal = ref(false)
const isEditingDept = ref(false)
const editingDeptId = ref<number | null>(null)
const deptForm = reactive({
  name: '',
  category_id: null as number | null,
  description: null as string | null,
})

// ─── Delete Category ──────────────────────────────────────────
const showDeleteCategoryConfirm = ref(false)
const deleteCategoryTarget = ref<DeptCategory | null>(null)

// ─── Delete Department ────────────────────────────────────────
const showDeleteDeptConfirm = ref(false)
const deleteDeptTarget = ref<Department | null>(null)

// ─── Sort Snapshots (存档) ───────────────────────────────────
const snapshots = ref<DeptSnapshot[]>([])
const showSnapshotModal = ref(false)
const snapshotModalMode = ref<'save' | 'edit'>('save')
const editingSnapshotId = ref<number | null>(null)
const snapshotForm = reactive({ name: '', note: '', overwrite_id: null as number | null })
const showDeleteSnapshotConfirm = ref(false)
const deleteSnapshotTarget = ref<DeptSnapshot | null>(null)

// ─── Methods ───────────────────────────────────────────────────

/**
 * 加载分类树。默认保留上一次的展开/折叠状态（新出现的分类默认展开）；
 * 传入 focusCatId 时，会展开并滚动定位到该分类，方便排序后回到调整位置。
 */
async function loadTreeData(opts?: { focusCatId?: number | null }) {
  loading.value = true
  try {
    const [treeRes, catRes] = await Promise.all([
      fetchDepartmentsTree(),
      fetchDeptCategories(),
    ])
    treeData.value = treeRes.data
    categories.value = catRes.data
    // Preserve expand/collapse state keyed by category id; new categories default to expanded
    const next: Record<string, boolean> = {}
    for (const cat of treeData.value) {
      next[catKey(cat)] = expandedCategories.value[catKey(cat)] ?? true
    }
    expandedCategories.value = next
  } catch (e) {
    console.error('Failed to load department tree:', e)
  } finally {
    loading.value = false
  }
  // Locate the just-adjusted category: expand it and scroll into view
  if (opts && opts.focusCatId !== undefined) {
    await nextTick()
    const key = opts.focusCatId === null ? 'uncategorized' : String(opts.focusCatId)
    if (key in expandedCategories.value) {
      expandedCategories.value[key] = true
    }
    await nextTick()
    const el = catRowEls.value[key]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }
}

function toggleCategory(cat: DepartmentTreeNode) {
  const key = catKey(cat)
  expandedCategories.value[key] = !expandedCategories.value[key]
}

// ─── Expand / Collapse all ────────────────────────────────────

const allExpanded = computed(() => {
  return treeData.value.length > 0 && treeData.value.every(c => isCatExpanded(c))
})

const allCollapsed = computed(() => {
  return treeData.value.length > 0 && treeData.value.every(c => !isCatExpanded(c))
})

function expandAllCategories() {
  const expanded: Record<string, boolean> = {}
  treeData.value.forEach(c => { expanded[catKey(c)] = true })
  expandedCategories.value = expanded
}

function collapseAllCategories() {
  const expanded: Record<string, boolean> = {}
  treeData.value.forEach(c => { expanded[catKey(c)] = false })
  expandedCategories.value = expanded
}

/** Get a category's position among sortable (id !== null) categories */
function sortableCatIdx(catIdx: number): number {
  let pos = 0
  for (let i = 0; i < catIdx; i++) {
    if (treeData.value[i]?.id !== null) pos++
  }
  return pos
}

/** Total number of sortable categories (id !== null) */
function sortableCatCount(): number {
  return treeData.value.filter(c => c.id !== null).length
}

// ─── Drag & Drop Reorder ─────────────────────────────────────

function onCatDragStart(catIdx: number, e: DragEvent) {
  const cat = treeData.value[catIdx]
  if (!cat || cat.id === null) return
  draggingCatIdx.value = catIdx
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(cat.id))
  }
}

function onCatDragOver(catIdx: number, e: DragEvent) {
  if (draggingCatIdx.value === null) return
  const cat = treeData.value[catIdx]
  if (!cat || cat.id === null) return
  if (draggingCatIdx.value === catIdx) return
  e.preventDefault()
  dragOverCatIdx.value = catIdx
}

function onCatDrop(catIdx: number, e: DragEvent) {
  e.preventDefault()
  const from = draggingCatIdx.value
  draggingCatIdx.value = null
  dragOverCatIdx.value = null
  if (from === null || from === catIdx) return
  moveCategoryTo(from, catIdx)
}

function onCatDragEnd() {
  draggingCatIdx.value = null
  dragOverCatIdx.value = null
}

async function moveCategoryTo(fromIdx: number, toIdx: number) {
  // Reorder among sortable categories only (exclude uncategorized)
  const filterable = treeData.value
    .map((c, i) => ({ c, i }))
    .filter(x => x.c.id !== null)
  const fromPos = filterable.findIndex(x => x.i === fromIdx)
  const toPos = filterable.findIndex(x => x.i === toIdx)
  if (fromPos < 0 || toPos < 0 || fromPos === toPos) return

  const arr = filterable.slice()
  const [moved] = arr.splice(fromPos, 1)
  arr.splice(toPos, 0, moved)

  const items = arr.map((x, idx) => ({ id: x.c.id!, sort_order: idx }))
  const focusCatId = treeData.value[fromIdx]?.id ?? null
  try {
    await reorderDeptCategories(items)
    await loadTreeData({ focusCatId })
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

function onDeptDragStart(catIdx: number, deptIdx: number, e: DragEvent) {
  const cat = treeData.value[catIdx]
  if (!cat || !cat.departments[deptIdx]) return
  draggingDept.value = { catIdx, deptIdx }
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(cat.departments[deptIdx].id))
  }
}

function onDeptDragOver(catIdx: number, deptIdx: number, e: DragEvent) {
  const drag = draggingDept.value
  if (!drag) return
  // Departments can only be reordered within their own category
  if (drag.catIdx !== catIdx) return
  if (drag.deptIdx === deptIdx) return
  e.preventDefault()
  dragOverDept.value = { catIdx, deptIdx }
}

function onDeptDrop(catIdx: number, deptIdx: number, e: DragEvent) {
  e.preventDefault()
  const drag = draggingDept.value
  draggingDept.value = null
  dragOverDept.value = null
  if (!drag || drag.catIdx !== catIdx || drag.deptIdx === deptIdx) return
  moveDeptTo(catIdx, drag.deptIdx, deptIdx)
}

function onDeptDragEnd() {
  draggingDept.value = null
  dragOverDept.value = null
}

async function moveDeptTo(catIdx: number, fromDeptIdx: number, toDeptIdx: number) {
  const cat = treeData.value[catIdx]
  if (!cat) return
  const arr = cat.departments.slice()
  const [moved] = arr.splice(fromDeptIdx, 1)
  arr.splice(toDeptIdx, 0, moved)

  const items = arr.map((d, idx) => ({ id: d.id, sort_order: idx }))
  const focusCatId = cat.id
  try {
    await reorderDepartments(items)
    await loadTreeData({ focusCatId })
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

function isDeptDragging(catIdx: number, deptIdx: number): boolean {
  const drag = draggingDept.value
  return !!drag && drag.catIdx === catIdx && drag.deptIdx === deptIdx
}

function isDeptDragOver(catIdx: number, deptIdx: number): boolean {
  const over = dragOverDept.value
  return !!over && over.catIdx === catIdx && over.deptIdx === deptIdx
}

// ─── Category CRUD ─────────────────────────────────────────────

function openAddCategory() {
  isEditingCategory.value = false
  editingCategoryId.value = null
  categoryForm.name = ''
  showCategoryModal.value = true
}

function openEditCategory(cat: DepartmentTreeNode) {
  if (cat.id === null) return // Cannot edit "uncategorized"
  isEditingCategory.value = true
  editingCategoryId.value = cat.id
  categoryForm.name = cat.name
  showCategoryModal.value = true
}

function closeCategoryModal() {
  showCategoryModal.value = false
}

async function saveCategory() {
  if (!categoryForm.name.trim()) {
    alert('请输入分类名称')
    return
  }
  saving.value = true
  try {
    if (isEditingCategory.value && editingCategoryId.value) {
      await updateDeptCategory(editingCategoryId.value, { name: categoryForm.name })
    } else {
      await createDeptCategory({ name: categoryForm.name })
    }
    showCategoryModal.value = false
    await loadTreeData()
  } catch (e: any) {
    console.error('Save category failed:', e)
    alert(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function confirmDeleteCategory(cat: DepartmentTreeNode) {
  if (cat.id === null) return // Cannot delete "uncategorized"
  deleteCategoryTarget.value = { id: cat.id, name: cat.name, sort_order: cat.sort_order }
  showDeleteCategoryConfirm.value = true
}

async function doDeleteCategory() {
  if (!deleteCategoryTarget.value) return
  deleting.value = true
  try {
    await deleteDeptCategory(deleteCategoryTarget.value.id)
    showDeleteCategoryConfirm.value = false
    deleteCategoryTarget.value = null
    await loadTreeData()
  } catch (e: any) {
    console.error('Delete category failed:', e)
    alert(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

async function moveCategoryUp(catIdx: number) {
  const targetCat = treeData.value[catIdx]
  if (!targetCat || targetCat.id === null) return
  // Build reorder list from filterable categories only (exclude uncategorized)
  const filterable = treeData.value.filter(c => c.id !== null)
  const items = filterable.map((c, i) => ({ id: c.id!, sort_order: i }))
  // Find target position in the filtered list
  const targetIdx = filterable.findIndex(c => c.id === targetCat.id)
  if (targetIdx <= 0) return // Already at top
  // Swap sort_order with the one above
  const a = items[targetIdx - 1]
  const b = items[targetIdx]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  try {
    await reorderDeptCategories(items)
    await loadTreeData({ focusCatId: targetCat.id })
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

async function moveCategoryDown(catIdx: number) {
  const targetCat = treeData.value[catIdx]
  if (!targetCat || targetCat.id === null) return
  // Build reorder list from filterable categories only (exclude uncategorized)
  const filterable = treeData.value.filter(c => c.id !== null)
  const items = filterable.map((c, i) => ({ id: c.id!, sort_order: i }))
  // Find target position in the filtered list
  const targetIdx = filterable.findIndex(c => c.id === targetCat.id)
  if (targetIdx < 0 || targetIdx >= filterable.length - 1) return // Already at bottom
  // Swap sort_order with the one below
  const a = items[targetIdx]
  const b = items[targetIdx + 1]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  try {
    await reorderDeptCategories(items)
    await loadTreeData({ focusCatId: targetCat.id })
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

// ─── Department CRUD ───────────────────────────────────────────

function openAddDeptToCategory(cat: DepartmentTreeNode) {
  isEditingDept.value = false
  editingDeptId.value = null
  deptForm.name = ''
  deptForm.category_id = cat.id
  deptForm.description = null
  showDeptModal.value = true
}

function openEditDept(dept: Department) {
  isEditingDept.value = true
  editingDeptId.value = dept.id
  deptForm.name = dept.name
  deptForm.category_id = dept.category_id ?? null
  deptForm.description = dept.description ?? null
  showDeptModal.value = true
}

function closeDeptModal() {
  showDeptModal.value = false
}

async function saveDept() {
  if (!deptForm.name.trim()) {
    alert('请输入部门名称')
    return
  }
  if (!deptForm.category_id) {
    alert('请选择所属分类')
    return
  }
  saving.value = true
  try {
    if (isEditingDept.value && editingDeptId.value) {
      await updateDepartment(editingDeptId.value, {
        name: deptForm.name,
        category_id: deptForm.category_id,
        description: deptForm.description,
      })
    } else {
      await createDepartment({
        name: deptForm.name,
        category_id: deptForm.category_id,
        description: deptForm.description,
      })
    }
    showDeptModal.value = false
    await loadTreeData()
  } catch (e: any) {
    console.error('Save department failed:', e)
    alert(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function confirmDeleteDept(dept: Department) {
  deleteDeptTarget.value = dept
  showDeleteDeptConfirm.value = true
}

async function doDeleteDept() {
  if (!deleteDeptTarget.value) return
  deleting.value = true
  try {
    await deleteDepartment(deleteDeptTarget.value.id)
    showDeleteDeptConfirm.value = false
    deleteDeptTarget.value = null
    await loadTreeData()
  } catch (e: any) {
    console.error('Delete department failed:', e)
    alert(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

async function moveDeptUp(catIdx: number, deptIdx: number) {
  if (deptIdx <= 0) return
  const cat = treeData.value[catIdx]
  if (!cat) return
  const items = cat.departments.map((d, i) => ({ id: d.id, sort_order: i }))
  // Swap sort_order
  const a = items[deptIdx - 1]
  const b = items[deptIdx]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  try {
    await reorderDepartments(items)
    await loadTreeData({ focusCatId: cat.id })
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

async function moveDeptDown(catIdx: number, deptIdx: number) {
  const cat = treeData.value[catIdx]
  if (!cat || deptIdx >= cat.departments.length - 1) return
  const items = cat.departments.map((d, i) => ({ id: d.id, sort_order: i }))
  // Swap sort_order
  const a = items[deptIdx]
  const b = items[deptIdx + 1]
  const tmp = a.sort_order
  a.sort_order = b.sort_order
  b.sort_order = tmp
  try {
    await reorderDepartments(items)
    await loadTreeData({ focusCatId: cat.id })
  } catch (e: any) {
    console.error('Reorder failed:', e)
    alert('排序调整失败')
  }
}

// ─── Sort Snapshots (存档) ────────────────────────────────────

async function loadSnapshots() {
  try {
    const res = await fetchDeptSnapshots()
    snapshots.value = res.data
  } catch (e) {
    console.error('Failed to load snapshots:', e)
  }
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function openSaveSnapshot() {
  snapshotModalMode.value = 'save'
  editingSnapshotId.value = null
  snapshotForm.name = ''
  snapshotForm.note = ''
  snapshotForm.overwrite_id = null
  showSnapshotModal.value = true
}

/** 选择覆盖某个已有存档时，自动带出其名称与备注，便于确认要覆盖的对象 */
function onOverwriteChange() {
  if (snapshotForm.overwrite_id === null) return
  const s = snapshots.value.find(x => x.id === snapshotForm.overwrite_id)
  if (s) {
    snapshotForm.name = s.name
    snapshotForm.note = s.note || ''
  }
}

function openEditSnapshot(s: DeptSnapshot) {
  snapshotModalMode.value = 'edit'
  editingSnapshotId.value = s.id
  snapshotForm.name = s.name
  snapshotForm.note = s.note || ''
  showSnapshotModal.value = true
}

function closeSnapshotModal() {
  showSnapshotModal.value = false
}

async function doSaveSnapshot() {
  if (!snapshotForm.name.trim()) {
    alert('请输入存档名称')
    return
  }
  saving.value = true
  try {
    if (snapshotModalMode.value === 'edit' && editingSnapshotId.value) {
      await updateDeptSnapshot(editingSnapshotId.value, {
        name: snapshotForm.name.trim(),
        note: snapshotForm.note.trim() || null,
      })
    } else if (snapshotForm.overwrite_id) {
      // 覆盖已保存的存档：同时用当前部门排序刷新其数据
      await updateDeptSnapshot(snapshotForm.overwrite_id, {
        name: snapshotForm.name.trim(),
        note: snapshotForm.note.trim() || null,
        recapture: true,
      })
    } else {
      await createDeptSnapshot({
        name: snapshotForm.name.trim(),
        note: snapshotForm.note.trim() || null,
      })
    }
    showSnapshotModal.value = false
    await loadSnapshots()
  } catch (e: any) {
    console.error('Save snapshot failed:', e)
    alert(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function handleApplySnapshot(s: DeptSnapshot) {
  if (!confirm(`确定要读取存档「${s.name}」吗？\n当前部门排序将被覆盖为存档中的顺序。`)) return
  try {
    await applyDeptSnapshot(s.id)
    alert('已恢复存档排序')
    await loadTreeData()
    await loadSnapshots()
  } catch (e: any) {
    console.error('Apply snapshot failed:', e)
    alert(e?.response?.data?.detail || '读取存档失败')
  }
}

function confirmDeleteSnapshot(s: DeptSnapshot) {
  deleteSnapshotTarget.value = s
  showDeleteSnapshotConfirm.value = true
}

async function doDeleteSnapshot() {
  if (!deleteSnapshotTarget.value) return
  deleting.value = true
  try {
    await deleteDeptSnapshot(deleteSnapshotTarget.value.id)
    showDeleteSnapshotConfirm.value = false
    deleteSnapshotTarget.value = null
    await loadSnapshots()
  } catch (e: any) {
    console.error('Delete snapshot failed:', e)
    alert(e?.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

// ─── Utility ───────────────────────────────────────────────────

async function handleSeedTree() {
  if (!confirm('重置分类树将覆盖现有分类排序，是否继续？')) return
  try {
    await seedDeptTree()
    alert('分类树已重置')
    await loadTreeData()
  } catch (e: any) {
    console.error('Seed tree failed:', e)
    alert('重置失败')
  }
}

async function initFromPhotos() {
  try {
    const res = await rescan()
    alert(`初始化完成，从照片中导入了 ${res.data.count} 人，部门信息已同步更新。`)
    await loadTreeData()
  } catch (e: any) {
    console.error('Init failed:', e)
    alert('初始化失败，请检查 photos 目录是否存在')
  }
}

// ─── Lifecycle ─────────────────────────────────────────────────

onMounted(() => {
  loadTreeData()
  loadSnapshots()
})
</script>

<style scoped>
.dept-manage {
  /* container */
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 12px;
}

.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a2e;
}

.header-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
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

.tree-hint {
  font-size: 12px;
  color: #aaa;
  margin-bottom: 12px;
}

/* ─── Drag & Drop ─────────────────────────── */
.tree-row[draggable='true'] {
  cursor: grab;
}

.tree-row--dragging {
  opacity: 0.45;
  background: #eef4ff !important;
  cursor: grabbing;
}

.tree-row--drag-over {
  background: #f0f5ff !important;
  box-shadow: inset 0 2px 0 0 #1677ff;
}

/* ─── Tree Structure ─────────────────────────── */
.tree-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 10px;
}

.tree-container {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.tree-group {
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  margin-bottom: 8px;
}

.tree-row {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border-bottom: 1px solid #f5f5f5;
  transition: background 0.15s;
}

.tree-row:hover {
  background: #fafbff;
}

.tree-row:last-child {
  border-bottom: none;
}

.tree-row--category {
  font-weight: 600;
  background: #f7f8fa;
}

.tree-row--category:hover {
  background: #f0f2f5;
}

.tree-row--uncategorized {
  background: #fff8e1;
  color: #a67c00;
}

.tree-row--dept {
  padding-left: 48px;
}

.tree-row--empty {
  padding-left: 48px;
  color: #bbb;
  font-size: 13px;
  font-style: italic;
}

.toggle-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
  margin-right: 6px;
  font-size: 12px;
  color: #666;
  display: flex;
  align-items: center;
}

.toggle-icon {
  display: inline-block;
  transition: transform 0.2s;
  font-size: 10px;
}

.toggle-icon--expanded {
  transform: rotate(90deg);
}

.category-name {
  font-size: 15px;
  color: #1a1a2e;
  flex: 1;
}

.category-count {
  font-size: 12px;
  color: #999;
  font-weight: 400;
  margin-right: 12px;
}

.dept-name {
  flex: 1;
  font-size: 14px;
  color: #333;
  font-weight: 400;
}

.row-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* ─── Sort Snapshots (存档) ─────────────────────── */
.snapshot-section {
  margin-top: 28px;
}

.snapshot-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.snapshot-title {
  font-size: 16px;
  font-weight: 700;
  color: #1a1a2e;
}

.snapshot-hint {
  font-size: 12px;
  color: #aaa;
  margin-bottom: 12px;
}

.snapshot-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.snapshot-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  gap: 12px;
  flex-wrap: wrap;
}

.snapshot-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
  flex-wrap: wrap;
}

.snapshot-name {
  font-size: 14px;
  font-weight: 600;
  color: #1a1a2e;
}

.snapshot-note {
  font-size: 12px;
  color: #888;
}

.snapshot-meta {
  font-size: 12px;
  color: #bbb;
}

.snapshot-empty {
  text-align: center;
  padding: 24px;
  color: #bbb;
  font-size: 13px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
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
  padding: 4px 10px;
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
  width: 520px;
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
  line-height: 1.6;
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
</style>
