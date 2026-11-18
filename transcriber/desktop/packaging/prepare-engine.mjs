/*
 * prepare-engine.mjs
 * Build a self-contained onedir worker and verify it in an isolated directory.
 * Onedir keeps one owned process and avoids extraction at every transcription.
 */
import { spawnSync } from 'node:child_process';
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = fileURLToPath(new URL('../', import.meta.url));
const engine = path.resolve(desktop, '../engine');
const generated = path.join(desktop, 'packaging/generated');
const python = path.join(engine, '.venv/bin/python');
export const preparedEngine = path.join(generated, 'engine-build/dist/transcriber-engine');

// Build only with the repository environment and preserve stdout/stderr on failures.
function run(program, args) {
  const result = spawnSync(program, args, { cwd: desktop, stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${program} failed (${result.status}).`);
}

// The real frozen worker must import its libraries without Python from PATH or models.
export function verifyEngine(directory = preparedEngine) {
  const temporary = mkdtempSync(path.join(tmpdir(), 'transcriber-package-'));
  try {
    const request = {
      version: 1,
      id: 1,
      action: 'inspect',
      cacheDir: path.join(temporary, 'models'),
    };
    const result = spawnSync(path.join(directory, 'transcriber-engine'), [], {
      cwd: temporary,
      input: JSON.stringify(request) + '\n',
      encoding: 'utf8',
      timeout: 60000,
      env: {
        PATH: '/usr/bin:/bin',
        HOME: temporary,
        HF_HOME: path.join(temporary, 'hub'),
        HF_HUB_OFFLINE: '1',
      },
    });
    if (result.error) throw result.error;
    if (result.status !== 0) throw new Error(`Frozen engine failed: ${result.stderr}`);
    const messages = result.stdout
      .trim()
      .split('\n')
      .map((line) => JSON.parse(line));
    const final = messages.at(-1);
    if (
      messages.length !== 1 ||
      final.version !== 1 ||
      final.id !== 1 ||
      final.event !== 'result' ||
      Object.values(final.models).some(Boolean)
    )
      throw new Error(`Invalid frozen-engine inspection: ${result.stdout}`);
    for (const name of [
      'dependency-provenance.json',
      'THIRD-PARTY-NOTICES.txt',
      'requirements.lock',
      'LICENSE',
    ])
      readFileSync(path.join(directory, name));
    console.log(
      'Verified frozen Python engine without model weights, source tree, or Python from PATH.',
    );
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}

// Keep staging/build output separate from Rust target cleanup and never fetch weights.
export function prepareEngine() {
  if (!['linux', 'darwin'].includes(process.platform))
    throw new Error('Packaging currently supports Linux and macOS.');
  mkdirSync(generated, { recursive: true });
  run(python, [
    '-m',
    'PyInstaller',
    '--noconfirm',
    '--clean',
    '--onedir',
    '--name',
    'transcriber-engine',
    '--distpath',
    path.join(generated, 'engine-build/dist'),
    '--workpath',
    path.join(generated, 'engine-build/work'),
    '--specpath',
    path.join(generated, 'engine-build'),
    '--collect-all',
    'faster_whisper',
    '--collect-all',
    'ctranslate2',
    '--collect-all',
    'tokenizers',
    '--collect-all',
    'onnxruntime',
    '--collect-all',
    'av',
    '--recursive-copy-metadata',
    'faster-whisper',
    '--add-data',
    `${path.join(engine, 'presets.json')}${path.delimiter}.`,
    path.join(engine, 'worker.py'),
  ]);
  run(python, [path.join(desktop, 'packaging/provenance.py'), preparedEngine]);
  copyFileSync(
    path.join(engine, 'requirements.lock'),
    path.join(preparedEngine, 'requirements.lock'),
  );
  copyFileSync(path.resolve(desktop, '../../LICENSE'), path.join(preparedEngine, 'LICENSE'));
  verifyEngine();
  return preparedEngine;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url))
  prepareEngine();
