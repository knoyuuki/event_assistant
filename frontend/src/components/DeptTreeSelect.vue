<template>
  <div class="dept-tree-select" ref="selectRef">
    <div
      class="select-trigger"
      :class="{ 'select-trigger--active': isOpen, 'select-trigger--disabled': disabled }"
      @click="toggle"
    >
      <span class="select-value" :class="{ 'select-value--placeholder': !modelValue }">
        {{ displayValue }}
      </span>
      <span class="select-arrow" :class="{ 'select-arrow--open': isOpen }">▾</span>
    </div>
    <div class="select-dropdown" v-if="isOpen">
      <!-- Search input -->
      <div class="dropdown-search">
        <input
          v-model="searchText"
          class="dropdown-search-input"
          placeholder="搜索部门..."
          ref="searchInputRef"
        />
        <button v-if="searchText" class="dropdown-search-clear" @click="searchText = ''">&times;</button>
      </div>
      <!-- "全部部门" option (optional, for filter mode) -->
      <div
        v-if="showAll && !searchText"
        class="dropdown-item dropdown-item--all"
        :class="{ 'dropdown-item--selected': modelValue === '' }"
        @click="select('')"
      >
        全部部门
      </div>
      <!-- Category groups (filtered) -->
      <template v-for="cat in filteredTreeData" :key="cat.id ?? 'uncategorized'">
        <div class="dropdown-group-header">
          {{ cat.name }}
        </div>
        <div
          v-for="dept in cat.departments"
          :key="dept.id"
          class="dropdown-item dropdown-item--dept"
          :class="{ 'dropdown-item--selected': modelValue === dept.name }"
          @click="select(dept.name)"
        >
          {{ dept.name }}
        </div>
      </template>
      <!-- Empty state -->
      <div v-if="searchText && !filteredTreeData.length" class="dropdown-empty">
        未找到匹配的部门
      </div>
      <div v-if="!searchText && !treeData.length" class="dropdown-empty">暂无部门数据</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import type { DepartmentTreeNode } from '../api'

const props = withDefaults(defineProps<{
  modelValue: string
  treeData: DepartmentTreeNode[]
  placeholder?: string
  showAll?: boolean
  disabled?: boolean
}>(), {
  placeholder: '请选择部门',
  showAll: false,
  disabled: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isOpen = ref(false)
const searchText = ref('')
const selectRef = ref<HTMLElement | null>(null)
const searchInputRef = ref<HTMLInputElement | null>(null)

const displayValue = computed(() => {
  if (!props.modelValue) return props.placeholder
  return props.modelValue
})

const filteredTreeData = computed(() => {
  if (!searchText.value) return props.treeData
  const q = searchText.value.toLowerCase()
  return props.treeData
    .map(cat => ({
      ...cat,
      departments: cat.departments.filter(d => d.name.toLowerCase().includes(q)),
    }))
    .filter(cat => cat.departments.length > 0)
})

function toggle() {
  if (props.disabled) return
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    searchText.value = ''
    nextTick(() => {
      searchInputRef.value?.focus()
    })
  }
}

function select(name: string) {
  emit('update:modelValue', name)
  searchText.value = ''
  isOpen.value = false
}

function onClickOutside(e: MouseEvent) {
  if (selectRef.value && !selectRef.value.contains(e.target as Node)) {
    isOpen.value = false
    searchText.value = ''
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.dept-tree-select {
  position: relative;
  display: inline-block;
  width: 100%;
}

.select-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  background: #fff;
  transition: border-color 0.2s;
  user-select: none;
  min-height: 36px;
}

.select-trigger:hover {
  border-color: #4096ff;
}

.select-trigger--active {
  border-color: #1677ff;
  box-shadow: 0 0 0 2px rgba(22, 119, 255, 0.1);
}

.select-trigger--disabled {
  background: #f5f5f5;
  color: #999;
  cursor: not-allowed;
}

.select-trigger--disabled:hover {
  border-color: #d9d9d9;
}

.select-value {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.select-value--placeholder {
  color: #bbb;
}

.select-arrow {
  font-size: 12px;
  color: #999;
  margin-left: 8px;
  transition: transform 0.2s;
}

.select-arrow--open {
  transform: rotate(180deg);
}

.select-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.08), 0 3px 6px rgba(0, 0, 0, 0.05);
  z-index: 500;
  max-height: 360px;
  overflow-y: auto;
  padding: 4px 0;
}

/* ─── Search ──────────────────────────── */
.dropdown-search {
  display: flex;
  align-items: center;
  padding: 6px 10px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
  position: sticky;
  top: 0;
  z-index: 2;
}

.dropdown-search-input {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  font-size: 13px;
  outline: none;
  background: #fafafa;
  transition: border-color 0.2s;
}

.dropdown-search-input:focus {
  border-color: #1677ff;
  background: #fff;
}

.dropdown-search-clear {
  background: none;
  border: none;
  font-size: 16px;
  color: #999;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  margin-left: 4px;
}

.dropdown-search-clear:hover {
  color: #555;
}

/* ─── Items ──────────────────────────── */
.dropdown-group-header {
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #555;
  background: #f7f8fa;
  border-bottom: 1px solid #f0f0f0;
  user-select: none;
  position: sticky;
  top: 0;
  z-index: 1;
}

.dropdown-group-header:not(:first-child) {
  margin-top: 2px;
  border-top: 1px solid #f0f0f0;
}

.dropdown-item {
  padding: 7px 12px 7px 24px;
  font-size: 14px;
  color: #333;
  cursor: pointer;
  transition: background 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-item:hover {
  background: #f0f5ff;
}

.dropdown-item--all {
  padding-left: 12px;
  font-weight: 500;
  color: #1677ff;
}

.dropdown-item--selected {
  color: #1677ff;
  font-weight: 500;
  background: #f0f5ff;
}

.dropdown-item--selected::after {
  content: ' ✓';
  color: #1677ff;
}

.dropdown-empty {
  padding: 20px 12px;
  text-align: center;
  color: #bbb;
  font-size: 13px;
}
</style>
