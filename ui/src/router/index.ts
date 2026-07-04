import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '../layouts/AppLayout.vue'
import HomeView from '../views/HomeView.vue'
import ObservabilityView from '../views/gateway/ObservabilityView.vue'
import UpstreamConfigView from '../views/gateway/UpstreamConfigView.vue'
import ModelCapabilityProbeView from '../views/gateway/ModelCapabilityProbeView.vue'
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
      { path: 'gateway/upstream-config', name: 'gatewayUpstreamConfig', component: UpstreamConfigView },
      { path: 'gateway/model-capability-probe', name: 'gatewayModelProbe', component: ModelCapabilityProbeView },
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
