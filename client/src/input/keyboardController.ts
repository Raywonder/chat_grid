import type { GameMode } from '../state/gameState';
import type { ModeInput } from './commandTypes';

type KeyboardControllerDeps = {
  dom: {
    settingsModal: HTMLDivElement;
    canvas: HTMLCanvasElement;
  };
  state: {
    running: boolean;
    mode: GameMode;
    keysPressed: Record<string, boolean>;
    nicknameInput: string;
    cursorPos: number;
  };
  isTextEditingMode: (mode: GameMode) => boolean;
  closeSettings: () => void;
  closeInteractiveItem: () => boolean;
  hasBlockedArrowTeleport: (code: string) => boolean;
  handleModeInput: (input: ModeInput) => void;
  runImmediateMovement: () => void;
  canOpenCommandPaletteInMode: (mode: GameMode) => boolean;
  openCommandPalette: () => void;
  getModeKeyUpTarget: (activeMode: GameMode) => GameMode | null;
  onModeKeyUp: (mode: GameMode, input: Pick<ModeInput, 'code' | 'shiftKey'>) => void;
  pasteIntoActiveTextInput: (text: string) => boolean;
  updateStatus: (message: string) => void;
  setReplaceTextOnNextType: (value: boolean) => void;
};

/**
 * Wires global keyboard/paste input handlers and leaves mode-specific behavior to injected callbacks.
 */
export function setupKeyboardInputHandlers(deps: KeyboardControllerDeps): void {
  let internalClipboardText = '';
  const nativeArrowReleaseTimers = new Map<string, number>();

  function clearPressedKeyState(): void {
    for (const key of Object.keys(deps.state.keysPressed)) {
      deps.state.keysPressed[key] = false;
    }
    for (const timer of nativeArrowReleaseTimers.values()) {
      window.clearTimeout(timer);
    }
    nativeArrowReleaseTimers.clear();
  }

  function recoverFromInputError(error: unknown): void {
    clearPressedKeyState();
    // Keep the accessible UI usable even if a hidden command handler throws.
    // Do not announce a retry prompt from a hidden/minimized desktop renderer;
    // the next input frame will be clean after the pressed-key state is reset.
    console.error('Endiginous input handler recovered after an error.', error);
    // Recovery is deliberately silent. A transient input exception must not
    // turn an ordinary arrow press into a repeated retry alert.
  }

  const nativeWindow = window as Window & {
    chatGridDesktop?: unknown;
    chatGridNativeKey?: (code: string, options?: { ctrlKey?: boolean; shiftKey?: boolean }) => boolean;
  };
  nativeWindow.chatGridNativeKey = (code: string, options = {}): boolean => {
    if (!deps.state.running) {
      return false;
    }
    const isArrow = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(code);
    const isDesktopWorldShortcut =
      code === 'KeyR' && Boolean(options.ctrlKey) && !options.shiftKey && !deps.isTextEditingMode(deps.state.mode);
    if (!isArrow && !isDesktopWorldShortcut) return false;
    if (deps.hasBlockedArrowTeleport(code)) return false;
    deps.dom.canvas.focus({ preventScroll: true });
    deps.state.keysPressed[code] = true;
    try {
      deps.handleModeInput({
        code,
        key: code,
        ctrlKey: Boolean(options.ctrlKey),
        shiftKey: Boolean(options.shiftKey),
        source: 'native',
      });
      if (isArrow) {
        deps.runImmediateMovement();
      }
      const previousTimer = nativeArrowReleaseTimers.get(code);
      if (previousTimer !== undefined) window.clearTimeout(previousTimer);
      nativeArrowReleaseTimers.set(
        code,
        window.setTimeout(() => {
          deps.state.keysPressed[code] = false;
          nativeArrowReleaseTimers.delete(code);
        }, 250),
      );
    } catch (error) {
      recoverFromInputError(error);
    }
    return true;
  };

  function isTypingKey(code: string): boolean {
    return code.startsWith('Key') || code === 'Space';
  }

  function codeFromKey(key: string, location: number): string | null {
    if (key === 'Escape' || key === 'Esc') return 'Escape';
    if (key === 'Enter' || key === 'Return') return 'Enter';
    if (key === 'Backspace') return 'Backspace';
    if (key === 'Delete' || key === 'Del') return 'Delete';
    if (key === 'ArrowUp' || key === 'Up') return 'ArrowUp';
    if (key === 'ArrowDown' || key === 'Down') return 'ArrowDown';
    if (key === 'ArrowLeft' || key === 'Left') return 'ArrowLeft';
    if (key === 'ArrowRight' || key === 'Right') return 'ArrowRight';
    if (key === 'Home') return 'Home';
    if (key === 'End') return 'End';
    if (key === 'PageUp') return 'PageUp';
    if (key === 'PageDown') return 'PageDown';
    if (key === 'Tab') return 'Tab';
    if (key === ' ' || key === 'Spacebar') return 'Space';
    if (key.length === 1) {
      if (/^[a-z]$/i.test(key)) return `Key${key.toUpperCase()}`;
      if (/^[0-9]$/.test(key)) return `Digit${key}`;
      if (key === '!') return 'Digit1';
      if (key === '@') return 'Digit2';
      if (key === '#') return 'Digit3';
      if (key === '$') return 'Digit4';
      if (key === '%') return 'Digit5';
      if (key === '^') return 'Digit6';
      if (key === '&') return 'Digit7';
      if (key === '*') return 'Digit8';
      if (key === '(') return 'Digit9';
      if (key === ')') return 'Digit0';
      if (key === '+' && location === 3) return 'NumpadAdd';
      if (key === '-' && location === 3) return 'NumpadSubtract';
      if (key === '+' || key === '=') return 'Equal';
      if (key === '-' || key === '_') return 'Minus';
      if (key === '/' || key === '?') return 'Slash';
      if (key === ',' || key === '<') return 'Comma';
      if (key === '.' || key === '>') return 'Period';
      if (key === ';' || key === ':') return 'Semicolon';
      if (key === "'" || key === '"') return 'Quote';
      if (key === '[' || key === '{') return 'BracketLeft';
      if (key === ']' || key === '}') return 'BracketRight';
      if (key === '\\' || key === '|') return 'Backslash';
    }
    return null;
  }

  function normalizeInputCode(event: KeyboardEvent): string {
    if (event.code && event.code !== 'Unidentified') {
      return event.code;
    }
    return codeFromKey(event.key, event.location) ?? event.code ?? '';
  }

  function isEditableElement(target: EventTarget | null): boolean {
    if (!(target instanceof HTMLElement)) return false;
    if (target.isContentEditable) return true;
    const tagName = target.tagName.toLowerCase();
    if (target instanceof HTMLMediaElement || tagName === 'button' || tagName === 'a') return true;
    if (tagName === 'textarea' || tagName === 'select') return true;
    if (tagName !== 'input') return false;
    const input = target as HTMLInputElement;
    return !['button', 'checkbox', 'radio', 'range', 'submit', 'reset'].includes(input.type);
  }

  function shouldMoveFocusToCanvas(event: KeyboardEvent, code: string): boolean {
    if (code === 'Tab') return false;
    if (event.altKey || event.ctrlKey || event.metaKey) return false;
    if (isEditableElement(event.target)) return false;
    if (deps.isTextEditingMode(deps.state.mode)) return false;
    if (deps.dom.settingsModal.contains(event.target as Node | null)) return false;
    return (
      code.startsWith('Arrow') ||
      code === 'Enter' ||
      code === 'Space' ||
      code === 'Slash' ||
      code === 'Backslash' ||
      code === 'Escape' ||
      /^Key[A-Z]$/.test(code) ||
      /^Digit[0-9]$/.test(code)
    );
  }

  function isDesktopClient(): boolean {
    return document.documentElement.classList.contains('chatgrid-native') || nativeWindow.chatGridDesktop != null;
  }

  document.addEventListener('keydown', (event) => {
    const code = normalizeInputCode(event);
    if (!code) return;
    const hasShortcutModifier = event.ctrlKey || event.metaKey;
    const input: ModeInput = {
      code,
      key: event.key,
      ctrlKey: hasShortcutModifier,
      shiftKey: event.shiftKey,
      source: 'web',
    };

    if (!deps.dom.settingsModal.classList.contains('hidden') && code === 'Escape') {
      deps.closeSettings();
      return;
    }
    if (code === 'Escape' && deps.closeInteractiveItem()) {
      event.preventDefault();
      return;
    }

    if (!deps.state.running) return;
    if (document.activeElement !== deps.dom.canvas) {
      if (!shouldMoveFocusToCanvas(event, code)) return;
      deps.dom.canvas.focus();
    }
    if (event.altKey) return;
    const allowedModifiedNormalShortcut =
      deps.state.mode === 'normal' &&
      (code === 'KeyG' ||
        code === 'KeyM' ||
        (isDesktopClient() && code === 'KeyR') ||
        code === 'Comma' ||
        code === 'Period' ||
        code === 'BracketLeft' ||
        code === 'BracketRight');
    if (hasShortcutModifier && !deps.isTextEditingMode(deps.state.mode) && !allowedModifiedNormalShortcut) return;
    if (deps.hasBlockedArrowTeleport(code)) {
      event.preventDefault();
      return;
    }

    const isNativePasteShortcut = hasShortcutModifier && deps.isTextEditingMode(deps.state.mode) && code === 'KeyV';
    // Arrow keys are world controls while the grid is running. Letting their
    // browser default through makes the page (and some screen-reader browse
    // modes) scroll instead of reliably delivering movement to the canvas.
    // The focused canvas has role=application, so consume the arrows just as
    // we do every other active Grid command.
    if (!isNativePasteShortcut) {
      event.preventDefault();
    }

    if (hasShortcutModifier && deps.isTextEditingMode(deps.state.mode)) {
      if (code === 'KeyV') {
        return;
      }
      if (code === 'KeyC') {
        const text = deps.state.nicknameInput;
        internalClipboardText = text;
        void navigator.clipboard?.writeText(text).catch(() => undefined);
        deps.updateStatus('copied');
        return;
      }
      if (code === 'KeyX') {
        const text = deps.state.nicknameInput;
        internalClipboardText = text;
        void navigator.clipboard?.writeText(text).catch(() => undefined);
        deps.state.nicknameInput = '';
        deps.state.cursorPos = 0;
        deps.setReplaceTextOnNextType(false);
        deps.updateStatus('cut');
        return;
      }
    }

    if (isTypingKey(code) && deps.state.keysPressed[code]) return;

    const opensCommandPalette =
      deps.canOpenCommandPaletteInMode(deps.state.mode) &&
      ((code === 'KeyK' && event.shiftKey) || code === 'ContextMenu' || (code === 'F10' && event.shiftKey));
    if (opensCommandPalette) {
      deps.openCommandPalette();
      deps.state.keysPressed[code] = true;
      return;
    }

    try {
      deps.handleModeInput(input);
      deps.state.keysPressed[code] = true;
      if (code.startsWith('Arrow')) {
        deps.runImmediateMovement();
      }
    } catch (error) {
      recoverFromInputError(error);
    }
  });

  document.addEventListener('keyup', (event) => {
    const code = normalizeInputCode(event);
    const keyUpMode = deps.getModeKeyUpTarget(deps.state.mode);
    if (code && keyUpMode) {
      deps.onModeKeyUp(keyUpMode, {
        code,
        shiftKey: event.shiftKey,
      });
    }
    if (code) {
      deps.state.keysPressed[code] = false;
    }
    if (event.code && event.code !== code) {
      deps.state.keysPressed[event.code] = false;
    }
  });

  document.addEventListener('paste', (event) => {
    if (document.activeElement !== deps.dom.canvas) return;
    if (!deps.state.running) return;
    const pasted = event.clipboardData?.getData('text') ?? internalClipboardText;
    if (!deps.pasteIntoActiveTextInput(pasted)) return;
    event.preventDefault();
    deps.updateStatus('pasted');
  });
}
