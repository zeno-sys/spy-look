import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'
import HomeView from '../views/HomeView.vue'
import ObservabilityView from '../views/gateway/ObservabilityView.vue'
import ModelConfigView from '../views/gateway/ModelConfigView.vue'
import ModelCapabilityProbeView from '../views/gateway/ModelCapabilityProbeView.vue'
import TokenSpeedTestView from '../views/gateway/TokenSpeedTestView.vue'
import VramCalculatorView from '../views/gateway/VramCalculatorView.vue'
import VideoToolsConfigView from '../views/video_tools/VideoToolsConfigView.vue'
import VoiceToTextView from '../views/video_tools/VoiceToTextView.vue'
import MdToDocxView from '../views/doc_tools/MdToDocxView.vue'
import MdHeadingNumberingView from '../views/doc_tools/MdHeadingNumberingView.vue'
import MdReaderView from '../views/doc_tools/MdReaderView.vue'
import ImageOcrView from '../views/image_tools/ImageOcrView.vue'
import ImageFormulaView from '../views/image_tools/ImageFormulaView.vue'
import ImageLayoutView from '../views/image_tools/ImageLayoutView.vue'
import SettingsView from '../views/settings/SettingsView.vue'
import SkillsManageView from '../views/agent_resources/SkillsManageView.vue'
import LoginView from '../views/auth/LoginView.vue'
import SetupView from '../views/auth/SetupView.vue'
import LocalResetView from '../views/auth/LocalResetView.vue'
import UsersManageView from '../views/auth/UsersManageView.vue'
import { useAuth } from '../composables/useAuth'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { public: true, authPage: true },
  },
  {
    path: '/setup',
    name: 'setup',
    component: SetupView,
    meta: { public: true, authPage: true },
  },
  {
    path: '/local-reset',
    name: 'localReset',
    component: LocalResetView,
    meta: { public: true, authPage: true },
  },
  {
    path: '/',
    component: AppLayout,
    children: [
      { path: '', name: 'home', component: HomeView },
      { path: 'gateway', redirect: '/gateway/observability' },
      { path: 'gateway/observability', name: 'gatewayObservability', component: ObservabilityView },
      { path: 'gateway/model-config', name: 'gatewayModelConfig', component: ModelConfigView },
      { path: 'gateway/upstream-config', redirect: '/gateway/model-config' },
      { path: 'gateway/model-capability-probe', name: 'gatewayModelProbe', component: ModelCapabilityProbeView },
      { path: 'gateway/token-speed-test', name: 'gatewayTokenSpeedTest', component: TokenSpeedTestView },
      { path: 'gateway/vram-calculator', name: 'gatewayVramCalculator', component: VramCalculatorView },
      { path: 'video-tools', redirect: '/video-tools/config' },
      { path: 'video-tools/config', name: 'videoToolsConfig', component: VideoToolsConfigView },
      { path: 'video-tools/voice-to-text', name: 'videoToolsVoiceToText', component: VoiceToTextView },
      { path: 'doc-tools', redirect: '/doc-tools/md-to-docx' },
      { path: 'doc-tools/md-to-docx', name: 'docToolsMdToDocx', component: MdToDocxView },
      {
        path: 'doc-tools/md-heading-numbering',
        name: 'docToolsMdHeadingNumbering',
        component: MdHeadingNumberingView,
      },
      { path: 'doc-tools/md-reader', name: 'docToolsMdReader', component: MdReaderView },
      { path: 'image-tools', redirect: '/image-tools/ocr' },
      { path: 'image-tools/ocr', name: 'imageToolsOcr', component: ImageOcrView },
      { path: 'image-tools/formula', name: 'imageToolsFormula', component: ImageFormulaView },
      { path: 'image-tools/layout', name: 'imageToolsLayout', component: ImageLayoutView },
      { path: 'settings', name: 'settings', component: SettingsView },
      {
        path: 'settings/users',
        name: 'settingsUsers',
        component: UsersManageView,
        meta: { ownerOnly: true },
      },
      { path: 'agent-resources', redirect: '/agent-resources/skills' },
      {
        path: 'agent-resources/skills',
        name: 'agentResourcesSkills',
        component: SkillsManageView,
      },
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const { refreshStatus, initialized, isLoggedIn, isOwner } = useAuth()

  try {
    await refreshStatus()
  } catch {
    // 后端未就绪时仍放行公开页，避免死循环
    if (to.meta.public) return true
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (!initialized.value) {
    if (to.name === 'setup' || to.name === 'localReset') return true
    return { name: 'setup' }
  }

  if (to.name === 'setup') {
    return isLoggedIn.value ? { name: 'home' } : { name: 'login' }
  }

  if (to.name === 'localReset') {
    return true
  }

  if (!isLoggedIn.value) {
    if (to.name === 'login') return true
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.name === 'login') {
    return { name: 'home' }
  }

  if (to.meta.ownerOnly && !isOwner.value) {
    return { name: 'home' }
  }

  return true
})
