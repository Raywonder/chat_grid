const { app, BrowserWindow, Menu, dialog, shell, session } = require('electron');
const fs = require('fs');
const path = require('path');

const DEFAULT_CHAT_GRID_URL = 'https://blind.software/chatgrid/';
const ALLOWED_PROTOCOLS = new Set(['http:', 'https:']);

let mainWindow = null;

function settingsPath() {
  return path.join(app.getPath('userData'), 'settings.json');
}

function normalizeChatGridUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return DEFAULT_CHAT_GRID_URL;
  const url = new URL(raw);
  if (!ALLOWED_PROTOCOLS.has(url.protocol)) {
    throw new Error('Chat Grid URL must start with http:// or https://.');
  }
  return url.toString();
}

function readSettings() {
  const fromEnv = process.env.CHGRID_DESKTOP_URL;
  if (fromEnv) {
    return { chatGridUrl: normalizeChatGridUrl(fromEnv) };
  }
  try {
    const raw = fs.readFileSync(settingsPath(), 'utf8');
    const parsed = JSON.parse(raw);
    return { chatGridUrl: normalizeChatGridUrl(parsed.chatGridUrl) };
  } catch {
    return { chatGridUrl: DEFAULT_CHAT_GRID_URL };
  }
}

function writeSettings(nextSettings) {
  fs.mkdirSync(app.getPath('userData'), { recursive: true });
  fs.writeFileSync(settingsPath(), JSON.stringify(nextSettings, null, 2) + '\n');
}

function getCurrentUrl() {
  return readSettings().chatGridUrl;
}

function loadChatGrid(url = getCurrentUrl()) {
  if (!mainWindow) return;
  mainWindow.loadURL(url);
}

async function promptForChatGridUrl() {
  if (!mainWindow) return;
  const current = getCurrentUrl();
  const result = await dialog.showMessageBox(mainWindow, {
    type: 'question',
    title: 'Chat Grid URL',
    message: 'Choose which Chat Grid to open.',
    detail: `Current URL:\n${current}`,
    buttons: ['Use live Chat Grid', 'Use local development', 'Cancel'],
    defaultId: 0,
    cancelId: 2,
    noLink: true,
  });
  if (result.response === 2) return;
  const chatGridUrl = result.response === 1 ? 'http://localhost:5173/' : DEFAULT_CHAT_GRID_URL;
  writeSettings({ chatGridUrl });
  loadChatGrid(chatGridUrl);
}

function createApplicationMenu() {
  const template = [
    {
      label: 'Chat Grid',
      submenu: [
        { label: 'Reload', accelerator: 'Ctrl+R', click: () => mainWindow?.reload() },
        { label: 'Focus Grid', accelerator: 'Ctrl+G', click: () => mainWindow?.webContents.send('chat-grid-focus') },
        { label: 'Chat Grid URL...', accelerator: 'Ctrl+Shift+U', click: promptForChatGridUrl },
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

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 820,
    minWidth: 720,
    minHeight: 520,
    title: 'Chat Grid',
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

  loadChatGrid();
}

app.whenReady().then(async () => {
  await session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowed = ['media', 'microphone', 'speaker-selection'].includes(permission);
    callback(allowed);
  });
  createApplicationMenu();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
