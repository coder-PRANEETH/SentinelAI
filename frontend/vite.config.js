import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/report-incident': 'http://127.0.0.1:8000',
      '/incident-chat': 'http://127.0.0.1:8000',
      '/voice-report-audio': 'http://127.0.0.1:8000'
    }
  }
})
