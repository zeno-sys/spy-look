import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 5173 falls in Windows excluded range 5109-5208 (Hyper-V/NAT) → EACCES
    host: '0.0.0.0',
    port: 5300,
    strictPort: true,
    allowedHosts: [
      '.vicp.fun',             // 以后换花生壳域名也自动过
    ],
    // Only proxy API prefixes — NOT frontend routes like /gateway/observability
    // changeOrigin helps when traffic comes through peanut-shell Host headers
    proxy: {
      '/v1': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/gateway/admin': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/gateway/logs': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/video-tools/admin': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/doc-tools/admin': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/healthz': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
