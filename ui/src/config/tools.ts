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
    description: 'OpenAI 兼容代理，请求追踪、对外模型路由、模型能力探测。',
    icon: 'Connection',
    accent: {
      gradient: 'linear-gradient(135deg, #eab308 0%, #ca8a04 100%)',
      surface: 'linear-gradient(160deg, #fffef9 0%, #fef9c3 100%)',
      iconColor: '#c27803',
    },
    homePath: '/gateway/observability',
    menuItems: [
      { path: '/gateway/model-config', title: '模型配置' },
      { path: '/gateway/observability', title: '请求日志' },
      { path: '/gateway/model-capability-probe', title: '能力测试' },
      { path: '/gateway/token-speed-test', title: 'Token 测试' },
      { path: '/gateway/vram-calculator', title: '显存计算' },
    ],
  },
  {
    id: 'video-tools',
    title: '视频工具',
    description: '视频处理工具集：视频转文字等。',
    icon: 'VideoCamera',
    accent: {
      gradient: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)',
      surface: 'linear-gradient(160deg, #f5f7ff 0%, #eef2ff 100%)',
      iconColor: '#4338ca',
    },
    homePath: '/video-tools/config',
    menuItems: [
      { path: '/video-tools/config', title: '工具配置' },
      { path: '/video-tools/voice-to-text', title: '视频转文字' },
    ],
  },
  {
    id: 'doc-tools',
    title: '文档工具',
    description: '文档处理：Markdown 阅读编辑、转 Word、标题自动编号。',
    icon: 'Document',
    accent: {
      gradient: 'linear-gradient(135deg, #0d9488 0%, #0f766e 100%)',
      surface: 'linear-gradient(160deg, #f0fdfa 0%, #ccfbf1 100%)',
      iconColor: '#0f766e',
    },
    homePath: '/doc-tools/md-to-docx',
    menuItems: [
      { path: '/doc-tools/md-to-docx', title: 'MD 转 DOCX' },
      { path: '/doc-tools/md-heading-numbering', title: 'MD 标题编号' },
      { path: '/doc-tools/md-reader', title: 'MD 编辑器' },
    ],
  },
]
