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

const routes = [
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
    ],
  },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
})
