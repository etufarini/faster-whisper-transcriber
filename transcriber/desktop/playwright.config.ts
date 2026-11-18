/*
 * playwright.config.ts
 * Exercise browser interactions in WebKit with retained failure evidence.
 */
import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  outputDir: './test-results/browser',
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI
    ? [['line'], ['json', { outputFile: 'test-results/browser/results.json' }]]
    : 'list',
  use: {
    baseURL: 'http://127.0.0.1:1420',
    viewport: { width: 960, height: 780 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'webkit', use: { browserName: 'webkit' } }],
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:1420',
    reuseExistingServer: !process.env.CI,
  },
});
