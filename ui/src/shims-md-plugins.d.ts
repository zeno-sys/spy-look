declare module '@traptitech/markdown-it-katex' {
  import type MarkdownIt from 'markdown-it'
  const markdownItKatex: MarkdownIt.PluginWithOptions<{
    throwOnError?: boolean
    errorColor?: string
  }>
  export default markdownItKatex
}

declare module 'markdown-it-task-lists' {
  import type MarkdownIt from 'markdown-it'
  const taskLists: MarkdownIt.PluginWithOptions<{
    enabled?: boolean
    label?: boolean
    labelAfter?: boolean
  }>
  export default taskLists
}
