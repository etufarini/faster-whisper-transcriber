/*
 * bundle.mjs
 * Prepare the integrated engine before Tauri reads its packaging configuration.
 * Build candidates locally without tagging, uploading or publishing a release.
 */
import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { prepareEngine } from './prepare-engine.mjs';
import { verifyPackage } from './verify-package.mjs';

const desktop = fileURLToPath(new URL('../', import.meta.url));
const engine = prepareEngine();
const config = path.join(desktop, 'packaging/generated/tauri.engine.json');
writeFileSync(
  config,
  JSON.stringify({ bundle: { resources: { [`${engine}/`]: 'engine/' } } }, null, 2) + '\n',
);
const result = spawnSync(
  path.join(desktop, 'node_modules/.bin/tauri'),
  ['build', '--config', config, ...process.argv.slice(2)],
  {
    cwd: desktop,
    stdio: 'inherit',
    env: { ...process.env, CARGO_TARGET_DIR: path.join(desktop, 'packaging/generated/build') },
  },
);
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
if (result.status === 0)
  verifyPackage(
    path.join(
      desktop,
      'packaging/generated/build',
      process.argv.includes('--debug') ? 'debug' : 'release',
      'bundle',
    ),
  );
