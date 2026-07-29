import { onMounted, onUnmounted, type Ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadRawFile, UploadUserFile } from 'element-plus'

const ACCEPTED_EXT = new Set(['png', 'jpg', 'jpeg', 'webp', 'bmp'])
const ACCEPTED_MIME = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
  'image/bmp',
  'image/x-ms-bmp',
])
const MAX_BYTES = 10 * 1024 * 1024

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  const tag = target.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (target.isContentEditable) return true
  return Boolean(target.closest('input, textarea, select, [contenteditable="true"]'))
}

function extFromMime(mime: string): string {
  if (mime === 'image/jpeg' || mime === 'image/jpg') return 'jpg'
  if (mime === 'image/png') return 'png'
  if (mime === 'image/webp') return 'webp'
  if (mime === 'image/bmp' || mime === 'image/x-ms-bmp') return 'bmp'
  return 'png'
}

function isAcceptedImage(file: File): boolean {
  if (file.type) return ACCEPTED_MIME.has(file.type.toLowerCase())
  const name = file.name || ''
  const dot = name.lastIndexOf('.')
  if (dot < 0) return false
  return ACCEPTED_EXT.has(name.slice(dot + 1).toLowerCase())
}

function normalizePasteFile(file: File): File {
  if (file.name && file.name.includes('.')) return file
  const ext = extFromMime(file.type || 'image/png')
  return new File([file], `paste.${ext}`, {
    type: file.type || `image/${ext === 'jpg' ? 'jpeg' : ext}`,
    lastModified: Date.now(),
  })
}

function extractClipboardImage(event: ClipboardEvent): File | null {
  const items = event.clipboardData?.items
  if (!items) return null
  for (const item of items) {
    if (!item.type.startsWith('image/')) continue
    const file = item.getAsFile()
    if (file) return normalizePasteFile(file)
  }
  const files = event.clipboardData?.files
  if (files) {
    for (const file of files) {
      if (file.type.startsWith('image/')) return normalizePasteFile(file)
    }
  }
  return null
}

export function applyImageFile(
  file: File,
  selectedFile: Ref<File | null>,
  fileList: Ref<UploadUserFile[]>,
): boolean {
  if (!isAcceptedImage(file)) {
    ElMessage.warning('仅支持 png / jpg / webp / bmp')
    return false
  }
  if (file.size > MAX_BYTES) {
    ElMessage.warning('图片不能超过 10 MB')
    return false
  }
  selectedFile.value = file
  fileList.value = [
    {
      name: file.name,
      uid: Date.now(),
      status: 'ready',
      raw: file as UploadRawFile,
    },
  ]
  return true
}

/** Page-level Ctrl+V / paste image → selectedFile + el-upload fileList */
export function useImagePasteUpload(
  selectedFile: Ref<File | null>,
  fileList: Ref<UploadUserFile[]>,
  options?: { disabled?: Ref<boolean> },
) {
  function onPaste(event: ClipboardEvent) {
    if (options?.disabled?.value) return
    if (isEditableTarget(event.target)) return
    const file = extractClipboardImage(event)
    if (!file) return
    event.preventDefault()
    if (applyImageFile(file, selectedFile, fileList)) {
      ElMessage.success(`已粘贴：${file.name}`)
    }
  }

  onMounted(() => {
    window.addEventListener('paste', onPaste)
  })
  onUnmounted(() => {
    window.removeEventListener('paste', onPaste)
  })
}
