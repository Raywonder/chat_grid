/** Converts a 0-1000 slider value into gain; values above 100 act as a boost. */
export function volumePercentToGain(value: unknown, fallbackPercent: number): number {
  const raw = Number(value);
  const normalized = Number.isFinite(raw)
    ? Math.max(0, Math.min(1000, raw)) / 100
    : Math.max(0, Math.min(1000, fallbackPercent)) / 100;
  if (normalized > 1) {
    return normalized;
  }
  // Smoothstep keeps 0->0, 50->0.5, 100->1 while easing low/high ranges.
  return normalized * normalized * (3 - 2 * normalized);
}
