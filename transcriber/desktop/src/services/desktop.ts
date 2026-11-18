/*
 * desktop.ts
 * Own all Tauri IPC, file dialogs, drag/drop and lifecycle subscriptions. Explicit
 * browser scenarios load development fixtures; release builds exclude them.
 */
import { Channel, invoke, isTauri } from '@tauri-apps/api/core';
import { open, save } from '@tauri-apps/plugin-dialog';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { getCurrentWebview } from '@tauri-apps/api/webview';
import { listen } from '@tauri-apps/api/event';
import type { Configuration, Operation, Progress, Result } from '../domain/transcription';
import { outputName } from '../domain/transcription';

const scenario = import.meta.env.DEV ? new URLSearchParams(location.search).get('scenario') : null;
const fixture = scenario
  ? import('./fixtures').then((module) => module.createFixture(scenario))
  : null;
export const simulated = !!fixture;
export const nativeAvailable = !!fixture || isTauri();

// Fail explicitly in an ordinary browser instead of pretending native work succeeded.
function requireNative() {
  if (!nativeAvailable)
    throw new Error('Native desktop services are unavailable. Open the Tauri application.');
}

// Retrieve actual local model status from the integrated engine.
export async function configuration(): Promise<Configuration> {
  if (fixture) return (await fixture).configuration();
  requireNative();
  return invoke('inspect_models');
}

// Return null on picker cancellation; never change selection implicitly.
export async function chooseInput(): Promise<string | null> {
  if (fixture) return (await fixture).chooseInput();
  requireNative();
  return open({
    title: 'Choose MP3 or MP4 file',
    multiple: false,
    filters: [{ name: 'Audio and video', extensions: ['mp3', 'mp4'] }],
  });
}

// Keep progress scoped to one invocation rather than a global event subscription.
export async function perform(
  request: Operation,
  onProgress: (event: Progress) => void,
): Promise<Result> {
  if (fixture) return (await fixture).perform(request, onProgress);
  requireNative();
  const events = new Channel<Progress>();
  events.onmessage = onProgress;
  return invoke('perform', { request, events });
}

// Rust keeps the operation reserved until its worker has actually exited.
export async function cancel(): Promise<void> {
  if (fixture) return (await fixture).cancel();
  return invoke('cancel_operation');
}

// Save only after a native destination selection; cancellation preserves the result.
export async function saveTranscript(input: string, text: string): Promise<boolean> {
  if (fixture) return (await fixture).saveTranscript(text);
  const selected = await save({
    title: 'Save transcription',
    defaultPath: outputName(input),
    filters: [{ name: 'Text', extensions: ['txt'] }],
  });
  if (!selected) return false;
  const path = selected.endsWith('.txt') ? selected : `${selected}.txt`;
  await invoke('save_transcript', { path, text });
  return true;
}

// Folder opening remains a native action, outside the renderer filesystem boundary.
export async function openModelFolder(): Promise<void> {
  if (fixture) return;
  return invoke('open_model_folder');
}

// Drop callbacks receive real native file paths rather than browser File objects.
export async function watchDrop(onDrop: (path: string) => void): Promise<() => void> {
  if (fixture || !isTauri()) return () => {};
  return getCurrentWebview().onDragDropEvent((event) => {
    if (event.payload.type === 'drop' && event.payload.paths[0]) onDrop(event.payload.paths[0]);
  });
}

// Window-close and application-menu exits share the same renderer decision flow.
export async function watchClose(
  onClose: () => void,
  onError: (message: string) => void,
): Promise<() => void> {
  if (fixture || !isTauri()) return () => {};
  const results = await Promise.allSettled([
    getCurrentWindow().onCloseRequested((event) => {
      event.preventDefault();
      onClose();
    }),
    listen('close-requested', onClose),
    listen<string>('shutdown-error', (event) => onError(event.payload)),
  ]);
  const listeners = results
    .filter((result) => result.status === 'fulfilled')
    .map((result) => result.value);
  const failed = results.find((result) => result.status === 'rejected');
  if (failed) {
    listeners.forEach((dispose) => dispose());
    throw failed.reason;
  }
  return () => listeners.forEach((dispose) => dispose());
}

// Close only after native shutdown acknowledges that the worker has been reaped.
export async function close(): Promise<void> {
  if (fixture) return;
  await invoke('shutdown');
  await getCurrentWindow().destroy();
}
