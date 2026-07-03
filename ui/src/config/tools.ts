export interface ToolMenuItem {
  path: string
  title: string
}

export interface ToolAccent {
  gradient: string
  surface: string
  iconColor: string
}

export interface ToolDefinition {
  id: string
  title: string
  description: string
  icon: string
  accent: ToolAccent
  homePath: string
  menuItems: ToolMenuItem[]
}

export const tools: ToolDefinition[] = [
  {
    id: 'gateway',
    title: '大模型网关',
    description: 'OpenAI 兼容代理，请求追踪、上游 Failover、模型能力探测。',
    icon: 'Connection',
    accent: {
      gradient: 'linear-gradient(135deg, #eab308 0%, #ca8a04 100%)',
      surface: 'linear-gradient(160deg, #fffef9 0%, #fef9c3 100%)',
      iconColor: '#c27803',
    },
    homePath: '/gateway/observability',
    menuItems: [
      { path: '/gateway/observability', title: '请求日志' },
      { path: '/gateway/upstream-config', title: '上游配置' },
      { path: '/gateway/model-capability-probe', title: '能力测试' },
    ],
  },
]
