const fs = require('fs');
const path = require('path');
const assert = require('assert');
const { test } = require('node:test');

const source = fs.readFileSync(path.join(__dirname, '..', 'src', 'main.cjs'), 'utf8');

test('opening a hidden window does not force a reload', () => {
  assert.match(source, /showMainWindow\(\{ recover = false \} = \{\}\)/);
  assert.match(source, /Opening the tray\/second-instance entry is a visibility operation/);
  assert.match(source, /mainWindow\.webContents\.focus\(\)/);
});

test('window reveal refocuses the world after restore/show', () => {
  assert.match(source, /mainWindow\.on\('restore', refocusWorldAfterWindowReveal\)/);
  assert.match(source, /mainWindow\.on\('show', refocusWorldAfterWindowReveal\)/);
  assert.match(source, /mainWindow\.webContents\.send\('chat-grid-focus'\)/);
});

test('native shell uses the shared settings bridge and native client marker', () => {
  assert.match(source, /native_client=electron/);
  assert.match(source, /url\.searchParams\.set\('native_client', 'electron'\)/);
  assert.match(source, /window\.chatGridNativeOpenSettings\?\.\(\)/);
  assert.doesNotMatch(source, /settingsButton.*click/);
});
