import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import App from './App.vue'
import ObservabilityView from './views/ObservabilityView.vue'
import UpstreamConfigView from './views/UpstreamConfigView.vue'
import ModelCapabilityProbeView from './views/ModelCapabilityProbeView.vue'
import './styles/global.css'

const routes = [
  { path: '/', name: 'observability', component: ObservabilityView },
  { path: '/upstream-config', name: 'upstreamConfig', component: UpstreamConfigView },
  { path: '/model-capability-probe', name: 'modelCapabilityProbe', component: ModelCapabilityProbeView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.use(ElementPlus, { locale: zhCn })
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}
app.mount('#app')
