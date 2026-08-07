<template>
  <div class="browse-view">
    <DeptFilter
      show-mode-toggle
      @update:department="onDeptChange"
      @update:mode="onModeChange"
    />

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!persons.length" class="empty">
      <p>暂无人员数据</p>
      <p class="empty-hint">请将照片放入 photos 目录，文件命名格式：姓名-部门-职位.jpg</p>
      <button class="rescan-btn" @click="doRescan">重新扫描</button>
    </div>

    <template v-else>
      <!-- Progress indicator -->
      <div class="browse-progress">
        <span class="progress-text">{{ currentIndex + 1 }} / {{ persons.length }}</span>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: ((currentIndex + 1) / persons.length * 100) + '%' }"></div>
        </div>
      </div>

      <!-- Photo display -->
      <PhotoCard :person="persons[currentIndex]" :show-info="true" />

      <!-- Navigation -->
      <div class="browse-nav">
        <button
          class="nav-btn"
          @click="prevPerson"
          :disabled="currentIndex === 0"
        >
          ← 上一个
        </button>
        <span class="nav-counter">{{ currentIndex + 1 }} / {{ persons.length }}</span>
        <button
          class="nav-btn"
          @click="nextPerson"
          :disabled="currentIndex === persons.length - 1"
        >
          下一个 →
        </button>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { fetchPersonsSequential, fetchPersonsRandom, rescan, type Person } from '../api'
import PhotoCard from '../components/PhotoCard.vue'
import DeptFilter from '../components/DeptFilter.vue'

const persons = ref<Person[]>([])
const loading = ref(false)
const currentIndex = ref(0)
const currentDept = ref('')
const currentMode = ref<'sequential' | 'random'>('sequential')

async function loadPersons() {
  loading.value = true
  try {
    const fetcher = currentMode.value === 'sequential' ? fetchPersonsSequential : fetchPersonsRandom
    const res = await fetcher(currentDept.value || undefined)
    persons.value = res.data
    currentIndex.value = 0
  } catch (e) {
    console.error('Failed to load persons:', e)
  } finally {
    loading.value = false
  }
}

function onDeptChange(dept: string) {
  currentDept.value = dept
  loadPersons()
}

function onModeChange(mode: 'sequential' | 'random') {
  currentMode.value = mode
  loadPersons()
}

function prevPerson() {
  if (currentIndex.value > 0) {
    currentIndex.value--
  }
}

function nextPerson() {
  if (currentIndex.value < persons.value.length - 1) {
    currentIndex.value++
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prevPerson()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    nextPerson()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

async function doRescan() {
  try {
    await rescan()
    await loadPersons()
  } catch (e) {
    console.error('Rescan failed:', e)
  }
}

// Load on mount
loadPersons()
</script>

<style scoped>
.browse-view {
  /* container */
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

.rescan-btn {
  margin-top: 16px;
  padding: 8px 24px;
  border: 1px solid #1677ff;
  background: #fff;
  color: #1677ff;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
}

.rescan-btn:hover {
  background: #e6f4ff;
}

.browse-progress {
  margin-bottom: 16px;
}

.progress-text {
  font-size: 13px;
  color: #888;
  margin-bottom: 4px;
  display: block;
}

.progress-bar {
  height: 4px;
  background: #e8e8e8;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #1677ff;
  border-radius: 2px;
  transition: width 0.3s;
}

.browse-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20px;
  margin-top: 20px;
}

.nav-btn {
  padding: 10px 24px;
  border: 1px solid #d9d9d9;
  background: #fff;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s;
  color: #333;
}

.nav-btn:hover:not(:disabled) {
  border-color: #1677ff;
  color: #1677ff;
}

.nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.nav-counter {
  font-size: 14px;
  color: #888;
  min-width: 60px;
  text-align: center;
}
</style>
