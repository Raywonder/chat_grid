const { app, BrowserWindow, Menu, Tray, desktopCapturer, dialog, nativeImage, shell, session } = require('electron');
const fs = require('fs');
const path = require('path');

const DEFAULT_ENDIGINOUS_URL = 'https://blind.software/chatgrid/?desktop=1';
const ALLOWED_PROTOCOLS = new Set(['http:', 'https:']);

let mainWindow = null;
let tray = null;
let isQuitting = false;
let mainWindowUnresponsive = false;

const hasSingleInstanceLock = app.requestSingleInstanceLock();
if (!hasSingleInstanceLock) {
  app.quit();
}

app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

function settingsPath() {
  return path.join(app.getPath('userData'), 'settings.json');
}

function normalizeEndiginousUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return DEFAULT_ENDIGINOUS_URL;
  const url = new URL(raw);
  if (!ALLOWED_PROTOCOLS.has(url.protocol)) {
    throw new Error('Endiginous URL must start with http:// or https://.');
  }
  return url.toString();
}

function readSettings() {
  const fromEnv = process.env.CHGRID_DESKTOP_URL;
  if (fromEnv) {
    return { endiginousUrl: normalizeEndiginousUrl(fromEnv) };
  }
  try {
    const raw = fs.readFileSync(settingsPath(), 'utf8');
    const parsed = JSON.parse(raw);
    return { endiginousUrl: normalizeEndiginousUrl(parsed.endiginousUrl ?? parsed.chatGridUrl) };
  } catch {
    return { endiginousUrl: DEFAULT_ENDIGINOUS_URL };
  }
}

function writeSettings(nextSettings) {
  fs.mkdirSync(app.getPath('userData'), { recursive: true });
  fs.writeFileSync(settingsPath(), JSON.stringify(nextSettings, null, 2) + '\n');
}

function appendRuntimeLog(event, details = {}) {
  const entry = {
    at: new Date().toISOString(),
    event,
    ...details,
  };
  fs.appendFile(path.join(app.getPath('userData'), 'runtime-events.jsonl'), `${JSON.stringify(entry)}\n`, () => undefined);
}

function getCurrentUrl() {
  return readSettings().endiginousUrl;
}

function loadEndiginous(url = getCurrentUrl()) {
  if (!mainWindow) return;
  mainWindow.loadURL(url).catch((error) => {
    appendRuntimeLog('load-url-failed', { message: error?.message || String(error) });
  });
}

function recoverEndiginousView() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    if (app.isReady()) createWindow();
    return;
  }
  appendRuntimeLog('recover-view-requested', {
    crashed: mainWindow.webContents.isCrashed(),
    unresponsive: mainWindowUnresponsive,
  });
  mainWindowUnresponsive = false;
  mainWindow.show();
  mainWindow.focus();
  if (mainWindow.webContents.isCrashed()) {
    loadEndiginous();
    return;
  }
  mainWindow.webContents.reloadIgnoringCache();
}

function showMainWindow({ recover = false } = {}) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    if (app.isReady()) createWindow();
    return;
  }
  // Opening the tray/second-instance entry is a visibility operation, not a
  // request to reload the world.  Reloading here made a hidden window look as
  // though navigation had failed, and could surface renderer recovery UI
  // before the window was visible.
  if (recover && (mainWindowUnresponsive || mainWindow.webContents.isCrashed())) {
    recoverEndiginousView();
    return;
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
  mainWindow.webContents.focus();
  setTimeout(() => {
    if (!mainWindow || mainWindow.isDestroyed() || !mainWindow.isVisible()) return;
    mainWindow.webContents.send('chat-grid-focus');
  }, 80);
}

function createTrayIcon() {
  const svg = encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">' +
      '<rect width="32" height="32" rx="7" fill="#2563eb"/>' +
      '<path d="M7 7h18v18H7zM13 7v18M19 7v18M7 13h18M7 19h18" fill="none" stroke="white" stroke-width="2"/>' +
    '</svg>',
  );
  return nativeImage.createFromDataURL(`data:image/svg+xml;charset=UTF-8,${svg}`).resize({ width: 16, height: 16 });
}

function createTray() {
  if (tray) return;
  tray = new Tray(createTrayIcon());
  tray.setToolTip('Endiginous');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Open Endiginous', click: () => showMainWindow() },
    { label: 'Reload Endiginous', click: () => loadEndiginous() },
    { label: 'Recover frozen view', click: recoverEndiginousView },
    { type: 'separator' },
    {
      label: 'Quit Endiginous',
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]));
  tray.on('click', () => showMainWindow());
  tray.on('double-click', () => showMainWindow());
}

async function promptForEndiginousUrl() {
  if (!mainWindow) return;
  const current = getCurrentUrl();
  const result = await dialog.showMessageBox(mainWindow, {
    type: 'question',
    title: 'Endiginous URL',
    message: 'Choose which Endiginous to open.',
    detail: `Current URL:\n${current}`,
    buttons: ['Use live Endiginous', 'Use local development', 'Cancel'],
    defaultId: 0,
    cancelId: 2,
    noLink: true,
  });
  if (result.response === 2) return;
  const endiginousUrl = result.response === 1 ? 'http://localhost:5173/' : DEFAULT_ENDIGINOUS_URL;
  writeSettings({ endiginousUrl });
  loadEndiginous(endiginousUrl);
}

function createApplicationMenu() {
  const template = [
    {
      label: 'Endiginous',
      submenu: [
        { label: 'Reload', click: () => mainWindow?.reload() },
        { label: 'Recover Frozen View', accelerator: 'Ctrl+Shift+R', click: recoverEndiginousView },
        { label: 'Focus Grid', accelerator: 'Ctrl+G', click: () => mainWindow?.webContents.send('chat-grid-focus') },
        { label: 'Endiginous URL...', accelerator: 'Ctrl+Shift+U', click: promptForEndiginousUrl },
        { label: 'Cast to device...', accelerator: 'Ctrl+Shift+C', click: () => mainWindow?.webContents.executeJavaScript("window.dispatchEvent(new Event('chatgrid-cast-to-device'));") },
        { type: 'separator' },
        { label: 'Open Current Page in Browser', click: () => mainWindow && shell.openExternal(mainWindow.webContents.getURL()) },
        { type: 'separator' },
        { label: 'Quit', accelerator: 'Alt+F4', click: () => app.quit() },
      ],
    },
    {
      label: 'Audio',
      submenu: [
        {
          label: 'Audio Setup',
          accelerator: 'Ctrl+,',
          click: () => mainWindow?.webContents.executeJavaScript("document.getElementById('settingsButton')?.click();"),
        },
        {
          label: 'Connect',
          accelerator: 'Ctrl+Enter',
          click: () => mainWindow?.webContents.executeJavaScript("document.getElementById('connectButton')?.click();"),
        },
        {
          label: 'Disconnect',
          accelerator: 'Ctrl+Shift+Enter',
          click: () => mainWindow?.webContents.executeJavaScript("document.getElementById('disconnectButton')?.click();"),
        },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { label: 'Developer Tools', accelerator: 'Ctrl+Shift+I', click: () => mainWindow?.webContents.toggleDevTools() },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

async function chooseDisplayMediaSource() {
  const sources = await desktopCapturer.getSources({
    types: ['window', 'screen'],
    fetchWindowIcons: true,
    thumbnailSize: { width: 320, height: 180 },
  });
  const candidates = sources
    .filter((source) => String(source.name || '').trim())
    .slice(0, 24);
  if (candidates.length === 0) return null;
  if (candidates.length === 1) return candidates[0];
  const buttons = [...candidates.map((source) => source.name.slice(0, 60)), 'Cancel'];
  const result = await dialog.showMessageBox(mainWindow || undefined, {
    type: 'question',
    title: 'Cast Local Media',
    message: 'Choose a screen, window, browser tab, or open media app to cast into Endiginous.',
    detail: 'For app audio such as YouTube, pick the window or screen that is playing it. Windows system audio is requested when the platform allows it.',
    buttons,
    defaultId: 0,
    cancelId: buttons.length - 1,
    noLink: true,
  });
  if (result.response < 0 || result.response >= candidates.length) return null;
  return candidates[result.response];
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 820,
    minWidth: 720,
    minHeight: 520,
    title: 'Endiginous',
    backgroundColor: '#111827',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (ALLOWED_PROTOCOLS.has(new URL(url).protocol)) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  mainWindow.webContents.on('will-navigate', (event, url) => {
    const next = new URL(url);
    if (!ALLOWED_PROTOCOLS.has(next.protocol)) {
      event.preventDefault();
    }
  });

  mainWindow.webContents.on('before-input-event', (event, input) => {
    const controlOrCommand = input.control || input.meta;
    if (controlOrCommand && !input.alt && !input.shift && input.code === 'KeyR' && input.type === 'keyDown') {
      event.preventDefault();
      mainWindow?.webContents.send('chat-grid-native-key', { code: 'KeyR', ctrlKey: true, shiftKey: false });
    }
  });

  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    mainWindowUnresponsive = true;
    appendRuntimeLog('render-process-gone', details);
  });

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    if (!isMainFrame) return;
    appendRuntimeLog('did-fail-load', { errorCode, errorDescription, validatedURL });
  });

  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    if (level < 2) return;
    appendRuntimeLog('renderer-console', { level, message, line, sourceId });
  });

  mainWindow.on('unresponsive', () => {
    mainWindowUnresponsive = true;
    appendRuntimeLog('window-unresponsive');
  });

  mainWindow.on('responsive', () => {
    mainWindowUnresponsive = false;
    appendRuntimeLog('window-responsive');
  });

  const refocusWorldAfterWindowReveal = () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    mainWindow.webContents.focus();
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()) {
        mainWindow.webContents.send('chat-grid-focus');
      }
    }, 80);
  };

  mainWindow.on('restore', refocusWorldAfterWindowReveal);
  mainWindow.on('show', refocusWorldAfterWindowReveal);

  mainWindow.on('minimize', (event) => {
    event.preventDefault();
    mainWindow?.hide();
  });

  mainWindow.on('close', (event) => {
    if (isQuitting) return;
    event.preventDefault();
    mainWindow?.hide();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  loadEndiginous();
}

app.on('second-instance', () => {
  showMainWindow();
});

app.on('before-quit', () => {
  isQuitting = true;
});

if (hasSingleInstanceLock) app.whenReady().then(async () => {
  await session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowed = ['media', 'microphone', 'speaker-selection', 'midi', 'midiSysex'].includes(permission);
    callback(allowed);
  });
  session.defaultSession.setDisplayMediaRequestHandler(async (_request, callback) => {
    try {
      const source = await chooseDisplayMediaSource();
      if (!source) {
        callback({});
        return;
      }
      const selection = { video: source };
      if (process.platform === 'win32') selection.audio = 'loopback';
      callback(selection);
    } catch (error) {
      appendRuntimeLog('display-media-picker-failed', { message: error?.message || String(error) });
      callback({});
    }
  });
  createApplicationMenu();
  createWindow();
  createTray();
  app.on('activate', () => {
    showMainWindow();
  });
});

app.on('window-all-closed', () => {
  // The tray owns the app lifetime. Explicit Quit remains available in both menus.
});
