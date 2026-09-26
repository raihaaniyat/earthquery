import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      // Forward every /api/* request to the FastAPI backend on port 8000.
      // This lets the frontend use relative paths (no baseUrl needed).
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // Health probes
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
});
