/*
 * transcription.test.ts
 * Protect platform-neutral input and export naming boundaries.
 */
import { describe, expect, it } from 'vitest';
import { outputName, supportedInput, presets } from '../src/domain/transcription';
describe('media boundaries', () => {
  it('accepts only supported extensions, case-insensitively', () => {
    expect(supportedInput('/recording.MP4')).toBe(true);
    expect(supportedInput('/recording.mp3')).toBe(true);
    expect(supportedInput('/recording.mp3.exe')).toBe(false);
    expect(supportedInput('/folder.mp3/recording')).toBe(false);
  });
  it('suggests adjacent TXT paths without confusing folder extensions', () => {
    expect(outputName('/folder.name/recording.MP3')).toBe('/folder.name/recording.txt');
    expect(outputName('C:\\folder.name\\recording.mp4')).toBe('C:\\folder.name\\recording.txt');
  });
  it('retains the existing preset mappings shared with the Python worker', () => {
    expect(presets).toEqual({
      High: { model: 'large-v3', mode: 'accurate' },
      Medium: { model: 'small', mode: 'balanced' },
      Low: { model: 'base', mode: 'fast' },
    });
  });
});
