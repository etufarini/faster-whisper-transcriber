/*
 * setup-engine.mjs
 * Prepare the repository-local Python runtime during npm ci, without models.
 */
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const engine = fileURLToPath(new URL('../../engine/', import.meta.url));
const environment = path.join(engine, '.venv');
const python = path.join(environment, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const requirements = path.join(engine, 'requirements.lock');
const digest = createHash('sha256').update(readFileSync(requirements)).digest('hex');
const receipt = path.join(environment, '.requirements-sha256');

// Execute literal arguments and stop installation if engine preparation fails.
function run(program, args) {
  const result = spawnSync(program, args, { stdio: 'inherit' });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${program} failed (${result.status}).`);
}

// Choose an already-installed supported interpreter; never download a toolchain.
function findPython() {
  const candidates = process.env.TRANSCRIBER_PYTHON
    ? [process.env.TRANSCRIBER_PYTHON]
    : ['python3.12', 'python3.13', 'python3.14', 'python3'];
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ['-c', 'import sys;sys.exit(not ((3,12) <= sys.version_info[:2] < (3,15)))']);
    if (!result.error && result.status === 0) return candidate;
  }
  throw new Error('Install Python 3.12–3.14 with venv support, or set TRANSCRIBER_PYTHON to its executable.');
}

if (!existsSync(python)) run(findPython(), ['-m', 'venv', environment]);
if (!existsSync(receipt) || readFileSync(receipt, 'utf8') !== digest) {
  run(python, ['-m', 'pip', '--disable-pip-version-check', 'install', '--only-binary=:all:', '--require-hashes', '-r', requirements]);
  run(python, ['-c', 'import faster_whisper, numpy, PyInstaller']);
  writeFileSync(receipt, digest);
}
console.log('Internal Python engine ready. No models were downloaded.');
