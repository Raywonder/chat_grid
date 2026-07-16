let worldControlsActive = false;

export function activateWorldControls(): void {
  worldControlsActive = true;
}

export function deactivateWorldControls(): void {
  worldControlsActive = false;
}

export function areWorldControlsActive(): boolean {
  return worldControlsActive;
}
