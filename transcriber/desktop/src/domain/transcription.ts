/*
 * transcription.ts
 * Share preset data with the engine and describe the narrow desktop contract.
 */
import presets from '../../../engine/presets.json';
export { presets };
export type Preset = keyof typeof presets;
export type Language = 'it' | 'en';
export interface Configuration {
  cacheDir: string;
  models: Record<Preset, boolean>;
  presets: typeof presets;
}
export interface Operation {
  action: 'download' | 'transcribe';
  preset: Preset;
  language: Language;
  input: string | null;
}
export interface Progress {
  version: 1;
  id: number;
  event: 'progress';
  phase: string;
  percent: number | null;
}
export interface Result {
  text?: string;
  available?: boolean;
}

// Accept media paths case-insensitively while leaving existence checks to Rust.
export function supportedInput(path: string): boolean {
  return /\.(mp3|mp4)$/i.test(path);
}

// Use either platform's path separator when suggesting the adjacent text export.
export function outputName(input: string): string {
  return input.replace(/\.[^./\\]+$/, '.txt');
}

// Keep user-facing phase text truthful during model loading and media processing.
export function progressLabel(progress: Progress): string {
  if (progress.phase === 'downloading') return 'Downloading model…';
  if (progress.phase === 'loading') return 'Loading model and decoding media…';
  return `Transcribing… ${progress.percent ?? 0}%`;
}
