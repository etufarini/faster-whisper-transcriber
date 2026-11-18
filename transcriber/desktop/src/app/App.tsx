/*
 * App.tsx
 * Compose the single-file workflow. Options are snapshotted at start; a ref guards
 * immediate duplicate actions before React rerenders. Native Rust enforces it too.
 */
import { useEffect, useRef, useState } from 'react';
import * as desktop from '../services/desktop';
import { progressLabel, supportedInput } from '../domain/transcription';
import type { Configuration, Language, Preset } from '../domain/transcription';
import InputPanel from '../features/transcription/InputPanel';
import ModelPanel from '../features/models/ModelPanel';
import Confirmation from '../components/Confirmation';

interface Decision {
  title: string;
  message: string;
  label: string;
  action: () => void;
}

// Keep all orchestration local to the small application rather than a global store.
export default function App() {
  const [config, setConfig] = useState<Configuration | null>(null);
  const [input, setInput] = useState<string | null>(null);
  const [preset, setPreset] = useState<Preset>('Medium');
  const [language, setLanguage] = useState<Language>('it');
  const [text, setText] = useState('');
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(true);
  const [stopping, setStopping] = useState(false);
  const [percent, setPercent] = useState<number | null>(null);
  const [status, setStatus] = useState('Checking local models…');
  const [error, setError] = useState('');
  const [decision, setDecision] = useState<Decision | null>(null);
  const active = useRef(true);
  const mounted = useRef(true);
  const pending = useRef<Promise<void> | null>(null);
  const closing = useRef(false);
  const selectRef = useRef<(path: string) => void>(() => {});
  const closeRef = useRef<() => void>(() => {});

  // Display actual configuration and release the UI only after engine inspection ends.
  async function refresh() {
    const next = await desktop.configuration();
    if (mounted.current) setConfig(next);
  }

  // Surface failure details while retaining the result and any previously saved file.
  function report(error: unknown) {
    if (mounted.current) setError(String(error instanceof Error ? error.message : error));
  }

  // Initial subscriptions have symmetric cleanup, including React StrictMode remounts.
  useEffect(() => {
    mounted.current = true;
    let disposed = false;
    // Delay inspection one microtask so StrictMode's discarded mount cannot start work.
    void Promise.resolve().then(async () => {
      if (disposed) return;
      try {
        await refresh();
        if (!disposed) setStatus('Ready');
      } catch (failure) {
        if (!disposed) {
          report(failure);
          setStatus('Model check failed');
        }
      } finally {
        if (!disposed) {
          active.current = false;
          setBusy(false);
        }
      }
    });
    const drops = desktop.watchDrop((path) => selectRef.current(path));
    const closes = desktop.watchClose(() => closeRef.current(), report);
    void drops.catch(report);
    void closes.catch(report);
    return () => {
      disposed = true;
      mounted.current = false;
      void drops.then((dispose) => dispose()).catch(() => {});
      void closes.then((dispose) => dispose()).catch(() => {});
    };
  }, []);

  // Selecting a new file preserves an unsaved result unless the user discards it.
  function select(path: string) {
    if (active.current || decision) return;
    if (!supportedInput(path)) {
      setError('Choose an MP3 or MP4 file.');
      return;
    }
    // Apply selection only after the replacement decision has been resolved.
    function apply() {
      setInput(path);
      setText('');
      setSaved(false);
      setError('');
      setStatus('Ready');
      setPercent(null);
    }
    if (text && !saved)
      setDecision({
        title: 'Replace the unsaved transcription?',
        message:
          'Choose Save TXT first to keep the current result, or discard it to choose another file.',
        label: 'Discard result',
        action: apply,
      });
    else apply();
  }
  selectRef.current = select;

  // File dialog cancellation leaves both the current input and result untouched.
  async function choose() {
    try {
      const path = await desktop.chooseInput();
      if (path) select(path);
    } catch (failure) {
      report(failure);
    }
  }

  // Own one promise through engine completion and subsequent cache refresh.
  async function run(action: 'download' | 'transcribe') {
    if (active.current) return;
    active.current = true;
    setBusy(true);
    setStopping(false);
    setError('');
    setPercent(null);
    setStatus(action === 'download' ? 'Downloading model…' : 'Starting transcription…');
    const request = { action, preset, language, input };
    // Keep the current result until a replacement succeeds, including cancellation/errors.
    async function execute() {
      try {
        const result = await desktop.perform(request, (event) => {
          if (mounted.current) {
            setPercent(event.percent);
            setStatus(progressLabel(event));
          }
        });
        if (action === 'transcribe') {
          if (!result.text) throw new Error('The engine returned no transcription.');
          setText(result.text);
          setSaved(false);
          setPercent(100);
          setStatus('Transcription complete');
        } else {
          await refresh();
          setStatus('Model downloaded and ready');
        }
      } catch (failure) {
        const message = String(failure instanceof Error ? failure.message : failure);
        if (message === 'Operation cancelled.') setStatus('Operation cancelled');
        else {
          report(failure);
          setStatus('Operation failed');
        }
      } finally {
        active.current = false;
        if (mounted.current && !closing.current) {
          setBusy(false);
          setStopping(false);
        }
      }
    }
    pending.current = execute();
    await pending.current;
  }

  // Explicit replacement confirmation protects the existing unsaved result.
  function start() {
    if (text && !saved)
      setDecision({
        title: 'Replace the unsaved transcription?',
        message:
          'A successful new transcription will replace this result. Save it first to keep a copy.',
        label: 'Start transcription',
        action: () => void run('transcribe'),
      });
    else void run('transcribe');
  }

  // Stop remains disabled until the original invocation acknowledges cancellation.
  async function stop() {
    setStopping(true);
    setStatus('Stopping…');
    try {
      await desktop.cancel();
    } catch (failure) {
      report(failure);
      setStopping(false);
    }
  }

  // Save errors keep the text available for another destination or a later retry.
  async function save() {
    if (!input || active.current) return;
    active.current = true;
    setBusy(true);
    setError('');
    // Keep export lifetime visible to shutdown, including a pending native save dialog.
    async function exportText() {
      try {
        if (await desktop.saveTranscript(input!, text)) {
          setSaved(true);
          setStatus('Transcription saved');
        }
      } catch (failure) {
        report(failure);
      } finally {
        active.current = false;
        if (!closing.current) setBusy(false);
      }
    }
    pending.current = exportText();
    await pending.current;
  }

  // Native shutdown waits for the active invocation before destroying the window.
  async function finishClose() {
    if (closing.current) return;
    closing.current = true;
    try {
      await desktop.cancel();
      await pending.current;
      await desktop.close();
    } catch (failure) {
      closing.current = false;
      active.current = false;
      setBusy(false);
      report(failure);
    }
  }

  closeRef.current = () => {
    if (active.current || (text && !saved))
      setDecision({
        title: 'Close Faster Whisper Transcriber?',
        message: active.current
          ? 'The active operation will be stopped. Any unsaved transcription will be discarded.'
          : 'The unsaved transcription will be discarded. Choose Save TXT first to keep it.',
        label: 'Close application',
        action: () => void finishClose(),
      });
    else void finishClose();
  };

  // Retry inspection without allowing a simultaneous download or transcription.
  async function retry() {
    if (active.current) return;
    active.current = true;
    setBusy(true);
    setError('');
    try {
      await refresh();
      setStatus('Ready');
    } catch (failure) {
      report(failure);
    } finally {
      active.current = false;
      setBusy(false);
    }
  }

  return (
    <main className="app-shell">
      <header>
        <div className="brand-icon" aria-hidden="true">
          ▥
        </div>
        <div>
          <p className="eyebrow">LOCAL AUDIO TO TEXT</p>
          <h1>Faster Whisper Transcriber</h1>
          <p>Transcribe on your computer. Your recordings stay here.</p>
        </div>
      </header>
      {desktop.simulated && (
        <aside className="notice">
          Development scenario · simulated services and transcription · no inference
        </aside>
      )}
      {!desktop.nativeAvailable && (
        <aside className="notice">
          Interface preview · open the desktop application to transcribe local files.
        </aside>
      )}
      <InputPanel
        input={input}
        preset={preset}
        language={language}
        disabled={busy || !desktop.nativeAvailable}
        onChoose={() => void choose()}
        onPreset={setPreset}
        onLanguage={setLanguage}
      />
      <ModelPanel
        config={config}
        preset={preset}
        busy={busy}
        onDownload={() => void run('download')}
        onCheck={() => void retry()}
        onOpen={() => void desktop.openModelFolder().catch(report)}
      />
      {error && (
        <section className="error" role="alert">
          <strong>Couldn’t complete the action</strong>
          <p>{error}</p>
          {!config && (
            <button disabled={busy} onClick={() => void retry()}>
              Retry model check
            </button>
          )}
          <button className="text-button" onClick={() => setError('')}>
            Dismiss
          </button>
        </section>
      )}
      <div className="actions primary-actions">
        <button
          className="primary"
          disabled={busy || !input || !config?.models[preset]}
          onClick={start}
        >
          Start transcription
        </button>
        <button className="danger" disabled={!busy || stopping} onClick={() => void stop()}>
          {stopping ? 'Stopping…' : 'Stop'}
        </button>
        <button disabled={busy || !text} onClick={() => void save()}>
          Save TXT
        </button>
      </div>
      <section className="progress-area" aria-label="Operation progress" aria-busy={busy}>
        <p role="status">{status}</p>
        <progress
          aria-label="Transcription progress"
          max="100"
          value={percent ?? (busy ? undefined : text ? 100 : 0)}
        />
      </section>
      {text && (
        <p className="result-note">
          {saved
            ? 'Your transcription has been saved.'
            : 'Your transcription is ready. Save TXT to keep a copy.'}
        </p>
      )}
      <footer>Powered by faster-whisper · Model downloads require an internet connection.</footer>
      {decision && (
        <Confirmation
          title={decision.title}
          message={decision.message}
          acceptLabel={decision.label}
          onCancel={() => setDecision(null)}
          onAccept={() => {
            const action = decision.action;
            setDecision(null);
            action();
          }}
        />
      )}
    </main>
  );
}
