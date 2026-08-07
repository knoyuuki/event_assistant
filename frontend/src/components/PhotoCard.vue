<template>
  <div class="photo-card">
    <div class="photo-wrapper">
      <img :src="photoUrl" :alt="person.name" class="photo-img" @error="onImgError" />
    </div>
    <div class="photo-info" v-if="showInfo">
      <div class="info-name">{{ person.name }}</div>
      <div class="info-meta">
        <span class="info-tag">{{ person.department }}</span>
        <span class="info-tag info-tag--position">{{ person.position }}</span>
        <span v-if="person.position_title" class="info-tag info-tag--title">
          {{ person.position_title }}
          <template v-if="person.position_level != null">(Lv.{{ person.position_level }})</template>
        </span>
      </div>
    </div>
    <div class="photo-info photo-info--hidden" v-if="showHiddenPlaceholder">
      <div class="info-name info-name--hidden">???</div>
      <div class="info-meta">
        <span class="info-tag">{{ person.department }}</span>
        <span class="info-tag info-tag--position">{{ person.position }}</span>
        <span v-if="person.position_title" class="info-tag info-tag--title">
          {{ person.position_title }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getPhotoUrl } from '../api'

interface Person {
  id: number
  name: string
  department: string
  position: string
  filename: string
  position_title?: string | null
  position_level?: number | null
}

const props = defineProps<{
  person: Person
  showInfo?: boolean
  showHiddenPlaceholder?: boolean
}>()

const photoUrl = computed(() => getPhotoUrl(props.person.filename))

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  img.style.display = 'none'
}
</script>

<style scoped>
.photo-card {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.photo-wrapper {
  width: 100%;
  height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fafafa;
  overflow: hidden;
}

.photo-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  display: block;
}

.photo-info {
  padding: 16px 20px;
  text-align: center;
}

.info-name {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 8px;
}

.info-name--hidden {
  color: #bbb;
  font-style: italic;
}

.info-meta {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}

.info-tag {
  display: inline-block;
  padding: 4px 12px;
  background: #e6f4ff;
  color: #1677ff;
  border-radius: 6px;
  font-size: 13px;
}

.info-tag--position {
  background: #fff7e6;
  color: #d48806;
}

.info-tag--title {
  background: #f6ffed;
  color: #389e0d;
}

.photo-info--hidden {
  opacity: 0.7;
}
</style>
