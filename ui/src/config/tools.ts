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
    title: '媒体工具',
    description: '媒体处理工具集：视频转文字、音频转文字等。',
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
      { path: '/video-tools/audio-to-text', title: '音频转文字' },
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
  {
    id: 'image-tools',
    title: '图片工具',
    description: '图片处理：本地 OCR、公式识别、版面识别等。',
    icon: 'Picture',
    accent: {
      gradient: 'linear-gradient(135deg, #ea580c 0%, #c2410c 100%)',
      surface: 'linear-gradient(160deg, #fff7ed 0%, #ffedd5 100%)',
      iconColor: '#c2410c',
    },
    homePath: '/image-tools/ocr',
    menuItems: [
      { path: '/image-tools/ocr', title: '图片 OCR' },
      { path: '/image-tools/formula', title: '公式识别' },
      { path: '/image-tools/layout', title: '版面识别' },
    ],
  },
  {
    id: 'agent-resources',
    title: 'Agent 资源',
    description: '持久化管理 Agent Skills 等资源：导入、标签筛选、版本与 zip 导出。',
    icon: 'Collection',
    accent: {
      gradient: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)',
      surface: 'linear-gradient(160deg, #f0f9ff 0%, #e0f2fe 100%)',
      iconColor: '#0369a1',
    },
    homePath: '/agent-resources/skills',
    menuItems: [{ path: '/agent-resources/skills', title: 'Skills 管理' }],
  },
  {
    id: 'bookmarks',
    title: '网页收藏',
    description: '书签管理、稍后阅读、网页剪藏快照，统一收藏与管理。',
    icon: 'CollectionTag',
    accent: {
      gradient: 'linear-gradient(135deg, #0891b2 0%, #0e7490 100%)',
      surface: 'linear-gradient(160deg, #ecfeff 0%, #cffafe 100%)',
      iconColor: '#0e7490',
    },
    homePath: '/bookmarks/manage',
    menuItems: [
      { path: '/bookmarks/manage', title: '书签管理' },
      { path: '/bookmarks/read-later', title: '稍后阅读' },
      { path: '/bookmarks/web-clips', title: '剪藏快照' },
    ],
  },
]
