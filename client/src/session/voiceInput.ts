type SpeechRecognitionAlternativeLike = { transcript: string };
type SpeechRecognitionResultLike = {
  isFinal: boolean;
  length: number;
  [index: number]: SpeechRecognitionAlternativeLike;
};
type SpeechRecognitionEventLike = Event & {
  resultIndex: number;
  results: { length: number; [index: number]: SpeechRecognitionResultLike };
};
type SpeechRecognitionErrorEventLike = Event & { error?: string };

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type VoiceInputOptions = {
  onTranscript: (text: string) => void;
  onStatus?: (message: string) => void;
};

/** Bridges browser speech recognition to the in-world companion while connected. */
export class VoiceInput {
  private recognition: SpeechRecognitionLike | null = null;
  private active = false;
  private restartTimer: number | null = null;
  private playbackSuppressionDepth = 0;
  private ignoreResultsUntilMs = 0;
  private focusMode = false;

  constructor(private readonly options: VoiceInputOptions) {}

  isSupported(): boolean {
    return this.getConstructor() !== null;
  }

  start(): boolean {
    if (this.active && this.recognition !== null) return true;
    const Constructor = this.getConstructor();
    if (!Constructor) {
      this.options.onStatus?.('Live voice input is unavailable in this browser; microphone audio is still connected.');
      return false;
    }

    this.active = true;
    this.recognition = new Constructor();
    this.recognition.continuous = true;
    this.recognition.interimResults = false;
    this.recognition.lang = document.documentElement.lang || 'en-US';
    this.recognition.onresult = (event) => {
      if (this.focusMode || this.playbackSuppressionDepth > 0 || Date.now() < this.ignoreResultsUntilMs) return;
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result.isFinal) continue;
        const text = result[0]?.transcript?.trim();
        if (text) this.options.onTranscript(text);
      }
    };
    this.recognition.onerror = (event) => {
      if (!this.active) return;
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        this.options.onStatus?.('Browser speech input is blocked; allow speech recognition for Indiginous.');
        this.stop();
      }
    };
    this.recognition.onend = () => {
      if (!this.active || this.focusMode || this.playbackSuppressionDepth > 0 || this.restartTimer !== null) return;
      this.restartTimer = window.setTimeout(() => {
        this.restartTimer = null;
        try {
          this.recognition?.start();
        } catch {
          // The browser may still be finishing the previous recognition session.
          this.scheduleRestart();
        }
      }, 250);
    };
    try {
      this.recognition.start();
      this.options.onStatus?.('Live voice input is listening in Indiginous.');
      return true;
    } catch {
      this.options.onStatus?.('Could not start live voice input; microphone audio is still connected.');
      this.stop();
      return false;
    }
  }

  stop(): void {
    this.active = false;
    this.playbackSuppressionDepth = 0;
    this.stopRecognitionInstance();
  }

  /** Ignore background speech while keeping the microphone session available. */
  setFocusMode(enabled: boolean): void {
    this.focusMode = enabled;
    if (enabled) {
      this.stopRecognitionInstance();
      return;
    }
    if (this.active && this.recognition === null && this.playbackSuppressionDepth === 0) {
      this.ignoreResultsUntilMs = Date.now() + 500;
      this.start();
    }
  }

  isFocusModeEnabled(): boolean {
    return this.focusMode;
  }

  /** Temporarily pauses recognition while agent speech is audible. */
  suspendForPlayback(): void {
    if (!this.active) return;
    this.playbackSuppressionDepth += 1;
    this.ignoreResultsUntilMs = Date.now() + 500;
    if (this.playbackSuppressionDepth === 1) this.stopRecognitionInstance();
  }

  /** Resumes recognition after all overlapping agent speech has finished. */
  resumeAfterPlayback(): void {
    if (this.playbackSuppressionDepth === 0) return;
    this.playbackSuppressionDepth -= 1;
    if (this.playbackSuppressionDepth === 0 && this.active && this.recognition === null) {
      this.ignoreResultsUntilMs = Date.now() + 500;
      this.start();
    }
  }

  private stopRecognitionInstance(): void {
    if (this.restartTimer !== null) {
      window.clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }
    const recognition = this.recognition;
    this.recognition = null;
    if (recognition) {
      recognition.onend = null;
      recognition.onresult = null;
      recognition.onerror = null;
      try {
        recognition.stop();
      } catch {
        // It is already stopped; there is nothing left to clean up.
      }
    }
  }

  private scheduleRestart(): void {
    if (!this.active || this.focusMode || this.playbackSuppressionDepth > 0 || this.restartTimer !== null) return;
    this.restartTimer = window.setTimeout(() => {
      this.restartTimer = null;
      try {
        this.recognition?.start();
      } catch {
        this.scheduleRestart();
      }
    }, 500);
  }

  private getConstructor(): SpeechRecognitionConstructor | null {
    const host = window as Window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    return host.SpeechRecognition ?? host.webkitSpeechRecognition ?? null;
  }
}
