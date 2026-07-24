import MarkdownIt from 'markdown-it'
import type { Options as MarkdownItOptions } from 'markdown-it'
import type Token from 'markdown-it/lib/token.mjs'
import type Renderer from 'markdown-it/lib/renderer.mjs'
import markdownItKatex from '@traptitech/markdown-it-katex'
import taskLists from 'markdown-it-task-lists'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import json from 'highlight.js/lib/languages/json'
import bash from 'highlight.js/lib/languages/bash'
import sql from 'highlight.js/lib/languages/sql'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import go from 'highlight.js/lib/languages/go'
import rust from 'highlight.js/lib/languages/rust'
import yaml from 'highlight.js/lib/languages/yaml'
import markdown from 'highlight.js/lib/languages/markdown'
import DOMPurify from 'dompurify'
import type { Config as DomPurifyConfig } from 'dompurify'
import type { OutlineItem } from './outline'
import { normalizeListIndentation } from './normalizeLists'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('json', json)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('java', java)
hljs.registerLanguage('go', go)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('md', markdown)

const escapeHtml = MarkdownIt().utils.escapeHtml

function highlightCode(str: string, lang: string): string {
  if (lang && hljs.getLanguage(lang)) {
    try {
      return hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
    } catch {
      /* fall through */
    }
  }
  return escapeHtml(str)
}

function fenceHighlight(str: string, lang: string): string {
  const highlighted = highlightCode(str, lang || '')
  const cls = lang ? ` class="hljs language-${escapeHtml(lang)}"` : ' class="hljs"'
  return `<pre><code${cls}>${highlighted}</code></pre>`
}

const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: false,
  highlight: fenceHighlight,
})

md.use(markdownItKatex, { throwOnError: false, errorColor: '#cc0000' })
md.use(taskLists, { enabled: true, label: true, labelAfter: true })

md.renderer.rules.fence = (tokens, idx) => {
  const token = tokens[idx]
  const info = (token.info || '').trim().split(/\s+/g)[0] || ''
  if (info.toLowerCase() === 'mermaid') {
    return `<div class="mermaid">${escapeHtml(token.content)}</div>\n`
  }
  const highlighted = fenceHighlight(token.content, info)
  const langLabel = info ? escapeHtml(info) : 'text'
  return (
    `<div class="md-code-block">` +
    `<div class="md-code-toolbar">` +
    `<span class="md-code-lang">${langLabel}</span>` +
    `<button type="button" class="md-code-copy">复制</button>` +
    `</div>${highlighted}</div>\n`
  )
}

const defaultHeadingOpen = md.renderer.rules.heading_open
md.renderer.rules.heading_open = (
  tokens: Token[],
  idx: number,
  options: MarkdownItOptions,
  env: { outline?: OutlineItem[]; headingCounter?: number },
  self: Renderer,
): string => {
  const outline = env.outline
  const counter = env.headingCounter ?? 0
  env.headingCounter = counter + 1
  const item = outline?.[counter]
  if (item) {
    tokens[idx].attrSet('id', `md-h-${item.line}`)
    tokens[idx].attrSet('data-line', String(item.line))
  }
  if (defaultHeadingOpen) {
    return defaultHeadingOpen(tokens, idx, options, env, self)
  }
  return self.renderToken(tokens, idx, options)
}

const PURIFY_CONFIG: DomPurifyConfig = {
  USE_PROFILES: { html: true },
  ADD_TAGS: [
    'annotation',
    'math',
    'semantics',
    'mrow',
    'mi',
    'mo',
    'mn',
    'msup',
    'msub',
    'mfrac',
    'msqrt',
    'mtext',
    'mspace',
    'menclose',
    'mtable',
    'mtr',
    'mtd',
    'mover',
    'munder',
    'munderover',
  ],
  ADD_ATTR: [
    'xmlns',
    'encoding',
    'aria-hidden',
    'focusable',
    'class',
    'style',
    'id',
    'data-line',
    'colspan',
    'rowspan',
  ],
}

export function renderMarkdownHtml(content: string, outline: OutlineItem[] = []): string {
  const env = { outline, headingCounter: 0 }
  const raw = md.render(normalizeListIndentation(content || ''), env)
  return DOMPurify.sanitize(raw, PURIFY_CONFIG)
}
