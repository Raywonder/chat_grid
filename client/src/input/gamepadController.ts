import type { GameMode } from '../state/gameState';
import type { ModeInput } from './commandTypes';

type GamepadControllerDeps = {
  getRunning: () => boolean;
  getMode: () => GameMode;
  isMediaGuideOpen?: () => boolean;
  setDirection: (code: 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight', pressed: boolean) => void;
  handleModeInput: (input: ModeInput) => void;
};

type Direction = 'ArrowUp' | 'ArrowDown' | 'ArrowLeft' | 'ArrowRight';

const BUTTON_COMMANDS: Array<[number, string]> = [
  [0, 'Enter'], // A / Cross
  [1, 'Escape'], // B / Circle
  [2, 'Space'], // X / Square: use the focused item
  [3, 'KeyI'], // Y / Triangle: information
];

/** Polls standard Xbox/DirectInput gamepads without taking over keyboard input. */
export function setupGamepadInputHandlers(deps: GamepadControllerDeps) {
  const previousButtons = new Map<number, boolean>();
  const directions: Direction[] = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];

  function firstConnectedGamepad(): Gamepad | null {
    if (typeof navigator.getGamepads !== 'function') return null;
    return Array.from(navigator.getGamepads()).find((pad): pad is Gamepad => Boolean(pad && pad.connected)) ?? null;
  }

  function directionPressed(pad: Gamepad, index: number, axis: number, sign: number): boolean {
    const button = pad.buttons[index]?.pressed ?? false;
    const axisValue = Number(pad.axes[axis] ?? 0);
    return button || (sign < 0 ? axisValue < -0.5 : axisValue > 0.5);
  }

  function update(): void {
    const pad = firstConnectedGamepad();
    if (!deps.getRunning() || !pad) {
      for (const code of directions) deps.setDirection(code, false);
      return;
    }

    const guideOpen = deps.isMediaGuideOpen?.() ?? false;
    const directionState: Array<[Direction, boolean]> = [
      ['ArrowUp', directionPressed(pad, 12, 1, -1)],
      ['ArrowDown', directionPressed(pad, 13, 1, 1)],
      ['ArrowLeft', directionPressed(pad, 14, 0, -1)],
      ['ArrowRight', directionPressed(pad, 15, 0, 1)],
    ];
    for (const [code, pressed] of directionState) {
      if (guideOpen && pressed && !(previousButtons.get(100 + directions.indexOf(code)) ?? false)) {
        deps.handleModeInput({ code, key: code, ctrlKey: false, shiftKey: false, source: 'gamepad' });
      }
      if (!guideOpen) deps.setDirection(code, pressed);
      previousButtons.set(100 + directions.indexOf(code), pressed);
    }

    for (const [buttonIndex, code] of BUTTON_COMMANDS) {
      const pressed = pad.buttons[buttonIndex]?.pressed ?? false;
      const wasPressed = previousButtons.get(buttonIndex) ?? false;
      if (pressed && !wasPressed) {
        deps.handleModeInput({
          code,
          key: code,
          ctrlKey: false,
          shiftKey: false,
          source: 'gamepad',
        });
      }
      previousButtons.set(buttonIndex, pressed);
    }
  }

  return { update };
}
