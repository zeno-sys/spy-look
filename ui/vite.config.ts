import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // Only proxy API prefixes — NOT frontend routes like /gateway/observability
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/gateway/admin': 'http://127.0.0.1:8000',
      '/gateway/logs': 'http://127.0.0.1:8000',
      '/video-tools/admin': 'http://127.0.0.1:8000',
      '/doc-tools/admin': 'http://127.0.0.1:8000',
      '/healthz': 'http://127.0.0.1:8000',
    },
  },
})
