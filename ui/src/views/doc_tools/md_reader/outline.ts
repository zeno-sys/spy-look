export interface OutlineItem {
  level: number
  text: string
  line: number
}

/** Parse ATX headings (# … ######), skipping fenced code blocks. Lines are 1-based. */
export function parseAtxOutline(content: string): OutlineItem[] {
  const lines = content.split(/\r?\n/)
  const items: OutlineItem[] = []
  let inFence = false
  let fenceMarker = ''

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const fenceMatch = /^(```+|~~~+)/.exec(line)
    if (fenceMatch) {
      const marker = fenceMatch[1][0]
      if (!inFence) {
        inFence = true
        fenceMarker = marker
      } else if (marker === fenceMarker) {
        inFence = false
        fenceMarker = ''
      }
      continue
    }
    if (inFence) continue

    const m = /^(#{1,6})\s+(.+?)\s*#*\s*$/.exec(line)
    if (!m) continue
    items.push({
      level: m[1].length,
      text: m[2].trim(),
      line: i + 1,
    })
  }
  return items
}
