import type { GameMode } from '../state/gameState';

type MidiMessageEventLike = {
  data: Uint8Array | number[];
};

type MidiInputLike = {
  name?: string;
  onmidimessage: ((event: MidiMessageEventLike) => void) | null;
};

type MidiAccessLike = {
  inputs: Map<string, MidiInputLike>;
  onstatechange: (() => void) | null;
};

type MidiNavigator = Navigator & {
  requestMIDIAccess?: (options?: { sysex?: boolean }) => Promise<MidiAccessLike>;
};

type MidiControllerDeps = {
  button: HTMLButtonElement;
  state: {
    mode: GameMode;
  };
  handleMidiNoteOn: (mode: GameMode, midi: number, velocity: number) => boolean;
  handleMidiNoteOff: (mode: GameMode, midi: number) => boolean;
  updateStatus: (message: string) => void;
  sfxUiBlip: () => void;
  sfxUiCancel: () => void;
};

export type MidiControllerHandle = {
  requestEnable: (reason?: 'manual' | 'piano' | 'auto') => Promise<boolean>;
  setControlVisible: (visible: boolean) => void;
};

const NOTE_ON = 0x90;
const NOTE_OFF = 0x80;

/** Wires optional Web MIDI devices into MIDI-capable item behaviors. */
export function setupMidiInputHandlers(deps: MidiControllerDeps): MidiControllerHandle {
  let midiAccess: MidiAccessLike | null = null;
  let enablePromise: Promise<boolean> | null = null;
  let lastInputCount = -1;

  function midiSupported(): boolean {
    return typeof (navigator as MidiNavigator).requestMIDIAccess === 'function';
  }

  function setControlVisible(visible: boolean): void {
    deps.button.classList.toggle('hidden', !visible);
    deps.button.hidden = !visible;
  }

  function handleMidiMessage(event: MidiMessageEventLike): void {
    const [statusByte = 0, data1 = 0, data2 = 0] = Array.from(event.data);
    const status = statusByte & 0xf0;
    if (status === NOTE_ON && data2 > 0) {
      deps.handleMidiNoteOn(deps.state.mode, data1, data2);
      return;
    }
    if (status === NOTE_OFF || (status === NOTE_ON && data2 === 0)) {
      deps.handleMidiNoteOff(deps.state.mode, data1);
      return;
    }
  }

  function attachInputs(announceChange = false): number {
    if (!midiAccess) return 0;
    let count = 0;
    for (const input of midiAccess.inputs.values()) {
      input.onmidimessage = handleMidiMessage;
      count += 1;
    }
    deps.button.textContent = count > 0 ? `MIDI on (${count})` : 'MIDI on';
    if (announceChange && lastInputCount >= 0 && count !== lastInputCount) {
      deps.updateStatus(count > 0 ? `${count} MIDI device${count === 1 ? '' : 's'} connected.` : 'MIDI device disconnected.');
    }
    lastInputCount = count;
    return count;
  }

  deps.button.disabled = !midiSupported();
  deps.button.textContent = midiSupported() ? 'Enable MIDI' : 'MIDI unavailable';
  setControlVisible(false);

  async function requestEnable(reason: 'manual' | 'piano' | 'auto' = 'manual'): Promise<boolean> {
    if (!midiSupported()) {
      if (reason === 'manual') {
        deps.updateStatus('MIDI is unavailable in this browser.');
        deps.sfxUiCancel();
      }
      return false;
    }
    if (midiAccess) {
      attachInputs();
      return true;
    }
    if (enablePromise) return enablePromise;
    enablePromise = (async () => {
      try {
        midiAccess = await (navigator as MidiNavigator).requestMIDIAccess?.();
        if (!midiAccess) throw new Error('MIDI unavailable');
        midiAccess.onstatechange = () => attachInputs(true);
        const inputCount = attachInputs();
        if (reason !== 'auto') {
          deps.updateStatus(reason === 'piano' ? 'MIDI enabled for piano.' : 'MIDI enabled.');
          deps.sfxUiBlip();
        } else if (inputCount > 0) {
          deps.updateStatus(`${inputCount} MIDI device${inputCount === 1 ? '' : 's'} detected.`);
        }
        return true;
      } catch {
        if (reason === 'manual') {
          deps.updateStatus('MIDI permission was not granted.');
          deps.sfxUiCancel();
        }
        return false;
      } finally {
        enablePromise = null;
      }
    })();
    return enablePromise;
  }

  deps.button.addEventListener('click', () => {
    void requestEnable('manual');
  });

  async function enablePreviouslyAuthorizedMidi(): Promise<void> {
    if (!midiSupported() || !navigator.permissions?.query) return;
    try {
      const permission = await navigator.permissions.query(
        { name: 'midi' } as PermissionDescriptor,
      );
      if (permission.state === 'granted') {
        await requestEnable('auto');
      }
      permission.addEventListener('change', () => {
        if (permission.state === 'granted') void requestEnable('auto');
      });
    } catch {
      // Browsers without a MIDI permission descriptor retain manual enablement.
    }
  }
  void enablePreviouslyAuthorizedMidi();

  return { requestEnable, setControlVisible };
}
