import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/v1': 'http://127.0.0.1:8000',
      '/logs': 'http://127.0.0.1:8000',
      '/admin': 'http://127.0.0.1:8000',
      '/healthz': 'http://127.0.0.1:8000',
    }
  }
})
