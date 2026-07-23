/**
 * UI elements used by binder setup.
 */
type UiDom = {
  connectButton: HTMLButtonElement;
  disconnectButton: HTMLButtonElement;
  focusGridButton: HTMLButtonElement;
  openSettingsButton: HTMLButtonElement;
  closeSettingsButton: HTMLButtonElement;
  audioInputSelect: HTMLSelectElement;
  audioOutputSelect: HTMLSelectElement;
  announcementModeSelect: HTMLSelectElement;
  radioAnnouncementModeSelect: HTMLSelectElement;
  itemBeaconsToggle: HTMLInputElement;
  movementDirectionsToggle: HTMLInputElement;
  flexPbxOutboundDialingToggle: HTMLInputElement;
  flexPbxDialingPrefixesInput: HTMLInputElement;
  settingsModal: HTMLDivElement;
  canvas: HTMLCanvasElement;
};

/**
 * Dependency contract for binding DOM event handlers.
 */
type UiBindingsDeps = {
  dom: UiDom;
  updateConnectAvailability: () => void;
  connect: () => Promise<void>;
  disconnect: () => void;
  closeSettings: () => void;
  openSettings: () => void;
  updateStatus: (message: string) => void;
  getGridName: () => string;
  sfxUiBlip: () => void;
  setupLocalMedia: (audioDeviceId: string) => Promise<void>;
  setPreferredInput: (id: string, name: string) => void;
  setPreferredOutput: (id: string, name: string) => void;
  updateDeviceSummary: () => void;
  setOutputDevice: (id: string) => Promise<void>;
  setAnnouncementMode: (mode: string) => void;
  setRadioAnnouncementMode: (mode: string) => void;
  setItemBeacons: (enabled: boolean) => void;
  setMovementDirections: (enabled: boolean) => void;
  setFlexPbxDialingPreferences: (enabled: boolean, prefixesText: string) => void;
};

/**
 * Attaches UI listeners (connect/settings/device changes) and focus traps.
 */
export function setupUiHandlers(deps: UiBindingsDeps): void {
  deps.dom.connectButton.addEventListener('click', () => {
    void deps.connect();
  });

  deps.dom.disconnectButton.addEventListener('click', () => {
    deps.disconnect();
  });

  deps.dom.focusGridButton.addEventListener('click', () => {
    deps.dom.canvas.focus();
    deps.updateStatus(`${deps.getGridName()} focused.`);
    deps.sfxUiBlip();
  });

  deps.dom.closeSettingsButton.addEventListener('click', () => {
    deps.closeSettings();
  });

  deps.dom.openSettingsButton.addEventListener('click', () => {
    deps.openSettings();
  });

  deps.dom.audioInputSelect.addEventListener('change', (event) => {
    const target = event.target as HTMLSelectElement;
    if (!target.value) return;
    deps.setPreferredInput(target.value, target.selectedOptions[0]?.text || '');
    deps.updateDeviceSummary();
    void deps.setupLocalMedia(target.value);
  });

  deps.dom.audioOutputSelect.addEventListener('change', (event) => {
    const target = event.target as HTMLSelectElement;
    deps.setPreferredOutput(target.value, target.selectedOptions[0]?.text || '');
    deps.updateDeviceSummary();
    void deps.setOutputDevice(target.value);
  });

  deps.dom.announcementModeSelect.addEventListener('change', (event) => {
    const target = event.target as HTMLSelectElement;
    deps.setAnnouncementMode(target.value);
  });

  deps.dom.radioAnnouncementModeSelect.addEventListener('change', (event) => {
    const target = event.target as HTMLSelectElement;
    deps.setRadioAnnouncementMode(target.value);
  });

  deps.dom.itemBeaconsToggle.addEventListener('change', (event) => {
    const target = event.target as HTMLInputElement;
    deps.setItemBeacons(target.checked);
  });

  deps.dom.movementDirectionsToggle.addEventListener('change', (event) => {
    const target = event.target as HTMLInputElement;
    deps.setMovementDirections(target.checked);
  });

  deps.dom.flexPbxOutboundDialingToggle.addEventListener('change', () => {
    deps.setFlexPbxDialingPreferences(
      deps.dom.flexPbxOutboundDialingToggle.checked,
      deps.dom.flexPbxDialingPrefixesInput.value,
    );
  });

  deps.dom.flexPbxDialingPrefixesInput.addEventListener('change', () => {
    deps.setFlexPbxDialingPreferences(
      deps.dom.flexPbxOutboundDialingToggle.checked,
      deps.dom.flexPbxDialingPrefixesInput.value,
    );
  });

  deps.dom.settingsModal.addEventListener('keydown', (event) => {
    if (event.key !== 'Tab') return;
    const focusable = Array.from(deps.dom.settingsModal.querySelectorAll<HTMLElement>('select, input, button')).filter(
      (element) => !element.hidden && !element.hasAttribute('hidden') && !(element as HTMLButtonElement | HTMLInputElement).disabled,
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (event.shiftKey && document.activeElement === first) {
      last.focus();
      event.preventDefault();
      return;
    }

    if (!event.shiftKey && document.activeElement === last) {
      first.focus();
      event.preventDefault();
    }
  });
}
