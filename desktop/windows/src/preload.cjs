const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('chatGridDesktop', {
  platform: process.platform,
});

ipcRenderer.on('chat-grid-focus', () => {
  const focusButton = document.getElementById('focusGridButton');
  const canvas = document.getElementById('gameCanvas');
  if (focusButton instanceof HTMLButtonElement && !focusButton.classList.contains('hidden')) {
    focusButton.click();
    return;
  }
  if (canvas instanceof HTMLCanvasElement) {
    canvas.focus();
  }
});
