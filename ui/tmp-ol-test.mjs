import MarkdownIt from 'markdown-it'

function normalizeListIndentation(source) {
  const lines = source.replace(/\t/g, '    ').split(/\r?\n/)
  const result = []
  const indents = []
  const contentCols = []
  const re = /^(\s*)([*+-]|\d+\.)(\s+)(.*)$/

  for (const line of lines) {
    const m = re.exec(line)
    if (!m) {
      if (line.trim()) {
        const ind = /^\s*/.exec(line)?.[0].length ?? 0
        while (indents.length && ind < indents[indents.length - 1]) {
          indents.pop()
          contentCols.pop()
        }
      }
      result.push(line)
      continue
    }

    let indent = m[1].length
    const marker = m[2]
    const spaces = m[3]
    const text = m[4]

    while (indents.length && indent < indents[indents.length - 1]) {
      indents.pop()
      contentCols.pop()
    }

    if (indents.length && indent === indents[indents.length - 1]) {
      indents.pop()
      contentCols.pop()
    }

    if (indents.length) {
      const parentIndent = indents[indents.length - 1]
      const need = contentCols[contentCols.length - 1]
      if (indent > parentIndent && indent < need) {
        indent = need
      }
    }

    result.push(`${' '.repeat(indent)}${marker}${spaces}${text}`)
    indents.push(indent)
    contentCols.push(indent + marker.length + spaces.length)
  }

  return result.join('\n')
}

const md = new MarkdownIt({ html: false })
const src = `1. a
  1. b
    1. c
2. d

1. x
  - y
    - z

10. long
  1. child`
console.log(md.render(normalizeListIndentation(src)))
