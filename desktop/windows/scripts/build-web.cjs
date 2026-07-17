const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const desktopRoot = path.resolve(__dirname, '..');
const projectRoot = path.resolve(desktopRoot, '..', '..');
const clientRoot = path.join(projectRoot, 'client');
const clientDist = path.join(clientRoot, 'dist');
const desktopWeb = path.join(desktopRoot, 'web');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    stdio: 'inherit',
    shell: process.platform === 'win32',
  });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

fs.rmSync(desktopWeb, { recursive: true, force: true });
run(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['run', 'build'], {
  cwd: clientRoot,
  env: {
    ...process.env,
    VITE_BASE_PATH: './',
  },
});
fs.cpSync(clientDist, desktopWeb, { recursive: true });
fs.copyFileSync(path.join(projectRoot, 'LICENSE'), path.join(desktopRoot, 'LICENSE'));
fs.copyFileSync(
  path.join(projectRoot, 'THIRD_PARTY_NOTICES.md'),
  path.join(desktopRoot, 'THIRD_PARTY_NOTICES.md'),
);

const soundsPath = path.join(desktopWeb, 'sounds');
if (!fs.existsSync(soundsPath)) {
  throw new Error(`Desktop web build is missing bundled sounds: ${soundsPath}`);
}

console.log(`Desktop web assets copied to ${desktopWeb}`);
