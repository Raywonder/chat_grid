const { spawn } = require('child_process');
const path = require('path');

const bin = process.platform === 'win32' ? 'electron.cmd' : 'electron';
const electronBin = path.join(__dirname, '..', 'node_modules', '.bin', bin);

const child = spawn(electronBin, ['.'], {
  cwd: path.join(__dirname, '..'),
  env: {
    ...process.env,
    CHGRID_DESKTOP_URL: process.env.CHGRID_DESKTOP_URL || 'http://localhost:5173/',
  },
  stdio: 'inherit',
  shell: false,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code || 0);
});
