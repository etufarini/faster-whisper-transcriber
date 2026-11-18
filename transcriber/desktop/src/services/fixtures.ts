/*
 * fixtures.ts
 * Clearly labelled development scenarios for browser interaction tests. This
 * module is dynamically imported only in development and never used for inference.
 */
import { presets } from '../domain/transcription';
import type { Configuration, Operation, Progress, Result } from '../domain/transcription';

// Keep fake state per page so browser checks cannot use personal models or data.
export function createFixture(scenario: string) {
  if (!['ready', 'missing', 'failure', 'slow', 'save-error'].includes(scenario))
    throw new Error(`Unknown development scenario: ${scenario}`);
  let available = scenario !== 'missing';
  let cancelled = false;

  // Simulate only the typed desktop contract, with explicit cancellation boundaries.
  async function perform(request: Operation, progress: (value: Progress) => void): Promise<Result> {
    cancelled = false;
    const steps = scenario === 'slow' ? 100 : 4;
    for (let step = 0; step < steps; step++) {
      await new Promise((resolve) => setTimeout(resolve, 30));
      if (cancelled) throw new Error('Operation cancelled.');
      progress({
        version: 1,
        id: 1,
        event: 'progress',
        phase: request.action === 'download' ? 'downloading' : 'transcribing',
        percent: request.action === 'download' ? null : Math.floor((step / steps) * 100),
      });
    }
    if (scenario === 'failure') throw new Error('The internal engine exited unexpectedly.');
    if (request.action === 'download') {
      available = true;
      return { available };
    }
    return { text: 'Example local transcription.\nSecond line.' };
  }

  return {
    // Return data with the same preset source used by the real engine.
    async configuration(): Promise<Configuration> {
      return {
        cacheDir: '/fixture/models/faster-whisper',
        models: { High: available, Medium: available, Low: available },
        presets,
      };
    },
    // A deterministic native-picker stand-in keeps browser flows reproducible.
    async chooseInput(): Promise<string> {
      return '/fixture/example.mp3';
    },
    perform,
    // The running fake promise rejects before another operation can begin.
    async cancel() {
      cancelled = true;
    },
    // Browser storage contains fixture evidence only, never real application data.
    async saveTranscript(text: string): Promise<boolean> {
      if (scenario === 'save-error') throw new Error('Cannot write the destination file.');
      localStorage.setItem('transcriber-fixture-export', text);
      return true;
    },
  };
}
