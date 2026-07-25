<template>
  <div
    class="canvas-wrap"
    :class="{ 'canvas-wrap--enlarge': enlarge }"
    :style="enlargeStyle"
  >
    <img :src="result.image_data_uri" alt="source" />
    <svg
      class="overlay"
      xmlns="http://www.w3.org/2000/svg"
      :viewBox="`0 0 ${result.width} ${result.height}`"
    >
      <g
        v-for="it in items"
        :key="it.id"
        :style="{ opacity: opacity / 100 }"
      >
        <polygon
          v-if="showBoxes"
          class="box"
          :class="{ active: activeId === it.id }"
          :points="it.points.map((p) => p.join(',')).join(' ')"
          :stroke="it.color"
          @click.stop="$emit('select', it.id)"
        />
        <text
          v-if="showLabels"
          class="lbl"
          :x="it.xmin + 2"
          :y="Math.max(14, it.ymin - 4)"
        >
          {{ labelPreview(it.text) }} {{ it.score.toFixed(2) }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface OcrItem {
  id: number
  text: string
  score: number
  points: number[][]
  xmin: number
  ymin: number
  xmax: number
  ymax: number
  color: string
}

export interface OcrResult {
  width: number
  height: number
  image_data_uri: string
  items: OcrItem[]
  full_text: string
  count: number
}

const props = defineProps<{
  result: OcrResult
  items: OcrItem[]
  activeId: number | null
  showBoxes: boolean
  showLabels: boolean
  opacity: number
  enlarge?: boolean
}>()

defineEmits<{
  select: [id: number]
}>()

const enlargeStyle = computed(() => {
  if (!props.enlarge) return undefined
  const w = Math.max(1, props.result.width)
  const h = Math.max(1, props.result.height)
  return {
    width: `min(calc(92vw - 96px), calc((92vh - 200px) * ${w} / ${h}))`,
    height: `min(calc(92vh - 200px), calc((92vw - 96px) * ${h} / ${w}))`,
  }
})

function labelPreview(text: string) {
  return text.length > 18 ? text.slice(0, 18) + '…' : text
}
</script>

<style scoped>
.canvas-wrap {
  position: relative;
  display: inline-block;
  line-height: 0;
  box-shadow: var(--sl-shadow-md);
  max-width: 100%;
  cursor: zoom-in;
}

.canvas-wrap--enlarge {
  cursor: default;
  max-width: none;
}

.canvas-wrap img {
  display: block;
  max-width: 100%;
  height: auto;
}

.canvas-wrap--enlarge img {
  width: 100%;
  height: 100%;
  max-width: none;
  max-height: none;
  object-fit: fill;
}

.overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.box {
  fill: transparent;
  stroke-width: 2;
  pointer-events: all;
  cursor: pointer;
  vector-effect: non-scaling-stroke;
}

.box.active {
  fill: rgba(37, 99, 235, 0.16);
  stroke-width: 3;
}

.lbl {
  font-size: 12px;
  paint-order: stroke;
  stroke: rgba(0, 0, 0, 0.55);
  stroke-width: 3px;
  fill: #fff;
  pointer-events: none;
}
</style>
