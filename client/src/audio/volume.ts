/** Converts a 0-100 slider value into gain using a perceptual smoothstep curve. */
export function volumePercentToGain(value: unknown, fallbackPercent: number): number {
  const raw = Number(value);
  const normalized = Number.isFinite(raw) ? Math.max(0, Math.min(100, raw)) / 100 : Math.max(0, Math.min(100, fallbackPercent)) / 100;
  // Smoothstep keeps 0->0, 50->0.5, 100->1 while easing low/high ranges.
  return normalized * normalized * (3 - 2 * normalized);
}
