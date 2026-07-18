export type AudioLayerState = {
  voice: boolean;
  item: boolean;
  media: boolean;
  world: boolean;
};

export type AnnouncementMode = 'full' | 'sounds_only' | 'required_only';
export type RadioAnnouncementMode = 'full' | 'sounds_only' | 'off';

export type AudioAnnouncementSettings = {
  mode: AnnouncementMode;
  radioAnnouncementMode: RadioAnnouncementMode;
  itemBeacons: boolean;
  movementDirections: boolean;
};
