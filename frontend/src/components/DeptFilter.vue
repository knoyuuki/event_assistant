<template>
  <div class="dept-filter">
    <div class="filter-row">
      <label class="filter-label">部门筛选</label>
      <DeptTreeSelect
        v-model="selectedDept"
        :tree-data="treeData"
        :show-all="true"
        placeholder="全部部门"
        style="min-width: 180px"
        @update:model-value="onFilterChange"
      />
    </div>
    <div class="filter-row" v-if="showModeToggle">
      <label class="filter-label">遍历模式</label>
      <div class="mode-toggle">
        <button
          :class="['mode-btn', { 'mode-btn--active': mode === 'sequential' }]"
          @click="setMode('sequential')"
        >
          顺序遍历
        </button>
        <button
          :class="['mode-btn', { 'mode-btn--active': mode === 'random' }]"
          @click="setMode('random')"
        >
          乱序遍历
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchDepartmentsTree, type DepartmentTreeNode } from '../api'
import DeptTreeSelect from './DeptTreeSelect.vue'

const props = defineProps<{
  showModeToggle?: boolean
}>()

const emit = defineEmits<{
  'update:department': [value: string]
  'update:mode': [value: 'sequential' | 'random']
}>()

const treeData = ref<DepartmentTreeNode[]>([])
const selectedDept = ref('')
const mode = ref<'sequential' | 'random'>('sequential')

onMounted(async () => {
  try {
    const res = await fetchDepartmentsTree()
    treeData.value = res.data
  } catch (e) {
    console.error('Failed to fetch departments tree:', e)
  }
})

function onFilterChange() {
  emit('update:department', selectedDept.value)
}

function setMode(val: 'sequential' | 'random') {
  mode.value = val
  emit('update:mode', val)
}
</script>

<style scoped>
.dept-filter {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 12px 20px;
  background: #fff;
  border-radius: 10px;
  margin-bottom: 20px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
  flex-wrap: wrap;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 14px;
  font-weight: 500;
  color: #666;
  white-space: nowrap;
}

.mode-toggle {
  display: flex;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid #d9d9d9;
}

.mode-btn {
  padding: 6px 16px;
  border: none;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  color: #666;
}

.mode-btn:not(:last-child) {
  border-right: 1px solid #d9d9d9;
}

.mode-btn:hover {
  background: #f0f5ff;
}

.mode-btn--active {
  background: #1677ff;
  color: #fff;
}
</style>
