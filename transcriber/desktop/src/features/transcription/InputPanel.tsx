/*
 * InputPanel.tsx
 * Keep file selection and the existing preset/language controls together.
 */
import type { Language, Preset } from '../../domain/transcription';
import { presets } from '../../domain/transcription';

// Native drag/drop is handled by the desktop service; this panel remains renderer-only.
export default function InputPanel({
  input,
  preset,
  language,
  disabled,
  onChoose,
  onPreset,
  onLanguage,
}: {
  input: string | null;
  preset: Preset;
  language: Language;
  disabled: boolean;
  onChoose: () => void;
  onPreset: (value: Preset) => void;
  onLanguage: (value: Language) => void;
}) {
  return (
    <section aria-label="Transcription options">
      <div className="drop-area">
        <span className="file-symbol" aria-hidden="true">
          ↧
        </span>
        <h2>{input ? input.split(/[\\/]/).at(-1) : 'Choose a recording'}</h2>
        <p>
          {input
            ? 'Ready to transcribe on this computer.'
            : 'Drop an MP3 or MP4 here, or choose a file.'}
        </p>
        {input && (
          <p className="file-path" title={input}>
            {input}
          </p>
        )}
        <button disabled={disabled} onClick={onChoose}>
          {input ? 'Choose another file' : 'Choose MP3/MP4 file'}
        </button>
      </div>
      <div className="options">
        <label>
          Reliability
          <select
            value={preset}
            disabled={disabled}
            onChange={(event) => onPreset(event.target.value as Preset)}
          >
            {Object.keys(presets).map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <label>
          Language
          <select
            value={language}
            disabled={disabled}
            onChange={(event) => onLanguage(event.target.value as Language)}
          >
            <option value="it">Italian</option>
            <option value="en">English</option>
          </select>
        </label>
      </div>
    </section>
  );
}
