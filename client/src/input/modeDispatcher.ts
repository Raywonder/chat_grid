import type { GameMode } from '../state/gameState';
import type { ModeInput } from './commandTypes';

type ModeHandler = (input: ModeInput) => void;

type ModeHandlers = Partial<Record<GameMode, ModeHandler>>;

type DispatchOptions = {
  mode: GameMode;
  input: ModeInput;
  handlers: ModeHandlers;
  onNormalMode: (code: string, shiftKey: boolean, ctrlKey: boolean) => void;
};

/**
 * Routes key input to the handler for the current game mode.
 */
export function dispatchModeInput(options: DispatchOptions): void {
  const modeHandler = options.handlers[options.mode];
  if (modeHandler) {
    modeHandler(options.input);
    return;
  }
  options.onNormalMode(options.input.code, options.input.shiftKey, options.input.ctrlKey);
}
