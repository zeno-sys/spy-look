/**
 * Soften CommonMark's strict nesting for ordered lists.
 * Editors often use 2-space nesting for both ul/ol; under `1. ` CM needs ≥3 spaces.
 * Also expands tabs to 4 spaces so nesting is detectable.
 */
export function normalizeListIndentation(source: string): string {
  const lines = source.replace(/\t/g, '    ').split(/\r?\n/)
  const result: string[] = []
  const indents: number[] = []
  const contentCols: number[] = []
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
