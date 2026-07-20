const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('chatGridDesktop', {
  platform: process.platform,
});

document.documentElement.classList.add('chatgrid-native');

ipcRenderer.on('chat-grid-focus', () => {
  try {
    const focusButton = document.getElementById('focusGridButton');
    const canvas = document.getElementById('gameCanvas');
    if (focusButton instanceof HTMLButtonElement && !focusButton.classList.contains('hidden')) {
      focusButton.click();
      return;
    }
    if (canvas instanceof HTMLCanvasElement) {
      canvas.focus();
    }
  } catch (error) {
    console.error('Endiginous desktop focus bridge recovered after an error.', error);
  }
});

ipcRenderer.on('chat-grid-native-key', (_event, input) => {
  try {
    if (!input || typeof input.code !== 'string') return;
    window.chatGridNativeKey?.(input.code, {
      ctrlKey: Boolean(input.ctrlKey),
      shiftKey: Boolean(input.shiftKey),
    });
  } catch (error) {
    console.error('Endiginous desktop key bridge recovered after an error.', error);
  }
});
