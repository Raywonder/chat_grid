import { type IncomingMessage } from '../../network/protocol';
import { type GameMode, type WorldItem } from '../../state/gameState';
import { type CommandDescriptor, type ModeInput } from '../../input/commandTypes';
import { createPianoBehavior } from './piano/behavior';
import { type ItemBehavior, type ItemBehaviorDeps } from './runtimeShared';

/** Runtime registry that composes all per-item client behavior modules. */
export class ItemBehaviorRegistry {
  private readonly behaviors: ItemBehavior[];

  constructor(deps: ItemBehaviorDeps) {
    this.behaviors = [createPianoBehavior(deps)];
  }

  /** Runs per-item initialization hooks after app bootstrap. */
  async initialize(): Promise<void> {
    for (const behavior of this.behaviors) {
      await behavior.onInit?.();
    }
  }

  /** Runs all per-item teardown hooks during disconnect/reset flows. */
  cleanup(): void {
    for (const behavior of this.behaviors) {
      behavior.onCleanup?.();
    }
  }

  /** Forwards incoming messages to behavior-specific use-result hooks. */
  onUseResultMessage(message: IncomingMessage): void {
    for (const behavior of this.behaviors) {
      behavior.onUseResultMessage?.(message);
    }
  }

  /** Lets item behaviors consume custom action-result status handling. */
  onActionResultStatus(message: Extract<IncomingMessage, { type: 'item_action_result' }>): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.onActionResultStatus?.(message)) {
        return true;
      }
    }
    return false;
  }

  /** Runs per-item world-update hooks after state changes. */
  onWorldUpdate(): void {
    for (const behavior of this.behaviors) {
      behavior.onWorldUpdate?.();
    }
  }

  /** Routes property preview changes into per-item behavior hooks. */
  onPropertyPreviewChange(item: WorldItem, key: string, value: unknown): void {
    for (const behavior of this.behaviors) {
      behavior.onPropertyPreviewChange?.(item, key, value);
    }
  }

  /** Gives item behaviors first chance to handle mode input. */
  handleModeInput(mode: GameMode, input: ModeInput): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.handleModeInput?.(mode, input)) {
        return true;
      }
    }
    return false;
  }

  /** Gives item behaviors first chance to handle mode key-up events. */
  handleModeKeyUp(mode: GameMode, input: Pick<ModeInput, 'code' | 'shiftKey'>): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.handleModeKeyUp?.(mode, input)) {
        return true;
      }
    }
    return false;
  }

  /** Gives item behaviors first chance to consume realtime MIDI note-on events. */
  handleMidiNoteOn(mode: GameMode, midi: number, velocity: number): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.handleMidiNoteOn?.(mode, midi, velocity)) {
        return true;
      }
    }
    return false;
  }

  /** Gives item behaviors first chance to consume realtime MIDI note-off events. */
  handleMidiNoteOff(mode: GameMode, midi: number): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.handleMidiNoteOff?.(mode, midi)) {
        return true;
      }
    }
    return false;
  }

  /** Returns whether any item-owned mode supports opening the command palette. */
  canOpenModeCommandPalette(mode: GameMode): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.canOpenModeCommandPalette?.(mode)) {
        return true;
      }
    }
    return false;
  }

  /** Resolves an optional suspended mode that still wants key-up events while another overlay is active. */
  getModeKeyUpTarget(activeMode: GameMode, returnMode: GameMode): GameMode | null {
    for (const behavior of this.behaviors) {
      const target = behavior.getModeKeyUpTarget?.(activeMode, returnMode);
      if (target) {
        return target;
      }
    }
    return null;
  }

  /** Returns palette-visible commands for the active item-owned mode, if any. */
  getModeCommands(mode: GameMode): CommandDescriptor[] {
    const commands: CommandDescriptor[] = [];
    for (const behavior of this.behaviors) {
      const next = behavior.getModeCommands?.(mode);
      if (next && next.length > 0) {
        commands.push(...next);
      }
    }
    return commands;
  }

  /** Runs an item-owned mode command by id, returning true when handled. */
  runModeCommand(mode: GameMode, commandId: string): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.runModeCommand?.(mode, commandId)) {
        return true;
      }
    }
    return false;
  }

  /** Gives item behaviors a chance to consume custom incoming packets. */
  onIncomingMessage(message: IncomingMessage): boolean {
    for (const behavior of this.behaviors) {
      if (behavior.onIncomingMessage?.(message)) {
        return true;
      }
    }
    return false;
  }

  /** Notifies behaviors that a peer left so they can release sender-owned runtime state. */
  onPeerLeft(senderId: string): void {
    for (const behavior of this.behaviors) {
      behavior.onPeerLeft?.(senderId);
    }
  }
}
