<template>
  <div class="canvas-wrap">
    <img :src="result.image_data_uri" alt="source" />
    <svg
      class="overlay"
      xmlns="http://www.w3.org/2000/svg"
      :viewBox="`0 0 ${result.width} ${result.height}`"
    >
      <template v-if="showPath && orderedPath.length >= 2">
        <polyline
          class="order-path"
          :points="orderedPath.map((it) => `${it.cx},${it.cy}`).join(' ')"
        />
        <polygon
          v-for="(arrow, i) in pathArrows"
          :key="'a' + i"
          class="order-arrow"
          :points="arrow"
        />
      </template>

      <template v-if="showBoxes">
        <g
          v-for="it in items"
          :key="it.id"
          :style="{ opacity: opacity / 100 }"
        >
          <rect
            class="box"
            :class="{ active: activeId === it.id }"
            :x="it.xmin"
            :y="it.ymin"
            :width="Math.max(1, it.xmax - it.xmin)"
            :height="Math.max(1, it.ymax - it.ymin)"
            :stroke="it.color"
            @click.stop="$emit('select', it.id)"
          />
          <g v-if="showOrder && it.reading_order != null" class="order-badge">
            <circle :cx="it.xmin + 14" :cy="it.ymin + 14" r="12" />
            <text :x="it.xmin + 14" :y="it.ymin + 14">{{ it.reading_order }}</text>
          </g>
          <text
            v-if="showLabels"
            class="lbl"
            :x="it.xmin + (it.reading_order != null && showOrder ? 30 : 2)"
            :y="Math.max(14, it.ymin - 4)"
          >
            {{ it.label_zh }} {{ it.score.toFixed(3) }}
          </text>
        </g>
      </template>

      <template v-else-if="showOrder">
        <g
          v-for="it in orderedPath"
          :key="'o' + it.id"
          class="order-badge"
          :style="{ opacity: opacity / 100 }"
        >
          <circle :cx="it.cx" :cy="it.cy" r="12" />
          <text :x="it.cx" :y="it.cy">{{ it.reading_order }}</text>
        </g>
      </template>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface LayoutItem {
  id: number
  label: string
  label_zh: string
  category_id: number
  model_order: number
  reading_order: number | null
  score: number
  xmin: number
  ymin: number
  xmax: number
  ymax: number
  cx: number
  cy: number
  color: string
}

export interface LayoutResult {
  width: number
  height: number
  image_data_uri: string
  items: LayoutItem[]
  legend: { label: string; label_zh: string; color: string }[]
  ordered_count: number
  count: number
}

const props = defineProps<{
  result: LayoutResult
  items: LayoutItem[]
  orderedPath: LayoutItem[]
  activeId: number | null
  showBoxes: boolean
  showLabels: boolean
  showOrder: boolean
  showPath: boolean
  opacity: number
}>()

defineEmits<{
  select: [id: number]
}>()

const pathArrows = computed(() => {
  const ordered = props.orderedPath
  const arrows: string[] = []
  for (let i = 0; i < ordered.length - 1; i++) {
    const a = ordered[i]
    const b = ordered[i + 1]
    const dx = b.cx - a.cx
    const dy = b.cy - a.cy
    const len = Math.hypot(dx, dy) || 1
    const ux = dx / len
    const uy = dy / len
    const ax = a.cx + ux * len * 0.7
    const ay = a.cy + uy * len * 0.7
    const s = 8
    const p1x = ax - ux * s - uy * s * 0.55
    const p1y = ay - uy * s + ux * s * 0.55
    const p2x = ax - ux * s + uy * s * 0.55
    const p2y = ay - uy * s - ux * s * 0.55
    arrows.push(`${ax},${ay} ${p1x},${p1y} ${p2x},${p2y}`)
  }
  return arrows
})
</script>

<style scoped>
.canvas-wrap {
  position: relative;
  display: inline-block;
  line-height: 0;
  box-shadow: var(--sl-shadow-md);
  max-width: 100%;
}

.canvas-wrap img {
  display: block;
  max-width: 100%;
  height: auto;
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

.order-badge {
  pointer-events: none;
}

.order-badge circle {
  fill: #dc2626;
  stroke: #fff;
  stroke-width: 2;
}

.order-badge text {
  fill: #fff;
  font-size: 13px;
  font-weight: 700;
  text-anchor: middle;
  dominant-baseline: central;
}

.order-path {
  fill: none;
  stroke: #dc2626;
  stroke-width: 2.5;
  stroke-dasharray: 8 6;
  opacity: 0.85;
  vector-effect: non-scaling-stroke;
}

.order-arrow {
  fill: #dc2626;
  opacity: 0.9;
}
</style>
