<template>
  <div class="test-view">
    <DeptFilter
      @update:department="onDeptChange"
    />

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!persons.length" class="empty">
      <p>暂无人员数据，请先在浏览模式下确认数据已加载</p>
    </div>

    <template v-else>
      <!-- Progress -->
      <div class="browse-progress">
        <span class="progress-text">{{ currentIndex + 1 }} / {{ persons.length }}</span>
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: ((currentIndex + 1) / persons.length * 100) + '%' }"></div>
        </div>
      </div>

      <!-- Photo display (name hidden by default) -->
      <PhotoCard
        :person="persons[currentIndex]"
        :show-info="revealed.has(persons[currentIndex].id)"
        :show-hidden-placeholder="!revealed.has(persons[currentIndex].id)"
      />

      <!-- Answer input area -->
      <div class="answer-section">
        <div class="answer-row">
          <input
            v-model="answers[currentIndex]"
            type="text"
            class="answer-input"
            placeholder="输入姓名..."
            @keyup.enter="goNextOrSubmit"
          />
          <button class="reveal-btn" @click="revealAnswer(currentIndex)">
            {{ revealed.has(persons[currentIndex].id) ? '已显示' : '查看答案' }}
          </button>
        </div>
        <div v-if="revealed.has(persons[currentIndex].id)" class="reveal-answer-text">
          正确答案：<strong>{{ persons[currentIndex].name }}</strong>
        </div>
      </div>

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
          @click="goNextOrSubmit"
        >
          {{ currentIndex === persons.length - 1 ? '提交测试' : '下一个 →' }}
        </button>
      </div>

      <!-- Quick submit -->
      <div class="submit-row">
        <button class="submit-btn" @click="submitTest">📝 提交测试</button>
        <button class="reset-btn" @click="resetTest">🔄 重新开始</button>
      </div>
    </template>

    <!-- Score board modal -->
    <ScoreBoard
      :result="testResult"
      :show="showScore"
      @close="showScore = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { fetchPersonsRandom, checkAnswers, saveTestResult, type Person, type CheckResult } from '../api'
import PhotoCard from '../components/PhotoCard.vue'
import DeptFilter from '../components/DeptFilter.vue'
import ScoreBoard from '../components/ScoreBoard.vue'

const persons = ref<Person[]>([])
const loading = ref(false)
const currentIndex = ref(0)
const currentDept = ref('')

// answers array: index in persons array -> user-typed name string
const answers = ref<string[]>([])

// Set of person IDs whose answer has been revealed
const revealed = ref<Set<number>>(new Set())

const testResult = ref<CheckResult | null>(null)
const showScore = ref(false)

async function loadPersons() {
  loading.value = true
  try {
    const res = await fetchPersonsRandom(currentDept.value || undefined)
    persons.value = res.data
    currentIndex.value = 0
    // Initialize answers array
    answers.value = new Array(persons.value.length).fill('')
    revealed.value = new Set()
    showScore.value = false
    testResult.value = null
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

function prevPerson() {
  if (currentIndex.value > 0) {
    currentIndex.value--
  }
}

function goNextOrSubmit() {
  if (currentIndex.value < persons.value.length - 1) {
    currentIndex.value++
  } else {
    submitTest()
  }
}

function revealAnswer(idx: number) {
  const person = persons.value[idx]
  if (person) {
    revealed.value.add(person.id)
    // Auto-fill the answer when revealing
    answers.value[idx] = person.name
  }
}

function resetTest() {
  currentIndex.value = 0
  answers.value = new Array(persons.value.length).fill('')
  revealed.value = new Set()
  showScore.value = false
  testResult.value = null
  // Reload to get new random order
  loadPersons()
}

async function submitTest() {
  const answerItems = persons.value.map((p, i) => ({
    id: p.id,
    name: answers.value[i] || '',
  }))

  try {
    const res = await checkAnswers(answerItems)
    testResult.value = res.data
    showScore.value = true

    // Save result to DB
    await saveTestResult(res.data.total, res.data.correct, res.data.score)
  } catch (e) {
    console.error('Submit failed:', e)
  }
}

function handleKeydown(e: KeyboardEvent) {
  // Don't navigate if score modal is open
  if (showScore.value) return
  // Don't navigate if user is typing in an input
  const tag = (e.target as HTMLElement).tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return

  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    prevPerson()
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    goNextOrSubmit()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// Load on mount
loadPersons()
</script>

<style scoped>
.test-view {
  /* container */
}

.loading,
.empty {
  text-align: center;
  padding: 60px 20px;
  color: #999;
  font-size: 16px;
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
  background: #ff4d4f;
  border-radius: 2px;
  transition: width 0.3s;
}

.answer-section {
  margin-top: 16px;
  padding: 16px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.06);
}

.answer-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.answer-input {
  flex: 1;
  padding: 10px 16px;
  border: 2px solid #d9d9d9;
  border-radius: 8px;
  font-size: 16px;
  outline: none;
  transition: border-color 0.2s;
}

.answer-input:focus {
  border-color: #1677ff;
}

.reveal-btn {
  padding: 10px 16px;
  border: 1px solid #faad14;
  background: #fffbe6;
  color: #d48806;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}

.reveal-btn:hover {
  background: #fff1b8;
}

.reveal-answer-text {
  margin-top: 10px;
  font-size: 15px;
  color: #52c41a;
  text-align: center;
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

.submit-row {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
}

.submit-btn {
  padding: 10px 28px;
  border: none;
  background: #1677ff;
  color: #fff;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  transition: background 0.2s;
}

.submit-btn:hover {
  background: #4096ff;
}

.reset-btn {
  padding: 10px 28px;
  border: 1px solid #d9d9d9;
  background: #fff;
  color: #666;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.2s;
}

.reset-btn:hover {
  border-color: #ff4d4f;
  color: #ff4d4f;
}
</style>
