import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/hermes',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30_000,
  outputDir: 'test-results/hermes',
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:1447',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 1447 --strictPort',
    url: 'http://127.0.0.1:1447/tests/hermes/fixture.html',
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
