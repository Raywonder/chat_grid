/**
 * Declarative command ids for the primary gameplay input mode.
 */
export type MainModeCommand =
  | 'editNickname'
  | 'toggleMute'
  | 'toggleOutputMode'
  | 'toggleLoopback'
  | 'toggleVoiceLayer'
  | 'toggleItemLayer'
  | 'toggleMediaLayer'
  | 'toggleWorldLayer'
  | 'cycleAnnouncementMode'
  | 'toggleItemBeacons'
  | 'masterVolumeUp'
  | 'masterVolumeDown'
  | 'openEffectSelect'
  | 'effectValueUp'
  | 'effectValueDown'
  | 'speakCoordinates'
  | 'openMicGainEdit'
  | 'calibrateMicrophone'
  | 'cycleFocusedItem'
  | 'useItem'
  | 'secondaryUseItem'
  | 'radioRemoteStationNext'
  | 'radioRemoteStationPrevious'
  | 'radioRemoteVolumeUp'
  | 'radioRemoteVolumeDown'
  | 'openUserActionMenu'
  | 'interactItem'
  | 'speakUsers'
  | 'addItem'
  | 'locateNearestItem'
  | 'listItems'
  | 'pickupDropItem'
  | 'pickupDropAttachedItems'
  | 'openItemManagement'
  | 'editItem'
  | 'inspectItem'
  | 'pingServer'
  | 'locateNearestUser'
  | 'listUsers'
  | 'listLocations'
  | 'openHelp'
  | 'openChat'
  | 'openDirectMessage'
  | 'openAdminMenu'
  | 'chatPrev'
  | 'chatNext'
  | 'chatFirst'
  | 'chatLast'
  | 'escape';

/**
 * Maps raw key events to a semantic command for main mode handling.
 */
export function resolveMainModeCommand(code: string, shiftKey: boolean, ctrlKey = false): MainModeCommand | null {
  if (ctrlKey && (code === 'Comma' || code === 'Period' || code === 'BracketLeft' || code === 'BracketRight')) return null;
  if (ctrlKey && code === 'ArrowRight') return 'radioRemoteStationNext';
  if (ctrlKey && code === 'ArrowLeft') return 'radioRemoteStationPrevious';
  if (ctrlKey && shiftKey && (code === 'ArrowUp' || code === 'KeyU')) return 'radioRemoteVolumeUp';
  if (ctrlKey && shiftKey && (code === 'ArrowDown' || code === 'KeyD')) return 'radioRemoteVolumeDown';
  if (ctrlKey && code === 'KeyM') return 'openDirectMessage';
  if (code === 'KeyG') return 'listLocations';
  if (code === 'KeyN') return shiftKey ? null : 'editNickname';
  if (code === 'KeyM') return shiftKey ? 'toggleOutputMode' : 'toggleMute';
  if (code === 'Digit1') return shiftKey ? 'toggleLoopback' : 'toggleVoiceLayer';
  if (code === 'Digit2') return 'toggleItemLayer';
  if (code === 'Digit3') return 'toggleMediaLayer';
  if (code === 'Digit4') return 'toggleWorldLayer';
  if (code === 'Digit5') return 'cycleAnnouncementMode';
  if (code === 'Digit6') return 'toggleItemBeacons';
  if (code === 'Digit7') return 'toggleOutputMode';
  if (code === 'Digit8') return 'toggleMute';
  if (code === 'Digit9') return 'toggleVoiceLayer';
  if (code === 'KeyE') return shiftKey ? null : 'openEffectSelect';
  if (code === 'Equal') return shiftKey ? 'effectValueUp' : 'masterVolumeUp';
  if (code === 'Minus') return shiftKey ? 'effectValueDown' : 'masterVolumeDown';
  if (code === 'NumpadAdd') return 'masterVolumeUp';
  if (code === 'NumpadSubtract') return 'masterVolumeDown';
  if (code === 'KeyC') return shiftKey ? null : 'speakCoordinates';
  if (code === 'KeyV') return shiftKey ? 'calibrateMicrophone' : 'openMicGainEdit';
  if (code === 'Tab') return 'cycleFocusedItem';
  if (code === 'Enter') return shiftKey ? 'openUserActionMenu' : 'useItem';
  if (code === 'Space') return shiftKey ? 'radioRemoteStationPrevious' : 'useItem';
  if (code === 'KeyJ') return shiftKey ? 'useItem' : 'interactItem';
  if (code === 'KeyU') return shiftKey ? null : 'speakUsers';
  if (code === 'KeyA') return shiftKey ? null : 'addItem';
  if (code === 'KeyI') return shiftKey ? 'listItems' : 'locateNearestItem';
  if (code === 'KeyD') return shiftKey ? 'pickupDropAttachedItems' : 'pickupDropItem';
  if (code === 'KeyO') return shiftKey ? 'inspectItem' : 'editItem';
  if (code === 'KeyP') return shiftKey ? null : 'pingServer';
  if (code === 'KeyL') return shiftKey ? 'listUsers' : 'locateNearestUser';
  if (code === 'Slash') return shiftKey ? 'openHelp' : 'openChat';
  if (code === 'KeyH') return shiftKey ? null : 'openChat';
  if (code === 'KeyZ') return shiftKey ? 'openAdminMenu' : 'openItemManagement';
  if (code === 'Comma') return shiftKey ? 'chatFirst' : 'chatPrev';
  if (code === 'Period') return shiftKey ? 'chatLast' : 'chatNext';
  if (code === 'Escape') return shiftKey ? null : 'escape';
  return null;
}
