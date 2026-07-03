<template>
  <div class="home-page">
    <section class="home-hero">
      <div class="home-hero-copy">
        <h1 class="home-hero-title">个人工具箱</h1>
        <p class="home-hero-desc">常用工具集中在一个本地服务里，按需选用，开箱即用。</p>
        <div class="home-hero-stats">
          <div class="home-stat">
            <span class="home-stat-value">{{ tools.length }}</span>
            <span class="home-stat-label">已上线</span>
          </div>
          <div class="home-stat-divider" aria-hidden="true" />
          <div class="home-stat">
            <span class="home-stat-value home-stat-value--muted">+</span>
            <span class="home-stat-label">持续扩展</span>
          </div>
        </div>
      </div>
      <div class="home-hero-visual" aria-hidden="true">
        <img
          class="home-hero-img"
          src="https://picsum.photos/seed/spy-look-devtools/720/480"
          alt=""
          width="720"
          height="480"
          loading="eager"
        />
        <div class="home-hero-visual-overlay" />
      </div>
    </section>

    <section class="home-tools">
      <h2 class="home-section-title">可用工具</h2>
      <div class="home-tool-grid">
        <article
          v-for="tool in tools"
          :key="tool.id"
          class="tool-card"
          :style="{
            '--tool-gradient': tool.accent.gradient,
            '--tool-surface': tool.accent.surface,
            '--tool-icon-color': tool.accent.iconColor,
          }"
          @click="goTo(tool.homePath)"
        >
          <div class="tool-card-accent" />
          <div class="tool-card-icon">
            <el-icon :size="20"><component :is="tool.icon" /></el-icon>
          </div>
          <h3 class="tool-card-title">{{ tool.title }}</h3>
          <p class="tool-card-desc">{{ tool.description }}</p>
          <div class="tool-card-tags" @click.stop>
            <button
              v-for="item in tool.menuItems"
              :key="item.path"
              type="button"
              class="tool-tag"
              @click="goTo(item.path)"
            >
              {{ item.title }}
            </button>
          </div>
          <div class="tool-card-footer">
            <span class="tool-card-action">打开工具</span>
            <el-icon class="tool-card-arrow"><ArrowRight /></el-icon>
          </div>
        </article>

        <article class="tool-card tool-card--placeholder">
          <div class="tool-card-accent tool-card-accent--muted" />
          <div class="tool-card-icon tool-card-icon--muted">
            <el-icon :size="20"><Plus /></el-icon>
          </div>
          <h3 class="tool-card-title">更多工具</h3>
          <p class="tool-card-desc">后续会持续加入新的个人效率工具。</p>
          <div class="tool-card-footer">
            <span class="tool-card-action tool-card-action--muted">敬请期待</span>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowRight, Plus } from '@element-plus/icons-vue'
import { tools } from '../config/tools'

const router = useRouter()

function goTo(path: string) {
  router.push(path)
}
</script>

<style scoped>
.home-page {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px 24px 48px;
}

/* ── Hero: asymmetric split ── */

.home-hero {
  display: grid;
  grid-template-columns: 1fr 1.1fr;
  gap: 32px;
  align-items: center;
  min-height: min(420px, calc(100dvh - 120px));
  padding-bottom: 40px;
  border-bottom: 1px solid var(--sl-border);
  margin-bottom: 36px;
}

.home-hero-copy {
  padding-right: 16px;
}

.home-hero-title {
  font-size: clamp(2rem, 4vw, 2.75rem);
  font-weight: 700;
  letter-spacing: -0.03em;
  line-height: 1.1;
  color: var(--sl-text);
  margin-bottom: 14px;
}

.home-hero-desc {
  font-size: 15px;
  line-height: 1.65;
  color: var(--sl-text-secondary);
  max-width: 36ch;
  margin-bottom: 28px;
}

.home-hero-stats {
  display: flex;
  align-items: center;
  gap: 20px;
}

.home-stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.home-stat-value {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--sl-accent);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.home-stat-value--muted {
  color: var(--sl-text-faint);
}

.home-stat-label {
  font-size: 12px;
  color: var(--sl-text-muted);
}

.home-stat-divider {
  width: 1px;
  height: 32px;
  background: var(--sl-border-strong);
}

.home-hero-visual {
  position: relative;
  border-radius: var(--sl-radius-lg);
  overflow: hidden;
  aspect-ratio: 3 / 2;
  box-shadow: var(--sl-shadow-lg);
}

.home-hero-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.home-hero-visual-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    rgba(234, 179, 8, 0.16) 0%,
    transparent 55%
  );
  pointer-events: none;
}

/* ── Tool grid (5 per row on desktop) ── */

.home-section-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--sl-text);
  margin-bottom: 14px;
}

.home-tool-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.tool-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 168px;
  padding: 14px 14px 12px;
  border-radius: var(--sl-radius-md);
  border: 1px solid var(--sl-border);
  background: var(--tool-surface, var(--sl-bg-elevated));
  box-shadow: var(--sl-shadow-sm);
  cursor: pointer;
  overflow: hidden;
  transition:
    transform 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    border-color 0.25s ease;
}

.tool-card:hover {
  transform: translateY(-2px);
  border-color: var(--sl-accent-border);
  box-shadow: var(--sl-shadow-md);
}

.tool-card:active {
  transform: scale(0.99);
}

.tool-card-accent {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--tool-gradient, var(--sl-accent));
}

.tool-card-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  margin-bottom: 10px;
  border-radius: var(--sl-radius-sm);
  background: var(--sl-bg-elevated);
  color: var(--tool-icon-color, var(--sl-accent));
  box-shadow: var(--sl-shadow-sm), inset 0 0 0 1px var(--sl-border);
}

.tool-card-title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--sl-text);
  margin: 0 0 4px;
  line-height: 1.3;
}

.tool-card-desc {
  flex: 1;
  margin: 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--sl-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tool-card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 10px;
}

.tool-tag {
  padding: 2px 8px;
  border: none;
  border-radius: 999px;
  background: var(--sl-accent-subtle);
  color: var(--sl-accent);
  font-size: 11px;
  line-height: 1.5;
  cursor: pointer;
  box-shadow: inset 0 0 0 1px var(--sl-accent-border);
  transition: background 0.15s ease, color 0.15s ease;
}

.tool-tag:hover {
  background: var(--sl-accent);
  color: #fff;
}

.tool-tag:active {
  transform: scale(0.97);
}

.tool-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 10px;
}

.tool-card-action {
  font-size: 12px;
  font-weight: 500;
  color: var(--sl-accent);
}

.tool-card-arrow {
  color: var(--sl-accent);
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}

.tool-card:hover .tool-card-arrow {
  transform: translateX(4px);
}

.tool-card--placeholder {
  cursor: default;
  border-style: dashed;
  border-color: var(--sl-border-strong);
  background: var(--sl-bg);
  box-shadow: none;
}

.tool-card--placeholder:hover {
  transform: none;
  border-color: var(--sl-text-faint);
  box-shadow: none;
}

.tool-card-accent--muted {
  background: linear-gradient(90deg, var(--sl-border-strong), var(--sl-border));
}

.tool-card-icon--muted {
  color: var(--sl-text-muted);
}

.tool-card-action--muted {
  color: var(--sl-text-muted);
}

@media (max-width: 1400px) {
  .home-tool-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}

@media (max-width: 1100px) {
  .home-tool-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 900px) {
  .home-hero {
    grid-template-columns: 1fr;
    min-height: auto;
    gap: 24px;
  }

  .home-hero-visual {
    order: -1;
    max-height: 220px;
    aspect-ratio: 16 / 9;
  }
}

@media (max-width: 768px) {
  .home-page {
    padding: 16px 16px 32px;
  }

  .home-tool-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 480px) {
  .home-tool-grid { grid-template-columns: 1fr; }
}
</style>
