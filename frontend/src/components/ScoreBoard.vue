<template>
  <div class="score-board" v-if="show">
    <div class="score-overlay" @click="$emit('close')"></div>
    <div class="score-panel">
      <h3 class="score-title">测试结果</h3>
      <div class="score-circle" :class="scoreClass">
        <span class="score-number">{{ result.score }}</span>
        <span class="score-unit">分</span>
      </div>
      <div class="score-stats">
        <span>共 {{ result.total }} 人</span>
        <span class="stat-divider">|</span>
        <span>正确 {{ result.correct }} 人</span>
      </div>
      <div class="score-details" v-if="result.details && result.details.length">
        <div
          v-for="d in result.details"
          :key="d.id"
          :class="['detail-row', { 'detail-row--wrong': !d.is_correct }]"
        >
          <span class="detail-icon">{{ d.is_correct ? '✓' : '✗' }}</span>
          <span class="detail-answer">{{ d.user_answer || '（未填写）' }}</span>
          <span v-if="!d.is_correct" class="detail-correct">
            → {{ d.correct_name }}
          </span>
        </div>
      </div>
      <button class="score-close-btn" @click="$emit('close')">关闭</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CheckResult } from '../api'

const props = defineProps<{
  result: CheckResult | null
  show: boolean
}>()

defineEmits<{
  close: []
}>()

const scoreClass = computed(() => {
  if (!props.result) return ''
  if (props.result.score === 100) return 'score-circle--perfect'
  if (props.result.score >= 60) return 'score-circle--good'
  return 'score-circle--bad'
})
</script>

<style scoped>
.score-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 100;
}

.score-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #fff;
  border-radius: 16px;
  padding: 32px;
  z-index: 101;
  width: 400px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  text-align: center;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.15);
}

.score-title {
  font-size: 20px;
  margin-bottom: 20px;
  color: #1a1a2e;
}

.score-circle {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
  border: 4px solid #d9d9d9;
}

.score-circle--perfect {
  border-color: #52c41a;
  background: #f6ffed;
}

.score-circle--good {
  border-color: #1677ff;
  background: #e6f4ff;
}

.score-circle--bad {
  border-color: #ff4d4f;
  background: #fff2f0;
}

.score-number {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
}

.score-circle--perfect .score-number { color: #52c41a; }
.score-circle--good .score-number { color: #1677ff; }
.score-circle--bad .score-number { color: #ff4d4f; }

.score-unit {
  font-size: 14px;
  color: #999;
}

.score-stats {
  font-size: 15px;
  color: #666;
  margin-bottom: 16px;
}

.stat-divider {
  margin: 0 8px;
  color: #d9d9d9;
}

.score-details {
  text-align: left;
  border-top: 1px solid #f0f0f0;
  padding-top: 12px;
  margin-bottom: 16px;
}

.detail-row {
  padding: 6px 0;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-row--wrong {
  color: #ff4d4f;
}

.detail-icon {
  font-weight: 700;
  width: 20px;
}

.detail-answer {
  flex: 1;
}

.detail-correct {
  color: #52c41a;
  font-weight: 500;
}

.score-close-btn {
  padding: 8px 32px;
  border: none;
  background: #1677ff;
  color: #fff;
  border-radius: 8px;
  font-size: 15px;
  cursor: pointer;
  transition: background 0.2s;
}

.score-close-btn:hover {
  background: #4096ff;
}
</style>
