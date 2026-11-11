import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';
const python = fileURLToPath(new URL('../.venv/Scripts/python.exe', import.meta.url));
export default defineConfig({
  testDir: './e2e',
  use: { baseURL: 'http://127.0.0.1:8002', channel: 'msedge', headless: true },
  webServer: {
    command: `"${python}" -m uvicorn app.main:app --app-dir .. --host 127.0.0.1 --port 8002`,
    url: 'http://127.0.0.1:8002',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
