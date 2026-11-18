/*
 * verify-package.mjs
 * Inspect actual native package resources and execute the installed-layout worker
 * with isolated user directories, no model files and a minimal system PATH.
 */
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { verifyEngine } from './prepare-engine.mjs';

// Find one packaged resource without depending on the product's display-name casing.
function find(directory, name) {
  const matches = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const child = path.join(directory, entry.name);
    if (entry.name === name) matches.push(child);
    else if (entry.isDirectory()) matches.push(...find(child, name));
  }
  return matches;
}

// A complete candidate must have both the embedded frontend and its frozen engine.
export function verifyPackage(bundle) {
  const temporary = mkdtempSync(path.join(tmpdir(), 'transcriber-install-'));
  try {
    let root;
    if (process.platform === 'linux') {
      const packages = find(bundle, 'deb').flatMap((directory) =>
        readdirSync(directory)
          .filter((name) => name.endsWith('.deb'))
          .map((name) => path.join(directory, name)),
      );
      if (packages.length !== 1)
        throw new Error(
          'Expected exactly one Debian candidate; remove obsolete candidates before packaging.',
        );
      const extraction = spawnSync('dpkg-deb', ['--extract', packages[0], temporary], {
        stdio: 'inherit',
      });
      if (extraction.error) throw extraction.error;
      if (extraction.status !== 0) throw new Error('Could not extract the Debian package.');
      root = temporary;
    } else {
      const apps = find(bundle, 'Faster Whisper Transcriber.app');
      if (apps.length !== 1) throw new Error('Expected exactly one macOS application candidate.');
      root = apps[0];
    }
    const engines = find(root, 'transcriber-engine');
    if (engines.length !== 1)
      throw new Error('The package does not contain exactly one integrated engine.');
    verifyEngine(path.dirname(engines[0]));
    const applications = find(root, 'faster-whisper-transcriber');
    if (applications.length !== 1)
      throw new Error('The native application executable is missing or duplicated.');
    const check = spawnSync(applications[0], ['--check-package'], {
      cwd: temporary,
      env: { PATH: '/usr/bin:/bin', HOME: temporary },
      encoding: 'utf8',
      timeout: 30000,
    });
    if (check.error) throw check.error;
    if (check.status !== 0)
      throw new Error(`Packaged GUI failed its asset/loader check: ${check.stderr}`);
    console.log(check.stdout.trim());
    console.log('Verified native package with its actual installed resource layout.');
  } finally {
    rmSync(temporary, { recursive: true, force: true });
  }
}
