const { contextBridge, ipcRenderer } = require('electron');

const desktopBridge = {
  platform: process.platform,
};
contextBridge.exposeInMainWorld('indiginousDesktop', desktopBridge);
// Keep the bridge available to an older web bundle during a staged update.
contextBridge.exposeInMainWorld('chatGridDesktop', desktopBridge);

document.documentElement.classList.add('indiginous-native');
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
    console.error('Indiginous desktop focus bridge recovered after an error.', error);
  }
});

ipcRenderer.on('chat-grid-native-key', (_event, input) => {
  try {
    if (!input || typeof input.code !== 'string') return;
    const options = {
      ctrlKey: Boolean(input.ctrlKey),
      shiftKey: Boolean(input.shiftKey),
    };
    window.indiginousNativeKey?.(input.code, options) ?? window.chatGridNativeKey?.(input.code, options);
  } catch (error) {
    console.error('Indiginous desktop key bridge recovered after an error.', error);
  }
});
