import { describe, expect, it } from 'vitest';
import { setupGamepadInputHandlers } from './gamepadController';

function pad(buttons: boolean[], axes = [0, 0]): Gamepad {
  return {
    axes,
    buttons: buttons.map((pressed) => ({ pressed, value: pressed ? 1 : 0 } as GamepadButton)),
    connected: true,
    id: 'Xbox Controller',
    index: 0,
    mapping: 'standard',
    timestamp: 1,
    hapticActuators: [],
    vibrationActuator: null,
  } as unknown as Gamepad;
}

describe('gamepadController', () => {
  it('maps standard d-pad/stick movement and edge-triggered Xbox buttons', () => {
    const original = navigator.getGamepads;
    let current = pad(Array(16).fill(false), [-1, 0]);
    Object.defineProperty(navigator, 'getGamepads', { configurable: true, value: () => [current] });
    const directions: string[] = [];
    const commands: string[] = [];
    const controller = setupGamepadInputHandlers({
      getRunning: () => true,
      getMode: () => 'normal',
      setDirection: (code, pressed) => { if (pressed) directions.push(code); },
      handleModeInput: (input) => commands.push(input.code),
    });

    controller.update();
    expect(directions).toContain('ArrowLeft');
    expect(commands).toEqual([]);
    current = pad([true, false, false, false, ...Array(12).fill(false)]);
    controller.update();
    expect(commands).toEqual(['Enter']);
    controller.update();
    expect(commands).toEqual(['Enter']);
    Object.defineProperty(navigator, 'getGamepads', { configurable: true, value: original });
  });
});
