/*
 * ModelPanel.tsx
 * Present the selected model's actual availability and explicit download action.
 */
import type { Configuration, Preset } from '../../domain/transcription';
import { presets } from '../../domain/transcription';

// Download is offered separately from transcription and disabled while any work runs.
export default function ModelPanel({
  config,
  preset,
  busy,
  onDownload,
  onOpen,
}: {
  config: Configuration | null;
  preset: Preset;
  busy: boolean;
  onDownload: () => void;
  onOpen: () => void;
}) {
  const available = config?.models[preset];
  return (
    <section className="model-panel" aria-label="Model availability">
      <div>
        <span className="eyebrow">MODEL · {presets[preset].model}</span>
        <p className={available ? 'available' : ''}>
          {config
            ? available
              ? 'Available locally'
              : 'Missing or incomplete'
            : 'Checking local models…'}
        </p>
        {config && (
          <button className="text-button" title={config.cacheDir} onClick={onOpen}>
            Open model folder
          </button>
        )}
      </div>
      <button disabled={busy || !config || available} onClick={onDownload}>
        {available ? 'Model ready' : 'Download model'}
      </button>
    </section>
  );
}
