/*
 * transcription.spec.ts
 * Check renderer flows against labelled development fixtures without real files
 * or inference, leaving native IPC and process lifetime to the native smoke test.
 */
import { expect, test } from '@playwright/test';

test('ordinary browser preview cannot start native work', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Interface preview', { exact: false })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start transcription' })).toBeDisabled();
});

test('missing model requires explicit download before transcription and export', async ({
  page,
}) => {
  await page.goto('/?scenario=missing');
  await expect(page.getByText('Missing or incomplete', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Choose MP3/MP4 file' }).click();
  await expect(page.getByRole('button', { name: 'Start transcription' })).toBeDisabled();
  await page.getByRole('button', { name: 'Download model' }).click();
  await expect(page.getByText('Available locally', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Start transcription' }).click();
  await expect(page.getByRole('status')).toHaveText('Transcription complete');
  await page.getByRole('button', { name: 'Save TXT' }).click();
  await expect(page.getByRole('status')).toHaveText('Transcription saved');
  expect(await page.evaluate(() => localStorage.getItem('transcriber-fixture-export'))).toContain(
    'Example local transcription.',
  );
});

test('cancellation releases controls and does not fabricate a result', async ({ page }) => {
  await page.goto('/?scenario=slow');
  await page.getByRole('button', { name: 'Choose MP3/MP4 file' }).click();
  await page.getByRole('button', { name: 'Start transcription' }).click();
  await expect(page.getByRole('button', { name: 'Choose another file' })).toBeDisabled();
  await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect(page.getByRole('status')).toHaveText('Operation cancelled');
  await expect(page.getByRole('button', { name: 'Start transcription' })).toBeEnabled();
  await expect(page.getByRole('button', { name: 'Save TXT' })).toBeDisabled();
});

test('failed export preserves the result and replacement requires a decision', async ({ page }) => {
  await page.goto('/?scenario=save-error');
  await page.getByRole('button', { name: 'Choose MP3/MP4 file' }).click();
  await page.getByRole('button', { name: 'Start transcription' }).click();
  await expect(page.getByRole('button', { name: 'Save TXT' })).toBeEnabled();
  await page.getByRole('button', { name: 'Save TXT' }).click();
  await expect(page.getByRole('alert')).toContainText('Cannot write the destination file.');
  await expect(page.getByRole('button', { name: 'Save TXT' })).toBeEnabled();
  await page.getByRole('button', { name: 'Choose another file' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Cancel', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Save TXT' })).toBeEnabled();
});

test('worker errors are explicit and allow another attempt', async ({ page }) => {
  await page.goto('/?scenario=failure');
  await page.getByRole('button', { name: 'Choose MP3/MP4 file' }).click();
  await page.getByRole('button', { name: 'Start transcription' }).click();
  await expect(page.getByRole('alert')).toContainText('The internal engine exited unexpectedly.');
  await expect(page.getByRole('button', { name: 'Start transcription' })).toBeEnabled();
});
