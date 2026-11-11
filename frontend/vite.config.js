import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, proxy: {
    '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    '/static': { target: 'http://127.0.0.1:8000', changeOrigin: false },
  }},
  test: { include: ['src/**/*.test.{js,jsx}'], environment: 'jsdom', setupFiles: ['./src/test-setup.js'] },
});
