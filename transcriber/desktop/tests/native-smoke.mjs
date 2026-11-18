/*
 * native-smoke.mjs
 * Exercise the actual Tauri WebView, native IPC, export and worker cleanup from a
 * copied GUI with temporary application directories and a model-free worker.
 */
import assert from 'node:assert/strict';
import { Buffer } from 'node:buffer';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { copyFile, mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import net from 'node:net';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const desktop = fileURLToPath(new URL('../', import.meta.url));
const mode = process.argv[2] ?? 'workflow';
if (!['workflow', 'real-engine', 'broken-initialization'].includes(mode))
  throw new Error('Unknown native test mode.');
const stage = await mkdtemp(path.join(tmpdir(), 'transcriber-native-'));
const evidence = path.join(desktop, 'test-results/native', mode);
await mkdir(evidence, { recursive: true });

// Reserve an automation port independently of application/model configuration.
async function freePort() {
  const server = net.createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

// Poll observable readiness with a bounded deadline; do not retry test assertions.
async function until(predicate, description) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    if (await predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 80));
  }
  throw new Error(`Timed out waiting for ${description}`);
}

const executable = path.join(stage, 'desktop without source', 'faster-whisper-transcriber');
await mkdir(path.dirname(executable));
await copyFile(path.join(desktop, 'src-tauri/target/debug/faster-whisper-transcriber'), executable);
const record = path.join(stage, 'worker.pid');
const environment = Object.fromEntries(
  Object.entries(process.env).filter(([key]) => !/^(TRANSCRIBER_|HF_|HUGGINGFACE_|XDG_)/.test(key)),
);
Object.assign(environment, {
  HOME: stage,
  XDG_CONFIG_HOME: path.join(stage, 'config'),
  XDG_DATA_HOME: path.join(stage, 'data'),
  TRANSCRIBER_TEST_WORKER: path.join(desktop, 'tests/fixtures/worker.py'),
  TRANSCRIBER_TEST_CACHE: path.join(stage, 'model cache'),
  TRANSCRIBER_FIXTURE_RECORD: record,
  TAURI_WEBDRIVER_PORT: String(await freePort()),
});
if (mode === 'real-engine') delete environment.TRANSCRIBER_TEST_WORKER;
if (mode === 'broken-initialization') environment.TRANSCRIBER_TEST_CACHE = 'invalid relative cache';
let log = '';
const app = spawn(executable, [], {
  cwd: stage,
  env: environment,
  stdio: ['ignore', 'pipe', 'pipe'],
});
app.stdout.on('data', (chunk) => {
  log += chunk;
});
app.stderr.on('data', (chunk) => {
  log += chunk;
});
const driver = `http://127.0.0.1:${environment.TAURI_WEBDRIVER_PORT}`;
let session;

// Keep driver errors explicit; only startup connection refusal is a readiness condition.
async function request(method, endpoint, body, timeout = 10000) {
  const response = await fetch(driver + endpoint, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: globalThis.AbortSignal.timeout(timeout),
  });
  const { value } = await response.json();
  if (!response.ok || value?.error)
    throw new Error(value?.message || `WebDriver ${response.status}`);
  return value;
}

// WebDriver evaluates in the actual native WebKit window, not a browser fixture.
async function evaluate(expression) {
  try {
    return await request('POST', `/session/${session}/execute/sync`, {
      script: `return (${expression})`,
      args: [],
    });
  } catch (error) {
    throw new Error(`Native evaluation failed: ${expression}`, { cause: error });
  }
}

// Exercise existing IPC directly where a system save dialog needs manual OS input.
async function invoke(command, args = {}) {
  return evaluate(
    `window.__TAURI_INTERNALS__.invoke(${JSON.stringify(command)}, ${JSON.stringify(args)})`,
  );
}

// Native drag events supply literal paths through the same listener used for OS drops.
async function drop(input) {
  await invoke('plugin:event|emit', {
    event: 'tauri://drag-drop',
    payload: { paths: [input], position: { x: 0, y: 0 } },
  });
}

// Keep DOM actions tied to visible labels rather than implementation-specific handlers.
async function click(label) {
  assert.equal(
    await evaluate(
      `(() => { const button = [...document.querySelectorAll('button')].find(button => button.textContent === ${JSON.stringify(label)}); if (!button || button.disabled) return false; button.click(); return true; })()`,
    ),
    true,
    `enabled button: ${label}`,
  );
}

// Capture readiness from the live status element rather than sleeping for inference.
async function status(expected) {
  await until(
    () =>
      evaluate(
        `document.querySelector('[role="status"]')?.textContent === ${JSON.stringify(expected)}`,
      ),
    expected,
  );
}

// Reaped children must no longer be visible to the operating system.
function exited(pid) {
  try {
    process.kill(pid, 0);
    return false;
  } catch (error) {
    if (error.code === 'ESRCH') return true;
    throw error;
  }
}

try {
  await until(async () => {
    if (app.exitCode !== null) throw new Error(`Native app exited during startup: ${log}`);
    try {
      return (await request('GET', '/status')).ready;
    } catch (error) {
      if (error.cause?.code === 'ECONNREFUSED') return false;
      throw error;
    }
  }, 'native driver');
  session = (await request('POST', '/session', { capabilities: {} }, 45000)).sessionId;
  if (mode !== 'workflow') {
    await status(mode === 'real-engine' ? 'Ready' : 'Model check failed');
    if (mode === 'real-engine') {
      assert.equal(
        await evaluate('document.querySelector(".model-panel p")?.textContent'),
        'Missing or incomplete',
      );
      await writeFile(
        path.join(evidence, 'desktop.png'),
        Buffer.from(await request('GET', `/session/${session}/screenshot`), 'base64'),
      );
    } else {
      assert.match(
        await evaluate('document.querySelector("[role=alert]")?.textContent'),
        /absolute path/,
      );
    }
    await invoke('plugin:event|emit', { event: 'tauri://close-requested', payload: null });
    await until(() => app.exitCode !== null || app.signalCode !== null, 'application shutdown');
    console.log(`PASS: native ${mode} opens and closes correctly without models.`);
  } else {
    await status('Ready');
    const media = path.join(stage, "recording ' literal.MP3");
    await writeFile(media, 'synthetic media');
    await drop(media);
    await until(
      () =>
        evaluate(
          `document.querySelector('h2')?.textContent === ${JSON.stringify(path.basename(media))}`,
        ),
      'native drop',
    );
    await click('Start transcription');
    await status('Transcription complete');
    const output = path.join(stage, 'result.txt');
    await invoke('save_transcript', { path: output, text: 'Native fixture transcription.' });
    assert.equal(await readFile(output, 'utf8'), 'Native fixture transcription.\n');
    const slow = path.join(stage, 'slow recording.mp4');
    await writeFile(slow, 'synthetic media');
    await drop(slow);
    await until(
      () => evaluate('!!document.querySelector("dialog[open]")'),
      'unsaved replacement decision',
    );
    await click('Discard result');
    await click('Start transcription');
    await status('Transcribing… 12%');
    const firstPid = Number(await readFile(record, 'utf8'));
    const concurrent = await evaluate(
      'window.__TAURI_INTERNALS__.invoke("inspect_models").then(() => "unexpected success", error => String(error))',
    );
    assert.match(concurrent, /already running/);
    await click('Stop');
    await status('Operation cancelled');
    assert.ok(exited(firstPid));
    await click('Start transcription');
    await status('Transcribing… 12%');
    const lastPid = Number(await readFile(record, 'utf8'));
    await invoke('plugin:event|emit', { event: 'tauri://close-requested', payload: null });
    await until(() => evaluate('!!document.querySelector("dialog[open]")'), 'close confirmation');
    await click('Cancel');
    assert.equal(exited(lastPid), false);
    await invoke('plugin:event|emit', { event: 'tauri://close-requested', payload: null });
    await until(() => evaluate('!!document.querySelector("dialog[open]")'), 'confirmed close');
    await writeFile(
      path.join(evidence, 'desktop.png'),
      Buffer.from(await request('GET', `/session/${session}/screenshot`), 'base64'),
    );
    await click('Close application');
    await until(() => app.exitCode !== null || app.signalCode !== null, 'application shutdown');
    assert.ok(exited(lastPid));
    console.log(
      'PASS: actual native window, IPC, literal file drop, atomic export, concurrent rejection, cancellation and confirmed shutdown reap workers.',
    );
  }
} catch (error) {
  if (session) {
    try {
      await writeFile(
        path.join(evidence, 'failure.png'),
        Buffer.from(await request('GET', `/session/${session}/screenshot`), 'base64'),
      );
    } catch {
      /* Driver shutdown may make screenshots unavailable. */
    }
  }
  throw error;
} finally {
  if (app.exitCode === null && app.signalCode === null) {
    app.kill('SIGTERM');
    await until(() => app.exitCode !== null || app.signalCode !== null, 'test cleanup');
  }
  await writeFile(path.join(evidence, 'app.log'), log);
}
